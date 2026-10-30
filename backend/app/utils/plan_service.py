"""
API 辅助函数
- 把 Individual 的目标值/路径转换成前端能用的 dict
- 处理分段景点的 Spot 时间加成
- 聚类 Pareto 解选差异化代表（避免 60 个相似方案堆在一起）
- 🆕 候选集版 NSGA-II（论文 4.3 节）：高德多模式取候选集 → NSGA-II 优化 → 四类代表方案
"""
from app.algorithms.nsga2 import (
    run_nsga2,
    run_nsga2_candidates,
    extract_representative_solutions,
)
from app.utils.data_loader import DataLoader
from app.models import City, Spot
import numpy as np

# ---- 缓存 Spot city_id + cost_time_extra，避免每次查库 --------------------
_spot_cache = {}   # spot_id -> {city_id, cost_time_extra, name}


# ===========================================================================
# 🆕 S3：体验惩罚公式（论文 4.3.1 节）
#   discomfort = 时间归一化(0-40) + 交通舒适度 + 换乘惩罚(8/次) + 用户打分修正(±40)
# ===========================================================================

# 交通舒适度系数表（越小越舒适，论文：高铁 0 / 公交 10）
MODE_COMFORT = {
    "高铁": 0,
    "飞机": 1,
    "火车": 2,
    "大巴": 4,         # 🆕 长途客运（介于火车与驾车之间）
    "地铁": 3,
    "驾车": 5,
    "驾车(备选)": 5,   # 备选路线也是驾车
    "打车": 6,
    "公交": 10,
    "骑行": 12,
    "步行": 15,
    "估算": 8,         # 兜底
}


def compute_discomfort(mode, n_transfers=0, time_norm=None, user_rating=0):
    """论文 4.3.1 节体验惩罚公式。

    discomfort = 时间归一化(0-40) + 交通舒适度 + 换乘惩罚(8/次) + 用户打分修正(±40)

    参数
    ----
    mode: 交通方式（查 MODE_COMFORT）
    n_transfers: 换乘次数（每次 +8）
    time_norm: 该段在候选集中的时间归一化值（最快 0，最慢 40）；
               None 表示尚未做归一化，该项按 0 计
    user_rating: 用户对该交通方式的历史打分（-2 ~ +2，0 中性）
                 +2 → -40（喜欢，降低惩罚）
                 -2 → +40（不喜欢，增加惩罚）
                 即 rating * 20 取负
    """
    comfort = MODE_COMFORT.get(mode, 8)
    transfer_penalty = n_transfers * 8
    time_component = time_norm if time_norm is not None else 0.0
    # 用户打分修正：rating=+2 → -40，rating=-2 → +40
    rating_correction = -user_rating * 20
    return round(time_component + comfort + transfer_penalty + rating_correction, 2)


def _apply_time_normalization(segments):
    """对每段候选集做时间归一化（最快 0，最慢 40），并加到 discomfort 上。

    在 build_segment_candidates 末尾调用：单段候选之间时间归一，
    使"快但贵"和"慢但便宜"的方案在不适感维度上有差异。
    """
    for candidates in segments:
        if not candidates:
            continue
        times = [c.get("time", 0) for c in candidates]
        t_min, t_max = min(times), max(times)
        for c in candidates:
            if t_max > t_min:
                c["time_norm"] = round((c["time"] - t_min) / (t_max - t_min) * 40, 2)
            else:
                c["time_norm"] = 0.0
            # 重新计算 discomfort = base + time_norm + rating_correction（rating=0 阶段）
            c["discomfort"] = round(
                c.get("_base_discomfort", 0) + c["time_norm"], 2
            )
    return segments


def _apply_user_rating_correction(segments, mode_ratings):
    """S6 用户打分修正：对每个候选按其交通方式的用户历史打分调整 discomfort。
    mode_ratings: dict mode -> rating(-2~+2)
    S3 阶段 mode_ratings 为空，此函数留作 S6 钩子。
    """
    if not mode_ratings:
        return segments
    for candidates in segments:
        for c in candidates:
            mode = c.get("mode", "")
            rating = mode_ratings.get(mode, 0)
            if rating != 0:
                # rating=+2 → -40，rating=-2 → +40
                c["discomfort"] = round(c.get("discomfort", 0) + (-rating * 20), 2)
    return segments


def _ensure_spot_cache():
    if _spot_cache:
        return
    for s in Spot.query.all():
        _spot_cache[s.id] = {
            "city_id": s.city_id,
            "cost_time_extra": s.cost_time_extra or 120,
            "name": s.name,
        }


def spot_city_id(spot_id: int) -> int:
    _ensure_spot_cache()
    return _spot_cache.get(spot_id, {}).get("city_id")


def spot_time_bonus(spot_id: int) -> int:
    _ensure_spot_cache()
    return _spot_cache.get(spot_id, {}).get("cost_time_extra", 120)


