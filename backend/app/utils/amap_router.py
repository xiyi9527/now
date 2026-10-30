"""
高德实时路线规划
  - 驾车 / 公交 / 步行 三种模式
  - 🆕 L1 内存缓存 + L2 SQLite 持久化缓存 + TTL 24h
  - 带并发限速（高德 Web 服务 QPS ≈ 5-10，flask 单线程串行足够）
"""
import os
import requests
import threading
from typing import Optional
from datetime import datetime, timedelta

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
_BASE = "https://restapi.amap.com/v3"
_TIMEOUT = 8

# ====== 🆕 二级缓存层 ======
# L1: 进程内内存（最快，微秒级）
_L1: dict = {}
_L1_lock = threading.Lock()
_L1_MAX = 1000

# TTL 配置：不同模式缓存时长不同（路况变快点短，步行慢）
_TTL_HOURS = {
    "driving": 24,     # 驾车 24h（路况虽变但可接受）
    "transit": 12,     # 公交 12h（班次固定但路线可能调整）
    "walking": 72,     # 步行 72h（路线基本不变）
    "route_between": 24,
}
_DEFAULT_TTL = 24

_call_count = 0       # 调试用：本次进程真实 API 调用次数
_cache_hit = 0
_l2_hit = 0           # 🆕 L2 SQLite 命中计数


def _l1_get(key: str) -> Optional[dict]:
    with _L1_lock:
        return _L1.get(key)


def _l1_set(key: str, val: dict):
    with _L1_lock:
        if len(_L1) >= _L1_MAX:
            # 简单淘汰：删前 30% key
            keys = list(_L1.keys())[:_L1_MAX // 3]
            for k in keys: _L1.pop(k, None)
        _L1[key] = val


def _l2_get(key: str) -> Optional[dict]:
    """L2: 从 SQLite amap_cache 表读（带 TTL 检查）"""
    try:
        from app import create_app
        from app.models import AmapCache
        app = create_app()
        with app.app_context():
            row = AmapCache.query.filter_by(cache_key=key).first()
            if row and not row.is_expired():
                return row.value_json
            elif row:
                # 过期了，删掉
                from app import db
                db.session.delete(row)
                db.session.commit()
    except Exception:
        pass  # 没 app context 或表不存在就跳过
    return None


def _l2_set(key: str, val: dict, ttl_hours: int):
    """L2: 写入 SQLite（upsert）"""
    try:
        from app import create_app, db
        from app.models import AmapCache
        app = create_app()
        expires = datetime.utcnow() + timedelta(hours=ttl_hours)
        with app.app_context():
            row = AmapCache.query.filter_by(cache_key=key).first()
            if row:
                row.value_json = val
                row.expires_at = expires
            else:
                row = AmapCache(cache_key=key, value_json=val, expires_at=expires)
                db.session.add(row)
            db.session.commit()
    except Exception:
        pass  # 静默失败，不影响主流程


def _mode_from_key(key: str) -> str:
    """🆕 从 cache key 前缀推导 mode（比调用方传参更可靠）"""
    return key.split("|", 1)[0] if "|" in key else "driving"


def _cache_get(key: str) -> Optional[dict]:
    """🆕 二级缓存读取：L1 → L2 → None"""
    global _cache_hit, _l2_hit
    # L1 内存
    v = _l1_get(key)
    if v is not None:
        _cache_hit += 1
        return v
    # L2 SQLite
    v = _l2_get(key)
    if v is not None:
        _l2_hit += 1
        _cache_hit += 1
        _l1_set(key, v)   # 回填 L1
        return v
    return None


def _cache_set(key: str, val: dict):
    """🆕 二级缓存写入：同时写 L1 + L2，TTL 从 key 前缀推导"""
    mode = _mode_from_key(key)
    ttl = _TTL_HOURS.get(mode, _DEFAULT_TTL)
    _l1_set(key, val)
    _l2_set(key, val, ttl)


def _api_get(path: str, params: dict) -> Optional[dict]:
    """统一 GET，返回高德 response 或 None"""
    global _call_count
    params = {"key": AMAP_KEY, "output": "JSON", **params}
    try:
        _call_count += 1
        r = requests.get(f"{_BASE}{path}", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if d.get("status") != "1":
            return None
        return d
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 三种出行模式
# ---------------------------------------------------------------------------

def driving(origin_lng: float, origin_lat: float,
            dest_lng: float, dest_lat: float) -> Optional[dict]:
    """
    高德驾车路线规划
    返回 {
        distance_km, duration_min, tolls_yuan,
        steps: [{instruction, road, distance_m, duration_s}],
        polyline: "lng,lat;lng,lat;...",
    }
    """
    key = f"driving|{origin_lng:.3f},{origin_lat:.3f}|{dest_lng:.3f},{dest_lat:.3f}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    d = _api_get("/direction/driving", {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
        "extensions": "all",  # 🆕 返回完整 polyline + 多条备选路线
        "strategy": 10,
        "alternatives": 3,    # 🆕 最多 3 条备选方案
    })
    if not d:
        return None

    paths = d.get("route", {}).get("paths") or []
    if not paths:
        return None
    p = paths[0]

    steps = []
    for step in p.get("steps", []):
        steps.append({
            "instruction": step.get("instruction", ""),
            "road": step.get("road", ""),
            "distance_m": int(step.get("distance", 0)),
            "duration_s": int(step.get("duration", 0)),
        })

    result = {
        "mode": "驾车",
        "distance_km": round(int(p.get("distance", 0)) / 1000, 1),
        "duration_min": round(int(p.get("duration", 0)) / 60),
        "tolls_yuan": float(p.get("tolls", 0)),
        "toll_distance_km": round(int(p.get("toll_distance", 0)) / 1000, 1),
        "steps": steps,
        # 🆕 polyline 在每个 step 内部，拼起来
        "polyline": ";".join(s.get("polyline", "") for s in (p.get("steps") or []) if s.get("polyline")),
        # 🆕 备选路线（paths[1:]）
        "alternatives": [
            {
                "polyline": ";".join(s.get("polyline", "") for s in (a.get("steps") or []) if s.get("polyline")),
                "distance_km": round(int(a.get("distance", 0)) / 1000, 1),
                "duration_min": round(int(a.get("duration", 0)) / 60),
                "tolls_yuan": float(a.get("tolls", 0)),
                "strategy": a.get("strategy", ""),
            } for a in paths[1:]
        ],
    }
    _cache_set(key, result)
    return result


