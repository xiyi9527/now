"""
完整后端路由层
  - GET  /api/health         健康检查
  - POST /api/register       注册
  - POST /api/login          登录（返回 JWT）
  - GET  /api/cities         城市列表
  - GET  /api/spots          景点列表
  - GET  /api/search?q=xxx   统一搜索（城市+景点+高德POI补全）
  - POST /api/plan           核心规划接口（分段 NSGA-II）
  - POST /api/plan/save      保存规划入库
  - GET  /api/plan/me        我的规划列表
  - GET  /api/plan/public    广场公开规划
"""
import os
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
)
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import User, City, Spot, Plan, Favorite
from sqlalchemy import desc
from app.utils.plan_service import run_segmented_plan, plan_direct_by_coords


bp = Blueprint("api", __name__)

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")


# ====================================================================
# 1. 基础
# ====================================================================
@bp.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "travel_planner2"})


# ====================================================================
# 🆕 高德缓存管理
# ====================================================================
@bp.route("/amap-cache/stats", methods=["GET"])
def amap_cache_stats():
    from app.utils.amap_router import cache_stats
    return jsonify({"ok": True, "data": cache_stats()})


@bp.route("/amap-cache/reset", methods=["POST"])
def amap_cache_reset():
    from app.utils.amap_router import reset_cache
    reset_cache()
    return jsonify({"ok": True, "msg": "L1+L2 缓存已清空"})


@bp.route("/amap-cache/purge", methods=["POST"])
def amap_cache_purge():
    from app.utils.amap_router import purge_expired
    return jsonify({"ok": True, "data": purge_expired()})


# ====================================================================
# 2. 认证
# ====================================================================
@bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    email = data.get("email", "")

    if not username or not password:
        return jsonify({"ok": False, "msg": "用户名和密码不能为空"}), 400
    if len(username) < 2 or len(password) < 6:
        return jsonify({"ok": False, "msg": "用户名≥2字符，密码≥6字符"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"ok": False, "msg": "用户名已存在"}), 409

    u = User(
        username=username,
        password_hash=generate_password_hash(password, method="pbkdf2"),
        email=email or None,
    )
    db.session.add(u)
    db.session.commit()

    token = create_access_token(identity=str(u.id), additional_claims={"role": u.role or "user"})
    return jsonify({
        "ok": True,
        "user": {"id": u.id, "username": u.username, "email": u.email, "role": u.role or "user"},
        "access_token": token,
    })


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    u = User.query.filter_by(username=username).first()
    if not u or not check_password_hash(u.password_hash, password):
        return jsonify({"ok": False, "msg": "用户名或密码错误"}), 401

    token = create_access_token(identity=str(u.id), additional_claims={"role": u.role or "user"})
    return jsonify({
        "ok": True,
        "user": {"id": u.id, "username": u.username, "email": u.email, "role": u.role or "user"},
        "access_token": token,
    })


# ====================================================================
# 3. 基础数据
# ====================================================================
@bp.route("/cities", methods=["GET"])
def list_cities():
    cities = City.query.order_by(City.is_hot.desc(), City.id).all()
    return jsonify({
        "ok": True,
        "data": [{
            "id": c.id,
            "name": c.name,
            "province": c.province,
            "hub_name": c.hub_name,
            "lat": float(c.lat),
            "lng": float(c.lng),
            "is_hot": bool(c.is_hot),
        } for c in cities],
    })


@bp.route("/spots", methods=["GET"])
def list_spots():
    city_id = request.args.get("city_id", type=int)
    q = Spot.query
    if city_id:
        q = q.filter_by(city_id=city_id)
    # 有图优先（防止以后再导入无图占位数据默认展示）→ is_hot desc → city_id → id
    from sqlalchemy import case
    spots = q.join(City, Spot.city_id == City.id).order_by(
        case((db.and_(Spot.img_url.isnot(None), Spot.img_url != ""), 1), else_=0).desc(),
        City.is_hot.desc(),
        Spot.city_id,
        Spot.id,
    ).all()
    city_map = {c.id: c.name for c in City.query.all()}
    return jsonify({
        "ok": True,
        "data": [{
            "id": s.id,
            "name": s.name,
            "city_id": s.city_id,
            "city_name": city_map.get(s.city_id, ""),
            "lat": float(s.lat),
            "lng": float(s.lng),
            "description": s.description,
            "cost_time_extra": s.cost_time_extra,
            "img_url": s.img_url or "",
        } for s in spots],
    })