# ---------------------------------------------------------------------------
# 同城玩法：start==end，直接串起多个同城景点，每段用 cost_matrix 真实数据
# ---------------------------------------------------------------------------
def _plan_local_tour(city_id: int, spot_ids: list,
                     start_spot_id: int = None, end_spot_id: int = None,
                     loader=None) -> list:
    """
    同城玩法重写：
    - 如果指定了 start_spot_id / end_spot_id → 点对点（A → B，中间可选加其他 spot）
    - 否则 → 中心出发环形（center → spots → center），给多种排序方案
    - 不走自回边（去掉 "景点→景点" 的游览 step）
    - 枚举 3-5 种不同排序，返回多个方案
    """
    from app.utils.amap_router import driving as amap_drive

    if loader is None:
        loader = DataLoader().load()
    city_info = loader.city_coord.get(city_id)
    if not city_info:
        return _fallback_nsga2_same_city(city_id, spot_ids)

    center_lat, center_lng = city_info

    # 准备 spot 字典
    all_spots = {}
    for sid in spot_ids:
        s = loader.spot_cache.get(sid)
        if s and s.get("city_id") == city_id:
            all_spots[sid] = {
                "id": sid, "name": s["name"],
                "lat": s["lat"], "lng": s["lng"],
                "time_bonus": s.get("cost_time_extra", 120),
            }

    # 如果指定了 start/end spot，且它们在 spot_ids 里
    start_spot = all_spots.get(start_spot_id) if start_spot_id else None
    end_spot = all_spots.get(end_spot_id) if end_spot_id else None

    # 中间点（排除 start/end spot）
    middle_spots = []
    for sid, sp in all_spots.items():
        if sid == start_spot_id or sid == end_spot_id:
            continue
        middle_spots.append(sp)

    def _get_drive(from_lat, from_lng, to_lat, to_lng):
        r = amap_drive(from_lng, from_lat, to_lng, to_lat)
        if r:
            # 高德原始 steps: [{instruction, road, distance_m, duration_s}, ...]
            # 简化版方便前端直接展示：格式化距离/时间
            simplified = []
            for s in r.get("steps", []):
                dist_m = s.get("distance_m", 0)
                dur_s = s.get("duration_s", 0)
                dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km"
                dur_str = f"{dur_s}s" if dur_s < 60 else f"{dur_s//60}min"
                simplified.append({
                    "instruction": s.get("instruction", ""),
                    "road": s.get("road", ""),
                    "distance_str": dist_str,
                    "duration_str": dur_str,
                    "distance_m": dist_m,
                    "duration_s": dur_s,
                })
            return {
                "distance_km": r["distance_km"],
                "duration_min": r["duration_min"],
                "tolls_yuan": r["tolls_yuan"],
                "road_cost": round(r["distance_km"] * 1.5 + r["tolls_yuan"], 1),
                "steps": r["steps"],
                "amap_steps": simplified,   # 🆕 格式化后的逐步导航指令
                "polyline": r.get("polyline", ""),
            }
        km = _haversine(from_lat, from_lng, to_lat, to_lng)
        return {
            "distance_km": round(km, 1),
            "duration_min": max(1, int(km * 1.3)),
            "tolls_yuan": 0,
            "road_cost": round(13 + km * 2.0, 1),
            "steps": [],
            "amap_steps": [],
            "polyline": "",
        }

    def _build_route(order, start_point, end_point, include_return=False):
        """
        根据排好序的 spot 列表生成完整路线
        order: [spot, spot, ...] 要经过的景点（不含 start_point/end_point 本身如果它们是 spot 的话）
        start_point: {"lat","lng","name"} 起点
        end_point: {"lat","lng","name"} 终点（如果 include_return 则回起点而不是 end_point）
        """
        pts = [start_point] + order
        if include_return:
            pts.append(start_point)
        else:
            pts.append(end_point)

        steps = []
        total_time = 0
        total_money = 0.0
        total_dis = 0.0
        step_order = 0
        cur_lat, cur_lng = pts[0]["lat"], pts[0]["lng"]

        for i in range(1, len(pts)):
            p = pts[i]
            drive = _get_drive(cur_lat, cur_lng, p["lat"], p["lng"])
            total_time += drive["duration_min"]
            total_money += drive["road_cost"]
            total_dis += round(drive["distance_km"] * 0.025, 2)
            step_order += 1

            road_detail = ""
            if drive["steps"]:
                first = drive["steps"][0]
                road_detail = f"，起步 {first['instruction'][:30]}"
            toll_note = f"，过路费 ¥{drive['tolls_yuan']}" if drive["tolls_yuan"] > 0 else ""

            # 到达终点前一个景点后加游览时间（不加单独 step，加在 instruction 里）
            extra_time = ""
            extra_instr = ""
            if p.get("time_bonus"):
                extra_time = f"（含游览 {p['time_bonus']} 分钟）"
                extra_instr = f" 到达 {p['name']} 后建议浏览拍照，约 {p['time_bonus']} 分钟。"
                total_time += p["time_bonus"]

            # 如果是 end_point 且用户指定了终点 spot，不加游览时间（终点是"目的地"，不是"要逛的景点"）
            if p == end_point and end_point.get("_is_user_end"):
                extra_time = ""
                extra_instr = ""
                total_time -= p.get("time_bonus", 0)

            from_label = "起点" if i == 1 else "上一地点"
            instruction = (
                f"从 {from_label} 出发，驾车前往 {p['name']}{extra_time}，"
                f"全程约 {drive['distance_km']} 公里，预计耗时 {drive['duration_min']} 分钟"
                f"{toll_note}{road_detail}。{extra_instr}"
            )

            steps.append({
                "step_order": step_order,
                "mode": "同城驾车",
                "from_name": from_label,
                "to_name": p["name"],
                "from_lng": cur_lng, "from_lat": cur_lat,
                "to_lng": p["lng"], "to_lat": p["lat"],
                "duration": drive["duration_min"],
                "cost": drive["road_cost"],
                "distance_km": drive["distance_km"],
                "tolls_yuan": drive["tolls_yuan"],
                "instruction": instruction,
                "polyline": drive.get("polyline", ""),
                "amap_steps": drive.get("amap_steps", []),  # 🆕 高德逐步导航指令
            })
            cur_lat, cur_lng = p["lat"], p["lng"]

        # route coords for map
        route_coords = [[start_point["lng"], start_point["lat"]]]
        for sp in order:
            route_coords.append([sp["lng"], sp["lat"]])
        if include_return:
            route_coords.append([start_point["lng"], start_point["lat"]])
        else:
            route_coords.append([end_point["lng"], end_point["lat"]])

        return {
            "total_time": total_time,
            "total_money": int(total_money),
            "total_discomfort": total_dis,
            "spot_ids": spot_ids,
            "route_coords": route_coords,
            "steps": steps,
        }

    # ============= 策略 A: 用户明确指定了 start spot 和 end spot =============
    if start_spot and end_spot:
        results = []
        start_point = {"lat": start_spot["lat"], "lng": start_spot["lng"], "name": start_spot["name"]}
        end_point = {"lat": end_spot["lat"], "lng": end_spot["lng"], "name": end_spot["name"], "_is_user_end": True}

        # 把 start/end spot 也当成"要经过的点"（中间点里如果包含它们要排除）
        # 中间点是除了 start/end 之外的 spot_ids
        mid_spots = []
        for sid, sp in all_spots.items():
            if sid not in (start_spot_id, end_spot_id):
                mid_spots.append(sp)

        # 枚举不同的中间点排序（贪心 + 反序 + 随机）
        # 排序策略：从 start spot 开始最近邻 → end spot
        def _greedy_mid(start_p, end_p, mids):
            """从 start_p 出发，每次去最近的 mid spot，最后去 end_p"""
            ordered = []
            remaining = mids[:]
            cur_lat, cur_lng = start_p["lat"], start_p["lng"]
            # 最近邻但不超过 3 个中间点（太多会让方案爆炸）
            while remaining and len(ordered) < 3:
                nearest = min(remaining, key=lambda s: _haversine(cur_lat, cur_lng, s["lat"], s["lng"]))
                # 如果最近的比直接去 end 还远很多，就不加了
                d_direct = _haversine(cur_lat, cur_lng, end_p["lat"], end_p["lng"])
                d_nearest = _haversine(cur_lat, cur_lng, nearest["lat"], nearest["lng"])
                if d_nearest > d_direct * 1.2:
                    break
                ordered.append(nearest)
                remaining.remove(nearest)
                cur_lat, cur_lng = nearest["lat"], nearest["lng"]
            return ordered

        # 方案 1: 点对点直达（start → end，无中间点）
        results.append(_build_route([], start_point, end_point))

        # 方案 2: 贪心加中间点
        greedy_order = _greedy_mid(start_point, end_point, mid_spots)
        if greedy_order:
            results.append(_build_route(greedy_order, start_point, end_point))

        # 方案 3: 反序贪心（从 end 往 start 反推，再反过来）
        def _greedy_mid_reverse(start_p, end_p, mids):
            """从 end_p 往 start_p 贪心，得到反序，再反过来"""
            ordered_rev = []
            remaining = mids[:]
            cur_lat, cur_lng = end_p["lat"], end_p["lng"]
            while remaining and len(ordered_rev) < 3:
                nearest = min(remaining, key=lambda s: _haversine(cur_lat, cur_lng, s["lat"], s["lng"]))
                ordered_rev.append(nearest)
                remaining.remove(nearest)
                cur_lat, cur_lng = nearest["lat"], nearest["lng"]
            return list(reversed(ordered_rev))

        rev_order = _greedy_mid_reverse(start_point, end_point, mid_spots)
        if rev_order and rev_order != greedy_order:
            results.append(_build_route(rev_order, start_point, end_point))

        # 方案 4: 随机打散中间点（如果有 2+ 个中间点）
        import random
        if len(mid_spots) >= 2:
            for _ in range(3):
                shuffled = mid_spots[:]
                random.shuffle(shuffled)
                r = _build_route(shuffled, start_point, end_point)
                # 只加明显不同的（时间差 > 5min）
                if all(abs(r["total_time"] - existing["total_time"]) > 5 for existing in results):
                    results.append(r)
                if len(results) >= 5:
                    break

        # 去重（按 total_time 近似）
        unique = []
        for r in results:
            if not any(abs(r["total_time"] - u["total_time"]) < 3 for u in unique):
                unique.append(r)

        return unique[:5]

    # ============= 策略 B: 无明确 start/end spot → 中心出发环形 =============
    # 从 center 出发，逛完所有 spot，回 center。枚举不同排序。
    center_point = {"lat": center_lat, "lng": center_lng, "name": "市中心"}
    spot_list = list(all_spots.values())

    if not spot_list:
        return _fallback_nsga2_same_city(city_id, spot_ids)

    results = []

    # 贪心：从 center 出发，每次去最近未访问 spot，最后回 center
    def _nearest_neighbor(start_lat, start_lng, spots):
        ordered = []
        remaining = spots[:]
        cur_lat, cur_lng = start_lat, start_lng
        while remaining:
            nearest = min(remaining, key=lambda s: _haversine(cur_lat, cur_lng, s["lat"], s["lng"]))
            ordered.append(nearest)
            remaining.remove(nearest)
            cur_lat, cur_lng = nearest["lat"], nearest["lng"]
        return ordered

    # 方案 1: 最近邻贪心
    nn_order = _nearest_neighbor(center_lat, center_lng, spot_list)
    results.append(_build_route(nn_order, center_point, center_point, include_return=True))

    # 方案 2: 反序（从最远的 spot 开始）
    farthest = max(spot_list, key=lambda s: _haversine(center_lat, center_lng, s["lat"], s["lng"]))
    rev_order = _nearest_neighbor(farthest["lat"], farthest["lng"], [s for s in spot_list if s["id"] != farthest["id"]])
    full_rev = [farthest] + rev_order
    if full_rev != nn_order:
        results.append(_build_route(full_rev, center_point, center_point, include_return=True))

    # 方案 3 & 4: 随机打散
    import random
    for _ in range(5):
        shuffled = spot_list[:]
        random.shuffle(shuffled)
        r = _build_route(shuffled, center_point, center_point, include_return=True)
        if all(abs(r["total_time"] - existing["total_time"]) > 5 for existing in results):
            results.append(r)
        if len(results) >= 5:
            break

    # 去重
    unique = []
    for r in results:
        if not any(abs(r["total_time"] - u["total_time"]) < 3 for u in unique):
            unique.append(r)

    return unique[:5]