def transit(origin_lng: float, origin_lat: float,
            dest_lng: float, dest_lat: float,
            city1: str = "", city2: str = "") -> Optional[dict]:
    """
    高德公交/地铁路线规划（跨城时高德会自动转成高铁+公交组合）
    city1/city2 可选，跨城时建议传以提升精度
    """
    key = f"transit|{origin_lng:.3f},{origin_lat:.3f}|{dest_lng:.3f},{dest_lat:.3f}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    params = {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    }
    if city1:
        params["city"] = city1
    if city2:
        params["cityd"] = city2

    d = _api_get("/direction/transit/integrated", params)
    if not d:
        return None

    transits = d.get("route", {}).get("transits") or []
    if not transits:
        return None
    t = transits[0]

    def _to_int(v, default=0):
        if v is None: return default
        if isinstance(v, (list, dict)): return default
        try: return int(float(v))
        except: return default

    def _mode_from_bustype(type_str: str) -> str:
        """高德 busline.type → 前端 mode 标签
        地铁/轻轨 → subway；高铁/火车/动车 → rail；其余 → bus"""
        s = (type_str or "").strip()
        if "地铁" in s or "轻轨" in s:
            return "subway"
        if "高铁" in s or "火车" in s or "动车" in s:
            return "rail"
        return "bus"

    # 🆕 把 segments 拆成可读的步骤（顺序：walking → bus，每个 segment 内）
    # 同时构建 transit_segments 细分结构，供前端拆 step 画线
    steps = []
    transit_segments = []  # 🆕 结构化细分，供 _plan_local_tour 拆 step
    polyline_parts = []    # 整体 polyline 拼接

    for seg in t.get("segments", []):
        # ---- 1. walking 段（走到上车站 / 终点）----
        walking = seg.get("walking", {})
        # 🐛 高德部分响应中 walking 字段为数组（[] 或 [{}]），统一归一化为 dict
        if isinstance(walking, list):
            walking = walking[0] if walking else {}
        w_dist = _to_int(walking.get("distance"))
        w_dur = _to_int(walking.get("duration"))
        w_poly = ""
        if isinstance(walking, dict) and walking.get("path"):
            w_poly = ";".join(p.get("polyline", "") for p in walking["path"] if p.get("polyline"))
        if w_dist > 0 or w_dur > 0:
            steps.append({
                "instruction": f"步行 {w_dist}m" if w_dist else "步行前往",
                "road": "",
                "distance_m": w_dist,
                "duration_s": w_dur,
                "mode": "walk",
                "polyline": w_poly,
            })
            polyline_parts.append(w_poly)

        # ---- 2. bus 段（乘地铁/公交/高铁，可能有多个 busline）----
        bus = seg.get("bus", {})
        buslines = bus.get("buslines", []) if isinstance(bus, dict) else []
        for line in buslines:
            b_mode = _mode_from_bustype(line.get("type", ""))
            dep_stop = line.get("departure_stop", {}) or {}
            arr_stop = line.get("arrival_stop", {}) or {}
            dep_name = dep_stop.get("name", "") if isinstance(dep_stop, dict) else ""
            arr_name = arr_stop.get("name", "") if isinstance(arr_stop, dict) else ""
            line_name = line.get("name", "")
            # mode 文案：subway→乘地铁，rail→乘高铁，bus→乘公交
            mode_cn = {"subway": "乘地铁", "rail": "乘高铁", "bus": "乘公交"}.get(b_mode, "乘车")
            steps.append({
                "instruction": f"{mode_cn} {line_name} 从 {dep_name} 到 {arr_name}",
                "road": line_name,
                "distance_m": _to_int(line.get("distance")),
                "duration_s": _to_int(line.get("duration")),
                "mode": b_mode,
                "polyline": line.get("polyline", ""),
                "from_stop": dep_name,
                "to_stop": arr_name,
            })
            polyline_parts.append(line.get("polyline", ""))
            # 🆕 transit_segments 细分结构
            transit_segments.append({
                "type": b_mode,
                "mode_cn": mode_cn,
                "line_name": line_name,
                "from_stop": dep_name,
                "to_stop": arr_name,
                "distance_m": _to_int(line.get("distance")),
                "duration_s": _to_int(line.get("duration")),
                "polyline": line.get("polyline", ""),
                "walking_before": {
                    "distance_m": w_dist,
                    "duration_s": w_dur,
                    "polyline": w_poly,
                } if (w_dist > 0 or w_dur > 0) else None,
            })

    result = {
        "mode": "公交",
        "distance_km": round(_to_int(t.get("distance")) / 1000, 1),
        "duration_min": round(_to_int(t.get("duration")) / 60),
        "cost_yuan": float(t.get("cost", 0) or 0),
        "walking_distance_m": _to_int(t.get("walking_distance")),
        "steps": steps,
        # 🆕 结构化细分（保留 segment 级 walking+bus 关系）
        "transit_segments": transit_segments,
        # 🆕 整体 polyline（拼接所有段，供地图画线）
        "polyline": ";".join(p for p in polyline_parts if p),
    }
    _cache_set(key, result)
    return result