# ====================================================================
# 3.1 🔍 统一搜索（城市 + 景点 + 高德 POI 补全）
# ====================================================================
@bp.route("/search", methods=["GET"])
def search_places():
    """
    统一搜索入口：
    params: q=xxx 必填，limit=20 可选，city 可选（高德限定城市）
    优先级：本地精确匹配 > 本地模糊匹配 > 高德 POI 补全
    """
    q = (request.args.get("q") or "").strip()
    if not q or len(q) < 1:
        return jsonify({"ok": True, "data": []})

    limit = int(request.args.get("limit", 20))

    cities = City.query.all()
    spots = Spot.query.all()
    city_map = {c.id: c for c in cities}

    results = []

    # ---- 1. 本地精确匹配（全等于或开头） ----
    ql = q.lower()
    for c in cities:
        if ql == c.name.lower() or c.name.lower().startswith(ql):
            results.append({
                "type": "city",
                "id": f"city_{c.id}",
                "city_id": c.id,
                "name": c.name,
                "label": f"🏙️ {c.name}{' 🔥' if c.is_hot else ''}",
                "address": c.province or "",
                "lat": float(c.lat),
                "lng": float(c.lng),
                "match": "exact",
            })
    for s in spots:
        if ql == s.name.lower() or s.name.lower().startswith(ql):
            results.append({
                "type": "spot",
                "id": f"spot_{s.id}",
                "spot_id": s.id,
                "city_id": s.city_id,
                "name": s.name,
                "label": f"📍 {s.name}（景点 · {city_map.get(s.city_id).name if s.city_id in city_map else ''}）",
                "address": city_map.get(s.city_id).name if s.city_id in city_map else "",
                "lat": float(s.lat),
                "lng": float(s.lng),
                "match": "exact",
            })

    # ---- 2. 本地模糊包含匹配（去重后） ----
    seen_ids = {r["id"] for r in results}
    for c in cities:
        if f"city_{c.id}" in seen_ids:
            continue
        if ql in c.name.lower() or ql in (c.province or "").lower():
            results.append({
                "type": "city",
                "id": f"city_{c.id}",
                "city_id": c.id,
                "name": c.name,
                "label": f"🏙️ {c.name}{' 🔥' if c.is_hot else ''}",
                "address": c.province or "",
                "lat": float(c.lat),
                "lng": float(c.lng),
                "match": "fuzzy",
            })
            seen_ids.add(f"city_{c.id}")
    for s in spots:
        if f"spot_{s.id}" in seen_ids:
            continue
        if ql in s.name.lower():
            results.append({
                "type": "spot",
                "id": f"spot_{s.id}",
                "spot_id": s.id,
                "city_id": s.city_id,
                "name": s.name,
                "label": f"📍 {s.name}（景点 · {city_map.get(s.city_id).name if s.city_id in city_map else ''}）",
                "address": city_map.get(s.city_id).name if s.city_id in city_map else "",
                "lat": float(s.lat),
                "lng": float(s.lng),
                "match": "fuzzy",
            })
            seen_ids.add(f"spot_{s.id}")

    # ---- 2b. 关键词重叠匹配（如 "黄果树瀑布" 能命中 "黄果树景区"） ----
    seen_names = {r["name"] for r in results}
    def _keyword_overlap(query: str, target: str) -> bool:
        """如果 query 和 target 共享 2+ 个以上连续中文字符就视为匹配"""
        import re
        q_chars = set(re.findall(r'[\u4e00-\u9fff]{2,}', query))
        t_chars = set(re.findall(r'[\u4e00-\u9fff]{2,}', target))
        # 也试单字的重叠（≥2 个字相同）
        overlap = sum(1 for ch in query if ch in target)
        if overlap >= 2 and query[0] in target[:3]:  # 首字必须对
            return True
        return bool(q_chars & t_chars)

    for s in spots:
        if f"spot_{s.id}" in seen_ids or s.name in seen_names:
            continue
        if _keyword_overlap(q, s.name):
            results.append({
                "type": "spot",
                "id": f"spot_{s.id}",
                "spot_id": s.id,
                "city_id": s.city_id,
                "name": s.name,
                "label": f"📍 {s.name}（景点 · {city_map.get(s.city_id).name if s.city_id in city_map else ''}）",
                "address": city_map.get(s.city_id).name if s.city_id in city_map else "",
                "lat": float(s.lat),
                "lng": float(s.lng),
                "match": "fuzzy",
            })
            seen_ids.add(f"spot_{s.id}")
            seen_names.add(s.name)
    for c in cities:
        if f"city_{c.id}" in seen_ids or c.name in seen_names:
            continue
        if _keyword_overlap(q, c.name):
            results.append({
                "type": "city",
                "id": f"city_{c.id}",
                "city_id": c.id,
                "name": c.name,
                "label": f"🏙️ {c.name}{' 🔥' if c.is_hot else ''}",
                "address": c.province or "",
                "lat": float(c.lat),
                "lng": float(c.lng),
                "match": "fuzzy",
            })
            seen_ids.add(f"city_{c.id}")
            seen_names.add(c.name)

    # 本地够了就直接返回，不调高德
    if len(results) >= limit:
        return jsonify({"ok": True, "data": results[:limit], "source": "local"})

    # ---- 3. 高德 POI 补全（加 typecode 白名单过滤垃圾） ----
    try:
        import requests as req
        r = req.get("https://restapi.amap.com/v3/assistant/inputtips", params={
            "keywords": q,
            "key": AMAP_KEY,
            "datatype": "poi",
            "output": "JSON",
        }, timeout=3)
        amap = r.json()
        if amap.get("status") == "1":
            # 白名单 typecode 前缀：110=名胜景点, 100=餐饮酒店, 190=村镇街道
            KEEP_PREFIXES = ("110", "100", "190")
            added = 0
            for tip in amap.get("tips", []):
                if added >= 5: break   # 高德 POI 最多 5 条
                loc = tip.get("location", "")
                if not loc or "," not in loc: continue
                typecode = tip.get("typecode", "")
                # 过滤垃圾：typecode 可能是 "110202|110101" 多值
                keep = False
                for tc_part in typecode.split("|"):
                    if tc_part.startswith(KEEP_PREFIXES):
                        keep = True; break
                if not keep: continue   # 房地产/交通/银行等垃圾项跳过
                lng_s, lat_s = loc.split(",", 1)
                try: lng, lat = float(lng_s), float(lat_s)
                except ValueError: continue

                # 距离过滤：找最近的已知城市，如果都 > 300km 就丢掉
                import math
                def _haversine_km(lat1, lng1, lat2, lng2):
                    R = 6371.0
                    dlat = math.radians(lat2 - lat1)
                    dlng = math.radians(lng2 - lng1)
                    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
                    return 2 * R * math.asin(math.sqrt(a))
                nearest_city_km = min(_haversine_km(lat, lng, float(c.lat), float(c.lng)) for c in cities)
                if nearest_city_km > 300:
                    continue  # 坐标离所有已知城市太远，大概率是同名异地 POI

                # 名称相关性过滤：如果已有本地匹配结果，高德 POI 也得和 query 首字匹配
                if seen_ids and q and tip.get("name", "")[:2] != q[:2]:
                    continue

                name = tip.get("name", "")
                if any(name == existing["name"] for existing in results): continue
                results.append({
                    "type": "poi",
                    "id": f"poi_{lng}_{lat}",
                    "name": name,
                    "label": f"🔍 {name}（高德）",
                    "address": tip.get("address", "") or tip.get("district", ""),
                    "lat": lat, "lng": lng,
                    "match": "amap",
                })
                added += 1
    except Exception:
        pass

    return jsonify({
        "ok": True,
        "data": results[:limit],
        "source": "hybrid" if len(results) > len(seen_ids) else "local",
    })