# ---------------------------------------------------------------------------
# 🆕 候选集构建（论文 4.3.2 节：高德多模式备选路线构成候选集）
# ---------------------------------------------------------------------------
def _polyline_to_coords(pl_str):
    """高德 polyline: 'lng1,lat1;lng2,lat2;...' → [[lng,lat],...]"""
    if not pl_str:
        return []
    coords = []
    for seg in pl_str.split(";"):
        for pair in seg.split("|"):
            parts = pair.split(",")
            if len(parts) == 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    pass
    return coords


def _simplify_steps(steps_raw):
    """把高德原始 steps 格式化成前端友好的逐步导航指令。"""
    out = []
    for s in (steps_raw or []):
        dist_m = s.get("distance_m", 0)
        dur_s = s.get("duration_s", 0)
        out.append({
            "instruction": s.get("instruction", ""),
            "road": s.get("road", ""),
            "distance_str": f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km",
            "duration_str": f"{dur_s}s" if dur_s < 60 else f"{dur_s//60}min",
            "distance_m": dist_m,
            "duration_s": dur_s,
        })
    return out


def _make_estimated_candidate(mode_label, distance_km, time_min, money,
                                f_pt, t_pt, n_transfers=0):
    """构造估算候选（飞机/高铁/大巴/打车无真实导航数据，基于距离+时间估算）。
    论文 4.3.2 节：高德无 API 的交通方式按典型参数估算加入候选集。
    附 display_steps 时间轴数据：起→交通方式标签→终（前端展示用，仿高德多模式时间轴）"""
    base = compute_discomfort(mode_label, n_transfers=n_transfers, time_norm=None, user_rating=0)
    time_str = f"{int(time_min)//60}小时{int(time_min)%60}分" if time_min >= 60 else f"{int(time_min)}分钟"
    dist_str = f"{distance_km:.0f}公里"
    # 时间轴展示数据（仿图片高德样式：起点圆+交通段标签+终点圆）
    display_steps = [
        {
            "type": "origin",
            "marker": "起",
            "name": f_pt["name"],
            "lat": f_pt["lat"], "lng": f_pt["lng"],
        },
        {
            "type": "transit",
            "mode": mode_label,
            "time_str": time_str,
            "money_str": f"¥{money:.0f}",
            "dist_str": dist_str,
            "n_transfers": n_transfers,
            "note": "估算方案 · 地图显示为直线" if mode_label in ("飞机", "高铁", "大巴") else "估算方案",
        },
        {
            "type": "destination",
            "marker": "终",
            "name": t_pt["name"],
            "lat": t_pt["lat"], "lng": t_pt["lng"],
        },
    ]
    return {
        "time": int(time_min),
        "money": float(money),
        "discomfort": base,
        "_base_discomfort": base,
        "_n_transfers": n_transfers,
        "mode": mode_label,
        "steps": [],                 # 估算模式无 step 级导航
        "amap_steps": [],
        "display_steps": display_steps,   # 🆕 时间轴展示数据
        "polyline": "",
        "route_coords": [[f_pt["lng"], f_pt["lat"]], [t_pt["lng"], t_pt["lat"]]],
        "distance_km": round(distance_km, 1),
        "tolls_yuan": 0,
        "from_name": f_pt["name"],
        "to_name": t_pt["name"],
        "_estimated": True,          # 标记为估算（前端可显示"估算"标签）
    }