def walking(origin_lng: float, origin_lat: float,
            dest_lng: float, dest_lat: float) -> Optional[dict]:
    """高德步行路线规划"""
    key = f"walking|{origin_lng:.3f},{origin_lat:.3f}|{dest_lng:.3f},{dest_lat:.3f}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    d = _api_get("/direction/walking", {
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    })
    if not d:
        return None

    paths = d.get("route", {}).get("paths") or []
    if not paths:
        return None
    p = paths[0]

    steps = []
    for step in p.get("steps", []):
        steps.append({
            "instruction": step.get("instruction", ""),
            "road": step.get("road", ""),
            "distance_m": int(step.get("distance", 0)),
            "duration_s": int(step.get("duration", 0)),
        })

    result = {
        "mode": "步行",
        "distance_km": round(int(p.get("distance", 0)) / 1000, 2),
        "duration_min": round(int(p.get("duration", 0)) / 60),
        "steps": steps,
        "polyline": ";".join(s.get("polyline", "") for s in (p.get("steps") or []) if s.get("polyline")),
    }
    _cache_set(key, result)
    return result


# ---------------------------------------------------------------------------
# 便捷函数：跨城自动选最佳模式，同城优先公交/打车
# ---------------------------------------------------------------------------

def route_between(lng1: float, lat1: float, lng2: float, lat2: float,
                  km_fallback: float = 0,
                  city1_name: str = "", city2_name: str = "",
                  prefer: str = "auto") -> Optional[dict]:
    """
    最上层封装：按距离自动选模式
      km_fallback: 如果 > 0 说明已经知道直线距离，用来决定策略
      prefer: "driving" / "transit" / "auto"
    """
    if prefer == "driving":
        return driving(lng1, lat1, lng2, lat2)
    if prefer == "transit":
        return transit(lng1, lat1, lng2, lat2, city1_name, city2_name)

    # auto：< 10km 同城 — 公交/步行优先；10-500km — 驾车；>500km — 公交(可能含高铁)
    km = km_fallback
    if km <= 0:
        import math
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lng2 - lng1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        km = 2 * R * math.asin(math.sqrt(a))

    if km < 10:
        # 同城短途：先试驾车（打车），比公交快
        r = driving(lng1, lat1, lng2, lat2)
        return r
    elif km < 500:
        # 中距离：驾车
        return driving(lng1, lat1, lng2, lat2)
    else:
        # 远距离：试公交（可能转高铁），不行就驾车
        r = transit(lng1, lat1, lng2, lat2, city1_name, city2_name)
        if r:
            return r
        return driving(lng1, lat1, lng2, lat2)