# ---- 1.1 附近景点推荐 ----
@bp.route("/spots/recommend", methods=["GET"])
def recommend_spots():
    """
    返回起点附近 + 终点附近 + 直线附近 的推荐景点
    params: start_city_id, end_city_id, radius_km (默认 200)
    """
    import math
    start_id = request.args.get("start_city_id", type=int)
    end_id = request.args.get("end_city_id", type=int)
    radius = request.args.get("radius_km", type=int) or 200

    all_spots = Spot.query.all()
    city_map = {c.id: c for c in City.query.all()}

    def haversine(lat1, lng1, lat2, lng2):
        R = 6371.0
        p1 = math.radians(lat1); p2 = math.radians(lat2)
        dp = math.radians(lat2 - lat1); dl = math.radians(lng2 - lng1)
        a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*R*math.asin(math.sqrt(a))

    def point_to_segment_dist(px, py, ax, ay, bx, by):
        """点 (px,py) 到线段 AB 的最近距离（度为单位，近似）"""
        dx, dy = bx-ax, by-ay
        if dx == 0 and dy == 0:
            return haversine(px, py, ax, ay)
        t = ((px-ax)*dx + (py-ay)*dy) / (dx*dx + dy*dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t*dx, ay + t*dy
        return haversine(px, py, cx, cy)

    start_city = city_map.get(start_id)
    end_city = city_map.get(end_id)
    result = {"start_near": [], "end_near": [], "line_near": []}

    for s in all_spots:
        slat, slng = float(s.lat), float(s.lng)
        base = {
            "id": s.id, "name": s.name, "city_id": s.city_id,
            "city_name": city_map.get(s.city_id).name if s.city_id in city_map else "",
            "lat": slat, "lng": slng, "img_url": s.img_url or "",
            "description": s.description or "",
            "cost_time_extra": s.cost_time_extra or 120,
        }
        if start_city:
            d = haversine(float(start_city.lat), float(start_city.lng), slat, slng)
            if d <= radius:
                result["start_near"].append({**base, "distance_km": round(d, 1)})
        if end_city:
            d = haversine(float(end_city.lat), float(end_city.lng), slat, slng)
            if d <= radius:
                result["end_near"].append({**base, "distance_km": round(d, 1)})
        if start_city and end_city:
            d = point_to_segment_dist(
                slat, slng,
                float(start_city.lat), float(start_city.lng),
                float(end_city.lat),   float(end_city.lng),
            )
            if d <= radius:
                result["line_near"].append({**base, "distance_km": round(d, 1)})

    # 按距离排序
    for k in result:
        result[k].sort(key=lambda x: x["distance_km"])

    return jsonify({"ok": True, "data": result})


# ====================================================================
# 4. 核心规划接口（分段 NSGA-II）
# ====================================================================
@bp.route("/plan", methods=["POST"])
def plan():
    """
    请求 JSON
    {
        "start_id": 1,            # 必填，起点城市ID
        "end_id": 2,              # 必填，终点城市ID
        "spot_ids": [1, 3],       # 可选，景点ID列表
        "is_driving": false,       # 可选，开车模式
        "preference": {           # 可选，偏好权重（三者相加建议为1）
            "time_weight": 0.4,
            "money_weight": 0.4,
            "comfort_weight": 0.2
        },
        "pop_size": 100,          # 可选，覆盖算法参数
        "max_gen": 150
    }
    """
    data = request.get_json(force=True) or {}

    start_lat = data.get("start_lat")
    start_lng = data.get("start_lng")
    end_lat   = data.get("end_lat")
    end_lng   = data.get("end_lng")
    start_name = data.get("start_name") or "起点"
    end_name   = data.get("end_name") or "终点"
    transport_mode = data.get("transport_mode", "auto")
    spot_ids = data.get("spot_ids") or []
    start_spot_id = data.get("start_spot_id")
    end_spot_id = data.get("end_spot_id")

    # ✅ 主路径：坐标直达 → NSGA-II 候选集优化（论文 4.3 节规格）
    #    高德多模式(driving alternatives=3 + transit + walking) 构建候选集
    #    → run_nsga2_candidates (pop20/gen15/cross0.9/mut0.3) → 四类代表方案
    iteration_logs = []
    if all([start_lat, start_lng, end_lat, end_lng]):
        # 🆕 S6: 取登录用户对各交通方式的均分，传入 NSGA-II 体验惩罚修正
        mode_ratings = {}
        try:
            uid_str = get_jwt_identity()
            if uid_str:
                from app.models import Rating
                from sqlalchemy import func as _f
                rows = db.session.query(
                    Rating.mode, _f.Avg(Rating.score)
                ).filter_by(user_id=int(uid_str)).group_by(Rating.mode).all()
                mode_ratings = {row[0]: round(float(row[1]), 2) for row in rows}
        except Exception:
            pass   # 未登录或无打分记录 → 不修正

        try:
            results, iteration_logs = plan_direct_by_coords(
                start_lat=float(start_lat), start_lng=float(start_lng),
                start_name=start_name,
                end_lat=float(end_lat), end_lng=float(end_lng),
                end_name=end_name,
                mid_spot_ids=[int(s) for s in spot_ids if int(s) not in (
                    int(start_spot_id) if start_spot_id else -1,
                    int(end_spot_id) if end_spot_id else -1,
                )],
                transport_mode=transport_mode,
                mode_ratings=mode_ratings,
            )
        except Exception as e:
            return jsonify({"ok": False, "msg": f"路线计算失败: {e}"}), 500

    # fallback：只有 start_id/end_id 没经纬度（旧客户端 / 城市对模式）
    # 仍走 cost_matrix + NSGA-II 城市排列版
    else:
        start_id = data.get("start_id")
        end_id = data.get("end_id")
        if not start_id or not end_id:
            return jsonify({"ok": False, "msg": "必须提供 start_lat/start_lng/end_lat/end_lng（经纬度直达模式）"}), 400
        try:
            results = run_segmented_plan(
                start_id=int(start_id), end_id=int(end_id),
                start_spot_id=int(start_spot_id) if start_spot_id else None,
                end_spot_id=int(end_spot_id) if end_spot_id else None,
                spot_ids=[int(s) for s in spot_ids],
            )
        except KeyError as e:
            return jsonify({"ok": False, "msg": f"无效的城市ID: {e}"}), 400
        except Exception as e:
            return jsonify({"ok": False, "msg": f"算法内部错误: {e}"}), 500

    if not results:
        return jsonify({"ok": False, "msg": "当前参数下没有可行路径"}), 404

    return jsonify({
        "ok": True,
        "count": len(results),
        "options": results,
        "iteration_logs": iteration_logs,   # 🆕 S2: HV 收敛曲线 / 帕累托解数
    })


# ====================================================================
# 5. 保存规划 / 我的规划 / 广场（步骤 4 先占位，接口先打通）
# ====================================================================
@bp.route("/plan/save", methods=["POST"])
@jwt_required()
def save_plan():
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True) or {}

    from app.models import PlanStep, Solution, IterationLog

    plan = Plan(
        user_id=user_id,
        start_city_id=data.get("start_city_id") or 0,
        end_city_id=data.get("end_city_id") or 0,
        spot_ids=",".join(str(s) for s in data.get("spot_ids", [])),
        total_time=int(data["total_time"]),
        total_money=float(data["total_money"]),
        total_discomfort=float(data.get("total_discomfort", 0)),
        route_detail=data.get("route_detail", {}),
        is_public=bool(data.get("is_public", False)),
    )
    db.session.add(plan)
    db.session.flush()

    # 步骤列表（可选）
    for step in data.get("steps", []):
        ps = PlanStep(
            plan_id=plan.id,
            step_order=step.get("step_order", 0),
            mode=step.get("mode", "综合交通"),
            from_name=step.get("from_name", ""),
            to_name=step.get("to_name", ""),
            duration=int(step.get("duration", 0)),
            cost=float(step.get("cost", 0)),
            instruction=step.get("instruction", ""),
        )
        db.session.add(ps)

    # 🆕 S2: 持久化 NSGA-II 帕累托解集（solution 表）
    # 兼容 objectives 为 list [time, cost, exp] 或 dict {time,cost,experience}
    def _obj(sol, key, idx, default=0):
        obj = sol.get("objectives")
        if isinstance(obj, dict):
            return float(obj.get(key, default))
        if isinstance(obj, (list, tuple)):
            return float(obj[idx]) if len(obj) > idx else float(default)
        return float(default)

    for sol in data.get("solutions", []):
        s = Solution(
            plan_id=plan.id,
            rank=int(sol.get("rank", 0)),
            label=sol.get("label", ""),
            objectives={
                "time": _obj(sol, "time", 0),
                "cost": _obj(sol, "cost", 1),
                "experience": _obj(sol, "experience", 2),
            },
            route_order=sol.get("route_order"),
            segments=sol.get("segments"),
            elapsed=sol.get("elapsed"),
        )
        db.session.add(s)

    # 🆕 S2: 持久化 NSGA-II 每代迭代日志（iteration_log 表）
    for log in data.get("iteration_logs", []):
        il = IterationLog(
            plan_id=plan.id,
            gen=int(log.get("gen", 0)),
            hv=float(log["hv"]) if log.get("hv") is not None else None,
            pareto_count=int(log.get("pareto_count", 0)),
            best_time=float(log["best_time"]) if log.get("best_time") is not None else None,
            best_cost=float(log["best_cost"]) if log.get("best_cost") is not None else None,
        )
        db.session.add(il)

    db.session.commit()
    return jsonify({"ok": True, "plan_id": plan.id})