def _make_candidate(amap_result, mode_label, f_pt, t_pt, is_alt=False):
    """把高德返回的路线结果统一成候选 dict（论文候选集元素）。
    is_alt=True 表示这是 driving 返回的 alternative 备选路线（不带 steps，只有 polyline）。"""
    distance_km = amap_result.get("distance_km", 0) or 0
    duration_min = amap_result.get("duration_min", 0) or 0
    tolls_yuan = amap_result.get("tolls_yuan", 0) or 0
    polyline = amap_result.get("polyline", "") or ""
    steps_raw = amap_result.get("steps", []) if not is_alt else []

    # 🆕 S3: 费用 + 基础不适感（论文 4.3.1 节）
    #   基础不适感 = 交通舒适度 + 换乘惩罚（不含时间归一化和用户打分修正，
    #   这两项由 _apply_time_normalization / _apply_user_rating_correction 后处理）
    if mode_label.startswith("驾车"):
        money = round(distance_km * 1.5 + tolls_yuan, 1)
        n_transfers = 0
    elif mode_label == "公交":
        money = amap_result.get("cost_yuan", 0) or round(distance_km * 0.4, 1)
        # 公交换乘次数：高德 steps 里出现 "乘坐" 的次数 - 1（首乘不算换乘）
        n_transfers = max(0, sum(1 for s in steps_raw if "乘坐" in s.get("instruction", "")) - 1)
    else:  # 步行
        money = 0.0
        n_transfers = 0

    base_discomfort = compute_discomfort(
        mode_label, n_transfers=n_transfers, time_norm=None, user_rating=0,
    )

    return {
        "time": duration_min,
        "money": money,
        "discomfort": base_discomfort,            # 后处理会加 time_norm
        "_base_discomfort": base_discomfort,       # 基础值（舒适度 + 换乘惩罚）
        "_n_transfers": n_transfers,               # 调试用
        "mode": mode_label,
        "steps": steps_raw,
        "amap_steps": _simplify_steps(steps_raw),
        "polyline": polyline,
        "route_coords": _polyline_to_coords(polyline) or [
            [f_pt["lng"], f_pt["lat"]], [t_pt["lng"], t_pt["lat"]]
        ],
        "distance_km": distance_km,
        "tolls_yuan": tolls_yuan,
        "from_name": f_pt["name"],
        "to_name": t_pt["name"],
        # 🆕 公交候选：保留细分 segments（walking+bus），供 _format_nsga2_solution 拆多 step
        "transit_segments": amap_result.get("transit_segments", []) if mode_label == "公交" else [],
    }


# ===========================================================================
# 🆕 S9：导航一致性 — 偏好→方案→导航全链路统一解析
# 论文 4.3.2 节
# 用户逻辑（用户反馈修正）：
#   - driving/transit/walking 锁定单模式（用户明确意图）
#   - auto（智能）= 所有交通方式都作为候选，让 NSGA-II 通过不适感目标
#     自然淘汰不合理方案（如跨城步行时间过长→不适感高→被支配）
# ===========================================================================
def _resolveAmapMode(distance_km, preference="auto"):
    """返回本段应启用的交通模式集合。
    返回: set，元素 ∈ {"driving", "transit", "walking"}
    """
    if preference == "driving":
        return {"driving"}
    if preference == "transit":
        return {"transit"}
    if preference == "walking":
        return {"walking"}

    # auto（智能）：公交+步行（真实导航）+打车/大巴/高铁/飞机（估算）
    # 不含驾车（用户无车，驾车单独走 driving 模式）
    return {"transit", "walking"}