def cache_stats() -> dict:
    """🆕 更新 stats: 显示 L1/L2 各自数量 + L2 命中"""
    l2_count = 0
    l2_expired = 0
    try:
        from app import create_app
        from app.models import AmapCache
        app = create_app()
        with app.app_context():
            rows = AmapCache.query.all()
            l2_count = len(rows)
            from datetime import datetime as _dt
            l2_expired = sum(1 for r in rows if _dt.utcnow() > r.expires_at)
    except Exception:
        pass
    return {
        "l1_entries": len(_L1),
        "l2_entries": l2_count,
        "l2_expired": l2_expired,
        "api_calls": _call_count,
        "l1_hits": _cache_hit - _l2_hit,
        "l2_hits": _l2_hit,
        "total_hits": _cache_hit,
    }


def reset_cache():
    """🆕 清 L1 + L2"""
    global _call_count, _cache_hit, _l2_hit
    with _L1_lock:
        _L1.clear()
    # 清 L2
    try:
        from app import create_app, db
        from app.models import AmapCache
        app = create_app()
        with app.app_context():
            AmapCache.query.delete()
            db.session.commit()
    except Exception:
        pass
    _call_count = 0
    _cache_hit = 0
    _l2_hit = 0


def purge_expired():
    """🆕 清理过期 L2 条目（可定时调用）"""
    try:
        from app import create_app, db
        from app.models import AmapCache
        from datetime import datetime as _dt
        app = create_app()
        with app.app_context():
            n = AmapCache.query.filter(AmapCache.expires_at < _dt.utcnow()).delete()
            db.session.commit()
            return {"purged": n}
    except Exception as e:
        return {"error": str(e)}