@bp.route("/plan/me", methods=["GET"])
@jwt_required()
def my_plans():
    user_id = int(get_jwt_identity())
    plans = Plan.query.filter_by(user_id=user_id).order_by(Plan.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "data": [_plan_short(p) for p in plans],
    })


@bp.route("/plan/public", methods=["GET"])
def public_plans():
    plans = Plan.query.filter_by(is_public=True).order_by(Plan.created_at.desc()).limit(50).all()
    return jsonify({
        "ok": True,
        "data": [_plan_short(p) for p in plans],
    })


def _plan_short(p: Plan) -> dict:
    return {
        "id": p.id,
        "start_city_id": p.start_city_id,
        "end_city_id": p.end_city_id,
        "spot_ids": [int(x) for x in (p.spot_ids or "").split(",") if x],
        "total_time": int(p.total_time),
        "total_money": float(p.total_money),
        "total_discomfort": float(p.total_discomfort) if p.total_discomfort else 0,
        "is_public": bool(p.is_public),
        "rating": int(p.rating) if p.rating else 0,
        "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
        "route_detail": p.route_detail,
    }


# ===================== 评分 =====================
@bp.route("/plan/<int:plan_id>/rate", methods=["POST"])
@jwt_required()
def rate_plan(plan_id):
    data = request.get_json(force=True) or {}
    rating = int(data.get("rating", 0))
    if not (1 <= rating <= 5):
        return jsonify({"ok": False, "msg": "评分必须 1-5"}), 400
    p = Plan.query.get_or_404(plan_id)
    p.rating = rating
    db.session.commit()
    return jsonify({"ok": True, "rating": rating})