def _build_segment_candidate_list(f_pt, t_pt, transport_mode="auto"):
    """为一段 (f_pt → t_pt) 构建候选列表（论文：高德多模式备选路线）。
    S9: 用 _resolveAmapMode 统一决定本段启用哪些模式，保证偏好→候选→导航一致。"""
    from app.utils.amap_router import (
        driving as amap_drive,
        transit as amap_transit,
        walking as amap_walk,
    )

    candidates = []

    # 🆕 S9: 用 _resolveAmapMode 统一决定本段启用的模式（偏好+距离）
    dist_km = _haversine(f_pt["lat"], f_pt["lng"], t_pt["lat"], t_pt["lng"])
    enabled = _resolveAmapMode(dist_km, transport_mode)

    # ---- 驾车（仅 driving 模式启用；智能模式不含驾车，因用户无车）----
    if "driving" in enabled:
        drive = amap_drive(f_pt["lng"], f_pt["lat"], t_pt["lng"], t_pt["lat"])
        if drive:
            candidates.append(_make_candidate(drive, "驾车", f_pt, t_pt, is_alt=False))
            for alt in drive.get("alternatives", [])[:2]:
                candidates.append(_make_candidate(alt, "驾车(备选)", f_pt, t_pt, is_alt=True))

    # ---- 公交 / 地铁 / 高铁（真实导航）----
    if "transit" in enabled:
        tr = amap_transit(f_pt["lng"], f_pt["lat"], t_pt["lng"], t_pt["lat"], "", "")
        if tr:
            candidates.append(_make_candidate(tr, "公交", f_pt, t_pt, is_alt=False))

    # ---- 步行（真实导航，auto 模式下 >200km 跳过 API 调用）----
    if "walking" in enabled:
        walk_dist = _haversine(f_pt["lat"], f_pt["lng"], t_pt["lat"], t_pt["lng"])
        if walk_dist <= 200:
            wk = amap_walk(f_pt["lng"], f_pt["lat"], t_pt["lng"], t_pt["lat"])
            if wk:
                candidates.append(_make_candidate(wk, "步行", f_pt, t_pt, is_alt=False))

    # =========================================================================
    # 🆕 智能模式专属估算候选（论文 4.3.2 节）
    #   打车/大巴/高铁/飞机 高德无 API，基于直线距离×1.3 估算（驾车实际比直线长约30%）
    #   ⚠️ 路线/距离/时间/费用均为估算，无真实导航 polyline，地图只显示直线
    # =========================================================================
    if transport_mode == "auto":
        # 估算驾车距离 = 直线距离 × 1.3（经验系数，城市道路弯曲度）
        est_drive_km = dist_km * 1.3

        # ---- 打车（出租车型）----
        if est_drive_km > 0:
            taxi_time = int(est_drive_km * 1.5)  # 城市均速约 40km/h=1.5min/km
            taxi_money = round(13 + max(0, est_drive_km - 3) * 2.5, 1)
            candidates.append(_make_estimated_candidate(
                "打车", est_drive_km, taxi_time, taxi_money,
                f_pt, t_pt, n_transfers=0,
            ))

        # ---- 大巴（长途客运）----
        if est_drive_km > 0:
            bus_time = int(est_drive_km * 1.6)  # 大巴均速约 40km/h + 城市停靠
            bus_money = round(est_drive_km * 0.4, 1)
            candidates.append(_make_estimated_candidate(
                "大巴", est_drive_km, bus_time, bus_money,
                f_pt, t_pt, n_transfers=0,
            ))

        # ---- 飞机（仅 >300km 跨城才有意义）----
        if dist_km > 300:
            fly_time = int(dist_km / 12 + 120)   # 700km/h + 2h 机场
            fly_money = round(dist_km * 1.2 + 200, 1)
            candidates.append(_make_estimated_candidate(
                "飞机", dist_km, fly_time, fly_money,
                f_pt, t_pt, n_transfers=2,
            ))

        # ---- 高铁（仅 >200km 跨城才有意义）----
        if dist_km > 200:
            train_time = int(dist_km / 4 + 60)   # 250-350km/h + 1h 车站
            train_money = round(dist_km * 0.55, 1)
            candidates.append(_make_estimated_candidate(
                "高铁", dist_km, train_time, train_money,
                f_pt, t_pt, n_transfers=2,
            ))

    # 兜底：什么都没拿到时用 Haversine 估一个候选
    if not candidates:
        km = _haversine(f_pt["lat"], f_pt["lng"], t_pt["lat"], t_pt["lng"])
        base = compute_discomfort("估算", n_transfers=0, time_norm=None, user_rating=0)
        candidates.append({
            "time": max(1, int(km * 1.3)),
            "money": round(13 + km * 2.0, 1),
            "discomfort": base,
            "_base_discomfort": base,
            "_n_transfers": 0,
            "mode": "估算",
            "steps": [], "amap_steps": [], "polyline": "",
            "route_coords": [[f_pt["lng"], f_pt["lat"]], [t_pt["lng"], t_pt["lat"]]],
            "distance_km": round(km, 1), "tolls_yuan": 0,
            "from_name": f_pt["name"], "to_name": t_pt["name"],
        })

    return candidates


def build_segment_candidates(start_lat, start_lng, start_name,
                             end_lat, end_lng, end_name,
                             mid_spot_ids=None, loader=None,
                             transport_mode="auto"):
    """构建分段候选集（论文 4.3.2 节）。
    返回 (segments, mid_points)：
      segments: List[List[dict]] 每段一个候选列表
      mid_points: List[dict] 中间景点信息（含 time_bonus）"""
    if loader is None:
        loader = DataLoader().load()
    _ensure_spot_cache()

    mid_points = []
    for sid in (mid_spot_ids or []):
        s = loader.spot_cache.get(sid)
        if s:
            mid_points.append({
                "id": sid, "name": s["name"],
                "lat": s["lat"], "lng": s["lng"],
                "time_bonus": s.get("cost_time_extra", 120),
            })

    pts = ([{"lat": float(start_lat), "lng": float(start_lng), "name": start_name}]
           + mid_points
           + [{"lat": float(end_lat), "lng": float(end_lng),
               "name": end_name, "_is_user_end": True}])

    segments = []
    for i in range(len(pts) - 1):
        segments.append(_build_segment_candidate_list(pts[i], pts[i + 1], transport_mode))

    # 🆕 S3: 时间归一化（最快 0，最慢 40），加到每个候选的 discomfort 上
    _apply_time_normalization(segments)
    return segments, mid_points


# ---------------------------------------------------------------------------
# 把 Individual.segments 拼接成前端可用的方案 dict
# ---------------------------------------------------------------------------
def _format_nsga2_solution(ind, mid_points):
    """把候选集版 Individual 转成前端 JSON（含分步导航 + route_coords）。"""
    picks = ind.segments or []
    steps = []
    route_coords = []
    total_time = 0
    total_money = 0.0
    total_dis = 0.0
    step_order = 0

    for cand in picks:
        seg_time = int(cand.get("time", 0))
        seg_money = float(cand.get("money", 0))
        seg_dis = float(cand.get("discomfort", 0))
        total_time += seg_time
        total_money += seg_money
        total_dis += seg_dis

        # 景点游览时间加成：段终点是中间景点（非用户终点）时累加
        bonus = 0
        bonus_note = ""
        to_name = cand.get("to_name", "")
        if mid_points and not cand.get("_is_user_end"):
            for mp in mid_points:
                if mp["name"] == to_name:
                    bonus = int(mp.get("time_bonus", 0))
                    bonus_note = f"（含游览 {bonus} 分钟）"
                    total_time += bonus
                    break

        # 🆕 方案A：公交候选拆多 step（走路到站→乘地铁→换乘公交→走路到终）
        # 每个细分 step（walk/bus/subway）独立一个 step，el-steps 自然展示
        sub_steps_raw = cand.get("steps", []) if cand.get("mode") == "公交" else []
        if sub_steps_raw:
            for sub in sub_steps_raw:
                step_order += 1
                s_mode = sub.get("mode", "bus")
                mode_cn = {"walk": "步行", "bus": "公交",
                           "subway": "地铁", "rail": "高铁"}.get(s_mode, "公交")
                s_dur_s = sub.get("duration_s", 0) or 0
                s_dur = max(1, round(s_dur_s / 60)) if s_dur_s else 1
                s_dist = round((sub.get("distance_m", 0) or 0) / 1000, 2)
                instr = sub.get("instruction", "") or f"{mode_cn}段"
                sub_poly = sub.get("polyline", "") or ""
                sub_coords = _polyline_to_coords(sub_poly)
                if sub_coords:
                    from_lng, from_lat = sub_coords[0][0], sub_coords[0][1]
                    to_lng, to_lat = sub_coords[-1][0], sub_coords[-1][1]
                else:
                    from_lng = from_lat = to_lng = to_lat = 0

                steps.append({
                    "step_order": step_order,
                    "mode": mode_cn,
                    "from_name": sub.get("from_stop") or cand.get("from_name", "起点"),
                    "to_name": sub.get("to_stop") or cand.get("to_name", "终点"),
                    "from_lng": from_lng, "from_lat": from_lat,
                    "to_lng": to_lng, "to_lat": to_lat,
                    "duration": s_dur,
                    "cost": 0,            # 公交费用整体算，不按 step 拆
                    "distance_km": s_dist,
                    "tolls_yuan": 0,
                    "instruction": instr,
                    "polyline": sub_poly,
                    "amap_steps": [],     # 细分 step 不再嵌套折叠面板
                })
                # 累加 route_coords（去重相邻重复点）
                if sub_coords:
                    if route_coords and route_coords[-1] == sub_coords[0]:
                        route_coords.extend(sub_coords[1:])
                    else:
                        route_coords.extend(sub_coords)
            # 景点 bonus 加在最后一个细分 step（段终点是中间景点时）
            if bonus_note and steps:
                steps[-1]["instruction"] = steps[-1]["instruction"] + f" {bonus_note}"
        else:
            # 驾车/步行/估算 候选：1 step
            step_order += 1
            toll_note = f"，过路费 \u00a5{cand['tolls_yuan']}" if cand.get("tolls_yuan", 0) > 0 else ""
            instruction = (
                f"从 {cand.get('from_name','起点')} 出发，{cand.get('mode','交通')}前往 "
                f"{to_name}{bonus_note}，全程约 {cand.get('distance_km',0)} 公里，"
                f"预计耗时 {seg_time} 分钟{toll_note}。"
            )

            rc = cand.get("route_coords") or []
            from_lng = rc[0][0] if rc else 0
            from_lat = rc[0][1] if rc else 0
            to_lng = rc[-1][0] if rc else 0
            to_lat = rc[-1][1] if rc else 0

            steps.append({
                "step_order": step_order,
                "mode": cand.get("mode", "交通"),
                "from_name": cand.get("from_name", "起点"),
                "to_name": to_name,
                "from_lng": from_lng, "from_lat": from_lat,
                "to_lng": to_lng, "to_lat": to_lat,
                "duration": seg_time,
                "cost": seg_money,
                "distance_km": cand.get("distance_km", 0),
                "tolls_yuan": cand.get("tolls_yuan", 0),
                "instruction": instruction,
                "polyline": cand.get("polyline", ""),
                "amap_steps": cand.get("amap_steps", []),
            })
            # 累加 route_coords（去重相邻重复点）
            if route_coords and rc:
                if route_coords[-1] == rc[0]:
                    route_coords.extend(rc[1:])
                else:
                    route_coords.extend(rc)
            else:
                route_coords.extend(rc)

    if not route_coords and picks:
        first = picks[0].get("route_coords", [])
        last = picks[-1].get("route_coords", [])
        if first: route_coords.append(first[0])
        if last: route_coords.append(last[-1])

    return {
        "label": getattr(ind, "solution_label", ""),
        "total_time": int(total_time),
        "total_money": round(total_money, 2),
        "total_discomfort": round(total_dis, 2),
        "spot_ids": [m["id"] for m in mid_points],
        "route_coords": route_coords,
        "steps": steps,
        "objectives": list(ind.objectives) if ind.objectives else None,
        "elapsed": round(getattr(ind, "elapsed", 0), 3),
        # 🆕 估算方案透传：display_steps 时间轴 + estimated 标记
        "is_estimated": any(c.get("_estimated") for c in picks),
        "display_steps": [ds for c in picks for ds in c.get("display_steps", [])],
    }


# ---------------------------------------------------------------------------
# 🆕 坐标直达规划（论文规格：高德候选集 → NSGA-II → 四类代表方案）
# ---------------------------------------------------------------------------
def plan_direct_by_coords(start_lat, start_lng, start_name,
                          end_lat, end_lng, end_name,
                          mid_spot_ids=None, loader=None,
                          transport_mode="auto",
                          mode_ratings=None):
    """坐标直达规划（NSGA-II 为主路径）。
    流程：高德多模式候选集 → NSGA-II（pop20/gen15/cross0.9/mut0.3）→ 四类代表方案。

    mode_ratings: 🆕 S6 用户对各交通方式的均分（-2~+2），用于体验惩罚修正。
                  如 {"驾车": 1.5, "公交": -1.0} → 驾车 -30 惩罚，公交 +20 惩罚。
    """
    if loader is None:
        loader = DataLoader().load()
    _ensure_spot_cache()

    # 1. 构建候选集
    segments, mid_points = build_segment_candidates(
        start_lat, start_lng, start_name,
        end_lat, end_lng, end_name,
        mid_spot_ids=mid_spot_ids, loader=loader,
        transport_mode=transport_mode,
    )

    # 🆕 S6: 应用用户打分修正到候选集 discomfort（形成 使用-打分-优化 闭环）
    if mode_ratings:
        _apply_user_rating_correction(segments, mode_ratings)

    # 2. 跑 NSGA-II（论文参数）+ 收集每代迭代日志（HV/pareto_count/best_time/best_cost）
    pareto, iteration_logs, population = run_nsga2_candidates(
        segments,
        pop_size=20, max_gen=15,
        cross_prob=0.9, mut_prob=0.3,
        spot_time_bonus=0,  # 游览时间在 _format_nsga2_solution 里按段累加，避免重复
        collect_logs=True,
    )
    if not pareto:
        return [], iteration_logs

    # 3. 提取四类代表方案（帕累托不足时从种群补充差异化方案）
    reps = extract_representative_solutions(pareto, population)

    # 🆕 兜底：当 reps 仍 < 3 且只有 1 段时，直接从候选集补充差异化方案
    # （NSGA-II 在单段且某候选全面支配时会收敛到 1 个解，需从候选集补充对比方案）
    if len(reps) < 3 and len(segments) == 1:
        cands = segments[0]
        existing_objs = {tuple(ind.objectives) for ind in reps}
        for c in cands:
            if len(reps) >= 4:
                break
            obj = (c["time"], c["money"], c["discomfort"])
            if obj in existing_objs:
                continue
            # 构造一个伪 Individual 供 _format_nsga2_solution 使用
            from app.algorithms.nsga2 import Individual as _Ind
            pseudo = _Ind([0])
            pseudo.objectives = list(obj)
            pseudo.segments = [c]
            pseudo.elapsed = 0
            pseudo.solution_label = "对比方案"
            reps.append(pseudo)
            existing_objs.add(obj)

    # 4. 格式化输出
    results = [_format_nsga2_solution(ind, mid_points) for ind in reps]

    # 附上完整帕累托前沿（供前端可视化 / S2 持久化）和迭代日志
    pareto_payload = [{
        "rank": 0,
        "label": getattr(ind, "solution_label", ""),
        "objectives": list(ind.objectives) if ind.objectives else None,
        "route_order": list(ind.genes),
        "elapsed": round(getattr(ind, "elapsed", 0), 3),
    } for ind in pareto]

    for r in results:
        r["iteration_logs"] = iteration_logs
        r["pareto_frontier"] = pareto_payload
    return results, iteration_logs