# ===========================================================================
# 🆕 S6：交通方式打分闭环（论文 4.7 节）— -2~+2 score，反馈到 NSGA-II 体验惩罚
# ===========================================================================
@bp.route("/rate", methods=["POST"])
@jwt_required()
def submit_mode_rating():
    """提交某规划中某交通方式的打分
    body: { plan_id, mode, score(-2~+2), comment? }
    """
    from app.models import Rating
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True) or {}
    plan_id = data.get("plan_id")
    mode = (data.get("mode") or "").strip()
    score = int(data.get("score", 0))
    comment = (data.get("comment") or "").strip()

    if not plan_id or not mode:
        return jsonify({"ok": False, "msg": "plan_id 和 mode 必填"}), 400
    if not (-2 <= score <= 2):
        return jsonify({"ok": False, "msg": "score 范围 -2~+2"}), 400

    # 同一用户对同一 plan+mode 的打分，覆盖更新
    existing = Rating.query.filter_by(user_id=user_id, plan_id=plan_id, mode=mode).first()
    if existing:
        existing.score = score
        existing.comment = comment or None
    else:
        r = Rating(user_id=user_id, plan_id=plan_id, mode=mode,
                    score=score, comment=comment or None)
        db.session.add(r)
    db.session.commit()
    return jsonify({"ok": True, "data": {"mode": mode, "score": score}})


@bp.route("/rate/user-means", methods=["GET"])
def user_mode_means():
    """查当前用户对各交通方式的平均打分（供 NSGA-II 体验惩罚修正用）
    可选鉴权：未登录或 token 失效时返回空 dict，不报 422
    返回: { 驾车: 1.5, 公交: -1.0, ... }"""
    from app.models import Rating
    from sqlalchemy import func
    from flask_jwt_extended import verify_jwt_in_request

    # 可选鉴权：verify 失败不抛异常
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        if not uid:
            return jsonify({"ok": True, "data": {}})
        user_id = int(uid)
    except Exception:
        return jsonify({"ok": True, "data": {}})

    rows = db.session.query(
        Rating.mode, func.Avg(Rating.score).label("mean")
    ).filter_by(user_id=user_id).group_by(Rating.mode).all()
    means = {row[0]: round(float(row[1]), 2) for row in rows}
    return jsonify({"ok": True, "data": means})


@bp.route("/rate/plan/<int:plan_id>", methods=["GET"])
@jwt_required()
def plan_ratings(plan_id):
    """查某规划的所有打分记录"""
    from app.models import Rating
    rows = Rating.query.filter_by(plan_id=plan_id).all()
    return jsonify({"ok": True, "data": [{
        "id": r.id, "user_id": r.user_id, "mode": r.mode,
        "score": r.score, "comment": r.comment,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in rows]})


# ===================== 分享 =====================
@bp.route("/plan/<int:plan_id>/share", methods=["POST"])
@jwt_required()
def share_plan(plan_id):
    p = Plan.query.get_or_404(plan_id)
    user_id = int(get_jwt_identity())
    if p.user_id != user_id:
        return jsonify({"ok": False, "msg": "只能分享自己的规划"}), 403
    p.is_public = True
    db.session.commit()
    return jsonify({"ok": True, "msg": "已发布到广场"})


# ===================== 取消分享 =====================
@bp.route("/plan/<int:plan_id>/unshare", methods=["POST"])
@jwt_required()
def unshare_plan(plan_id):
    p = Plan.query.get_or_404(plan_id)
    p.is_public = False
    db.session.commit()
    return jsonify({"ok": True})


# ===========================================================================
# 🆕 S7：路线广场增强（论文 4.8 节）— 分享/点赞/收藏/推荐
# ===========================================================================
@bp.route("/plaza/share", methods=["POST"])
@jwt_required()
def plaza_share():
    """把规划分享到广场（创建 shared_route 记录）
    body: { plan_id, title, description, origin_name, dest_name, route_data }
    """
    from app.models import SharedRoute, Plan
    user_id = int(get_jwt_identity())
    data = request.get_json(force=True) or {}
    plan_id = data.get("plan_id")
    title = (data.get("title") or "").strip()
    if not plan_id or not title:
        return jsonify({"ok": False, "msg": "plan_id 和 title 必填"}), 400

    plan = Plan.query.get(plan_id)
    if not plan or plan.user_id != user_id:
        return jsonify({"ok": False, "msg": "只能分享自己的规划"}), 403

    route_data = data.get("route_data") or plan.route_detail or {}
    sr = SharedRoute(
        user_id=user_id,
        title=title,
        description=(data.get("description") or "").strip() or None,
        origin_name=(data.get("origin_name") or "").strip() or None,
        dest_name=(data.get("dest_name") or "").strip() or None,
        route_data=route_data,
    )
    db.session.add(sr)
    db.session.commit()
    return jsonify({"ok": True, "data": {"id": sr.id}}), 201


@bp.route("/plaza/list", methods=["GET"])
def plaza_list():
    """广场列表（推荐排序：favorites_count*2 + likes，降序）
    参数: sort=recommend|latest|hot, q=关键词
    """
    from app.models import SharedRoute
    from sqlalchemy import or_
    sort = request.args.get("sort", "recommend")
    q = (request.args.get("q") or "").strip()

    query = SharedRoute.query.filter_by(is_public=True)
    if q:
        query = query.filter(or_(
            SharedRoute.title.contains(q),
            SharedRoute.origin_name.contains(q),
            SharedRoute.dest_name.contains(q),
        ))
    if sort == "latest":
        query = query.order_by(desc(SharedRoute.created_at))
    elif sort == "hot":
        query = query.order_by(desc(SharedRoute.likes))
    else:  # recommend: 收藏×2 + 点赞
        query = query.order_by(desc(SharedRoute.favorites_count * 2 + SharedRoute.likes))

    routes = query.limit(50).all()
    return jsonify({"ok": True, "data": [{
        "id": r.id, "title": r.title, "description": r.description,
        "origin_name": r.origin_name, "dest_name": r.dest_name,
        "likes": r.likes, "favorites_count": r.favorites_count,
        "score": (r.favorites_count or 0) * 2 + (r.likes or 0),
        "username": r.user.username if r.user else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    } for r in routes]})


@bp.route("/plaza/<int:sid>", methods=["GET"])
def plaza_detail(sid):
    """广场路线详情（含 route_data）"""
    from app.models import SharedRoute
    r = SharedRoute.query.get(sid)
    if not r:
        return jsonify({"ok": False, "msg": "路线不存在"}), 404
    return jsonify({"ok": True, "data": {
        "id": r.id, "title": r.title, "description": r.description,
        "origin_name": r.origin_name, "dest_name": r.dest_name,
        "likes": r.likes, "favorites_count": r.favorites_count,
        "route_data": r.route_data,
        "username": r.user.username if r.user else None,
        "user_id": r.user_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }})


@bp.route("/plaza/<int:sid>/like", methods=["POST"])
@jwt_required()
def plaza_like(sid):
    """点赞（每次 +1，简单计数，不做去重）"""
    from app.models import SharedRoute
    r = SharedRoute.query.get_or_404(sid)
    r.likes = (r.likes or 0) + 1
    db.session.commit()
    return jsonify({"ok": True, "likes": r.likes})


@bp.route("/plaza/<int:sid>/favorite", methods=["POST"])
@jwt_required()
def plaza_favorite(sid):
    """收藏路线（幂等，已收藏则取消）"""
    from app.models import SharedRoute, UserFavorite
    user_id = int(get_jwt_identity())
    r = SharedRoute.query.get_or_404(sid)
    existing = UserFavorite.query.filter_by(user_id=user_id, shared_route_id=sid).first()
    if existing:
        db.session.delete(existing)
        r.favorites_count = max(0, (r.favorites_count or 0) - 1)
        db.session.commit()
        return jsonify({"ok": True, "favorited": False, "favorites_count": r.favorites_count})
    f = UserFavorite(user_id=user_id, shared_route_id=sid)
    db.session.add(f)
    r.favorites_count = (r.favorites_count or 0) + 1
    db.session.commit()
    return jsonify({"ok": True, "favorited": True, "favorites_count": r.favorites_count})


@bp.route("/plaza/favorites/check/<int:sid>", methods=["GET"])
@jwt_required()
def plaza_fav_check(sid):
    """检查当前用户是否已收藏某路线"""
    from app.models import UserFavorite
    user_id = int(get_jwt_identity())
    f = UserFavorite.query.filter_by(user_id=user_id, shared_route_id=sid).first()
    return jsonify({"ok": True, "favorited": bool(f)})


@bp.route("/plaza/<int:sid>/apply", methods=["POST"])
@jwt_required()
def plaza_apply(sid):
    """一键应用：把广场路线复制为自己的规划
    body: 可选 { title }
    """
    from app.models import SharedRoute, Plan
    user_id = int(get_jwt_identity())
    r = SharedRoute.query.get_or_404(sid)
    data = request.get_json(silent=True) or {}

    rd = r.route_data or {}
    plan = Plan(
        user_id=user_id,
        start_city_id=int(rd.get("start_city_id", 0)) or 0,
        end_city_id=int(rd.get("end_city_id", 0)) or 0,
        spot_ids=",".join(str(x) for x in rd.get("spot_ids", [])),
        total_time=int(rd.get("total_time", 0)),
        total_money=float(rd.get("total_money", 0)),
        total_discomfort=float(rd.get("total_discomfort", 0)),
        route_detail=rd,
        is_public=False,
    )
    db.session.add(plan)
    db.session.commit()
    return jsonify({"ok": True, "data": {"plan_id": plan.id}}), 201


# ===================== 收藏 =====================
@bp.route("/favorites", methods=["GET"])
@jwt_required()
def list_favorites():
    user_id = int(get_jwt_identity())
    favs = db.session.query(Favorite, Plan).filter(
        Favorite.user_id == user_id,
        Plan.id == Favorite.plan_id,
    ).order_by(Favorite.created_at.desc()).all()
    return jsonify({
        "ok": True,
        "data": [_plan_short(p) for _, p in favs],
    })


@bp.route("/favorites", methods=["POST"])
@jwt_required()
def add_favorite():
    data = request.get_json(force=True) or {}
    plan_id = data.get("plan_id")
    if not plan_id:
        return jsonify({"ok": False, "msg": "plan_id 必填"}), 400
    user_id = int(get_jwt_identity())
    exist = Favorite.query.filter_by(user_id=user_id, plan_id=plan_id).first()
    if exist:
        return jsonify({"ok": False, "msg": "已收藏"}), 409
    db.session.add(Favorite(user_id=user_id, plan_id=plan_id))
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/favorites/<int:plan_id>", methods=["DELETE"])
@jwt_required()
def remove_favorite(plan_id):
    user_id = int(get_jwt_identity())
    fav = Favorite.query.filter_by(user_id=user_id, plan_id=plan_id).first()
    if fav:
        db.session.delete(fav)
        db.session.commit()
    return jsonify({"ok": True})


@bp.route("/favorites/check/<int:plan_id>", methods=["GET"])
@jwt_required()
def check_favorite(plan_id):
    user_id = int(get_jwt_identity())
    fav = Favorite.query.filter_by(user_id=user_id, plan_id=plan_id).first()
    return jsonify({"ok": True, "favorited": fav is not None})