# ---------------------------------------------------------------------------
# 分段规划（NSGA-II 核心的上层编排）
# ---------------------------------------------------------------------------
def run_segmented_plan(start_id: int, end_id: int,
                       spot_ids: list,
                       start_spot_id: int = None,
                       end_spot_id: int = None,
                       is_driving: bool = False,
                       preference: dict = None,
                       pop_size: int = 100,
                       max_gen: int = 150) -> list:
    """
    基于 cost_matrix 城市对的 NSGA-II 规划入口（城市 ID 模式）。
    当客户端只提供 start_id/end_id（无经纬度）时走此路径。
    完整规划入口。根据 start/end/spot_ids 自动选择策略：
      - start == end → 同城玩法（高德驾车 + 景点排序）
        - 有 start/end spot → 点对点（尊重用户意图，不去市中心）
        - 无 start/end spot → 中心出发环形（给多种排序）
      - 无 spot → 直接两点 NSGA-II
      - 有 spot → 分段 NSGA-II
    """
    from app.algorithms.nsga2 import run_nsga2

    preference = preference or {}
    _ensure_spot_cache()

    # ============ 高德实时填充：加载 DataLoader 并把焦点城市的缺失边补上 ============
    loader = DataLoader().load()
    focus_cities = {start_id, end_id}
    for sid in spot_ids:
        sc = _spot_cache.get(sid, {}).get("city_id")
        if sc:
            focus_cities.add(sc)
    loader.fill_missing_from_amap(
        focus_city_ids=list(focus_cities), max_edges=200
    )

    # ============ 同城玩法 ============
    if start_id == end_id and spot_ids:
        return _plan_local_tour(start_id, spot_ids,
                                start_spot_id=start_spot_id,
                                end_spot_id=end_spot_id,
                                loader=loader)

    # ============ 无景点：直接 NSGA-II 两点 ============
    if not spot_ids:
        pareto = run_nsga2([start_id, end_id],
                           pop_size=pop_size, max_gen=max_gen,
                           spot_time_bonus=0, is_driving=is_driving)
        pareto = [i for i in pareto if i.objectives[0] != np.inf]
        pareto = _cluster_pareto(pareto, n=5)
        return [_plan_to_dict(
            {"segments": [i], "spot_at_end_list": [],
             "total_time": i.objectives[0],
             "total_money": i.objectives[1],
             "total_discomfort": i.objectives[2]},
            [])
            for i in pareto]

    # ============ 有景点：分段 NSGA-II ============
    # 简化：所有 spot 时间加进 spot_time_bonus，nsga2 跑 start→end
    spot_time_pairs = [(s, spot_time_bonus(s)) for s in spot_ids]

    pareto = run_nsga2(
        [start_id, end_id],
        pop_size=pop_size, max_gen=max_gen,
        spot_time_bonus=sum(t for _, t in spot_time_pairs),
        is_driving=is_driving,
    )
    pareto = [i for i in pareto if i.objectives[0] != np.inf]
    pareto = _cluster_pareto(pareto, n=5)

    # 给每个候选附上 spot_at_end_list（把景点放在终点前游览）
    result = []
    for i in pareto:
        candidate = {
            "segments": [i],
            "spot_at_end_list": [spot_time_pairs],
            "total_time": i.objectives[0],
            "total_money": i.objectives[1],
            "total_discomfort": i.objectives[2],
        }
        result.append(_plan_to_dict(candidate, spot_ids))

    return result


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """返回两点间的直线距离（公里），同城场景下近似于驾车距离的 70-85%"""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _fallback_nsga2_same_city(city_id: int, spot_ids: list) -> list:
    """nsga2 兜底，不太靠谱但能返回点东西"""
    pareto = run_nsga2([city_id, city_id], spot_time_bonus=sum(spot_time_bonus(s) for s in spot_ids))
    pareto = [p for p in pareto if p.objectives[0] != np.inf]
    if pareto:
        pareto = _cluster_pareto(pareto, n=1)
        return [_plan_to_dict(
            {"total_time": i.objectives[0], "total_money": i.objectives[1],
             "total_discomfort": i.objectives[2], "segments": [i],
             "spot_at_end_list": [[(s, spot_time_bonus(s)) for s in spot_ids]]},
            spot_ids) for i in pareto]
    return []


# ---------------------------------------------------------------------------
# 方案聚类：从 Pareto 前沿里选 N 个差异化代表
# ---------------------------------------------------------------------------
def _cluster_pareto(individuals, n=5):
    """
    从 Pareto 前沿里选 n 个差异化最大的解。
    做法：每选一个，把已选解附近（目标空间欧氏距离小于阈值）的删掉。
    如果删完还不够，阈值减半继续，直到选满 n 或没有解为止。
    """
    if len(individuals) <= n:
        return individuals

    objs = np.array([ind.objectives for ind in individuals])
    # 归一化每个目标到 [0,1]，避免时间(min)比钱(¥)大一个数量级
    mins = objs.min(axis=0)
    maxs = objs.max(axis=0)
    ranges = np.where(maxs - mins < 1e-6, 1, maxs - mins)
    norm = (objs - mins) / ranges

    selected = []
    remaining = list(range(len(individuals)))
    thresholds = [0.30, 0.20, 0.12, 0.06, 0.03]

    for th in thresholds:
        if len(selected) >= n or not remaining:
            break
        # 继续选
        while len(selected) < n and remaining:
            # 计算每个 remaining 点到已选集合的最小距离
            if not selected:
                # 第一个：选目标空间最中心的点
                center = norm.mean(axis=0)
                dists = np.linalg.norm(norm[remaining] - center, axis=1)
                pick = remaining[int(np.argmin(dists))]
            else:
                sel_objs = norm[selected]
                min_dists = []
                for ri in remaining:
                    d = np.min(np.linalg.norm(sel_objs - norm[ri], axis=1))
                    min_dists.append(d)
                min_dists = np.array(min_dists)
                far_idx = int(np.argmax(min_dists))
                pick = remaining[far_idx]
            selected.append(pick)
            # 移除附近的
            cur = norm[pick]
            remaining = [ri for ri in remaining
                         if np.linalg.norm(norm[ri] - cur) > th]

    # 选不满 n 就把剩余的也加上（保持多样化）
    while len(selected) < n and remaining:
        selected.append(remaining.pop(0))

    return [individuals[i] for i in selected[:n]]


# ---------------------------------------------------------------------------
# 把 Candidate dict 转成前端 JSON（含具体交通指令）
# ---------------------------------------------------------------------------
def _plan_to_dict(candidate: dict, spot_ids: list) -> dict:
    loader = DataLoader()
    all_steps = []
    all_route_coords = []
    step_order = 0
    spot_at_end_list = candidate.get("spot_at_end_list", [])

    for seg_idx, ind in enumerate(candidate["segments"]):
        full_stops = ind.full_path(ind.start_idx, ind.end_idx)
        full_route_idx = loader.full_route(full_stops)

        # 坐标数组
        for idx in full_route_idx:
            cid = loader.city_ids[idx]
            city = loader.id_to_city.get(cid)
            if city:
                all_route_coords.append([float(city.lng), float(city.lat)])

        # 分步详情（含具体交通指令）
        for a, b in zip(full_route_idx, full_route_idx[1:]):
            step_order += 1
            a_city = loader.id_to_city[loader.city_ids[a]]
            b_city = loader.id_to_city[loader.city_ids[b]]
            seg_time = int(loader.time_matrix[a][b])
            seg_money = round(float(loader.money_matrix[a][b]), 2)

            # ---- 优先用高德驾车 API 生成真实指令 ----
            from app.utils.amap_router import driving as _amap_drive
            drive = _amap_drive(float(a_city.lng), float(a_city.lat),
                                float(b_city.lng), float(b_city.lat))
            # 🆕 格式化高德逐步导航指令（方便前端展示）
            amap_steps_simplified = []
            if drive and drive.get("steps"):
                for s in drive["steps"]:
                    dist_m = s.get("distance_m", 0)
                    dur_s = s.get("duration_s", 0)
                    dist_str = f"{dist_m}m" if dist_m < 1000 else f"{dist_m/1000:.1f}km"
                    dur_str = f"{dur_s}s" if dur_s < 60 else f"{dur_s//60}min"
                    amap_steps_simplified.append({
                        "instruction": s.get("instruction", ""),
                        "road": s.get("road", ""),
                        "distance_str": dist_str,
                        "duration_str": dur_str,
                        "distance_m": dist_m,
                        "duration_s": dur_s,
                    })
            if drive:
                # 真实交通指令
                toll_note = f"，过路费 ¥{drive['tolls_yuan']}" if drive['tolls_yuan'] > 0 else ""
                road_note = ""
                if drive['steps']:
                    s0 = drive['steps'][0]
                    road_note = f"，起步 {s0['instruction']}"
                instruction = (
                    f"从 {a_city.name} 出发，驾车前往 {b_city.name}，"
                    f"全程约 {drive['distance_km']} 公里，预计耗时 {drive['duration_min']} 分钟"
                    f"{toll_note}{road_note}。"
                )
            else:
                # 回退：用时间粗略推断
                hh = seg_time // 60; mm = seg_time % 60
                if seg_time <= 10:
                    instruction = f"从 {a_city.name} 步行前往 {b_city.name}，约 {seg_time} 分钟"
                elif seg_time <= 400:
                    instruction = f"从 {a_city.name} 乘坐城际交通前往 {b_city.name}，耗时约 {hh}h{mm}min，约 ¥{seg_money:.0f}"
                else:
                    instruction = f"从 {a_city.name} 前往 {b_city.name}，总耗时约 {hh}h{mm}min，约 ¥{seg_money:.0f}"

            if seg_time <= 10: mode = "步行"
            elif seg_time <= 60: mode = "市内公交"
            elif seg_time <= 120: mode = "城际大巴"
            elif seg_time <= 400: mode = "高铁动车"
            else: mode = "长途交通"

            all_steps.append({
                "step_order": step_order,
                "mode": mode,
                "from_name": a_city.name,
                "to_name": b_city.name,
                "from_lng": float(a_city.lng), "from_lat": float(a_city.lat),
                "to_lng": float(b_city.lng), "to_lat": float(b_city.lat),
                "duration": seg_time, "cost": seg_money,
                "instruction": instruction,
                "amap_steps": amap_steps_simplified,  # 🆕 高德逐步导航指令
            })

        # 段末附加多个景点（从 spot_at_end_list 拿）
        if seg_idx < len(spot_at_end_list):
            for sid, sb in spot_at_end_list[seg_idx]:
                if sid in _spot_cache:
                    spot_info = _spot_cache[sid]
                    city_c = City.query.get(spot_info["city_id"])
                    step_order += 1
                    all_steps.append({
                        "step_order": step_order,
                        "mode": "景点游览",
                        "from_name": spot_info["name"],
                        "to_name": spot_info["name"],
                        "from_lng": float(city_c.lng) if city_c else 0,
                        "from_lat": float(city_c.lat) if city_c else 0,
                        "to_lng": float(city_c.lng) if city_c else 0,
                        "to_lat": float(city_c.lat) if city_c else 0,
                        "duration": spot_info["cost_time_extra"],
                        "cost": 0.0,
                        "instruction": f"游览 {spot_info['name']}，建议用时 {spot_info['cost_time_extra']} 分钟。可拍照打卡、品尝当地美食、感受文化底蕴。",
                    })

    return {
        "total_time": int(candidate["total_time"]),
        "total_money": round(float(candidate["total_money"]), 2),
        "total_discomfort": round(float(candidate["total_discomfort"]), 2),
        "spot_ids": spot_ids,
        "route_coords": all_route_coords,
        "steps": all_steps,
    }
