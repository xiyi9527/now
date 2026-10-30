"""
🔐 管理员后台 API Blueprint
所有路由前缀: /api/admin
统一权限: @admin_required（查 JWT claim → role='admin'）
"""
from functools import wraps
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from app import db
from app.models import User, City, Spot, CostMatrix, Plan, Solution, IterationLog
from sqlalchemy import func, desc


admin_bp = Blueprint("admin", __name__)


# ========= 🔐 权限装饰器 =========
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify(ok=False, msg="需要管理员权限"), 403
        return fn(*args, **kwargs)
    return wrapper


def _user_to_dict(u):
    return {
        "id": u.id, "username": u.username, "email": u.email,
        "avatar_url": u.avatar_url, "role": u.role or "user",
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ========= 📊 仪表盘统计 =========
@admin_bp.route("/stats", methods=["GET"])
@admin_required
def admin_stats():
    return jsonify(ok=True, data={
        "users": User.query.count(),
        "admins": User.query.filter_by(role="admin").count(),
        "cities": City.query.count(),
        "spots": Spot.query.count(),
        "plans": Plan.query.count(),
        "public_plans": Plan.query.filter_by(is_public=True).count(),
        "cost_matrix": CostMatrix.query.count(),
    })


# ========= 👥 用户管理 =========
@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    q = User.query
    if request.args.get("role"):
        q = q.filter_by(role=request.args["role"])
    kw = request.args.get("kw", "").strip()
    if kw:
        q = q.filter(User.username.contains(kw) | User.email.contains(kw))
    users = q.order_by(User.id.desc()).limit(200).all()
    return jsonify(ok=True, data=[_user_to_dict(u) for u in users])


@admin_bp.route("/users/<int:uid>/role", methods=["PUT"])
@admin_bp.route("/users/<int:uid>", methods=["DELETE"])
@admin_required
def user_action(uid):
    u = User.query.get(uid)
    if not u:
        return jsonify(ok=False, msg="用户不存在"), 404

    if request.method == "PUT":
        data = request.get_json()
        role = data.get("role")
        if role not in ("user", "admin"):
            return jsonify(ok=False, msg="role 只能是 user/admin"), 400
        u.role = role
        db.session.commit()
        return jsonify(ok=True, data=_user_to_dict(u))

    # DELETE
    # 防止删自己
    if int(get_jwt_identity()) == uid:
        return jsonify(ok=False, msg="不能删除自己"), 400
    db.session.delete(u)
    db.session.commit()
    return jsonify(ok=True)


# ========= 🏙️ 城市管理 =========
@admin_bp.route("/cities", methods=["GET", "POST"])
@admin_required
def admin_cities():
    if request.method == "POST":
        data = request.get_json()
        city = City(
            name=data["name"], province=data.get("province"),
            hub_name=data.get("hub_name"),
            lat=float(data["lat"]), lng=float(data["lng"]),
            is_hot=data.get("is_hot", False),
        )
        db.session.add(city)
        db.session.commit()
        return jsonify(ok=True, data={"id": city.id})

    # GET — 带关键词搜索
    kw = request.args.get("kw", "").strip()
    q = City.query
    if kw:
        q = q.filter(City.name.contains(kw) | City.province.contains(kw))
    return jsonify(ok=True, data=[{
        "id": c.id, "name": c.name, "province": c.province,
        "lat": float(c.lat), "lng": float(c.lng),
        "is_hot": bool(c.is_hot), "spots_count": len(c.spots),
    } for c in q.order_by(City.is_hot.desc(), City.id).all()])


@admin_bp.route("/cities/<int:cid>", methods=["PUT", "DELETE"])
@admin_required
def admin_city_one(cid):
    c = City.query.get(cid)
    if not c:
        return jsonify(ok=False, msg="城市不存在"), 404

    if request.method == "PUT":
        data = request.get_json()
        for k in ("name", "province", "hub_name"):
            if k in data:
                setattr(c, k, data[k])
        if "lat" in data:
            c.lat = float(data["lat"])
        if "lng" in data:
            c.lng = float(data["lng"])
        if "is_hot" in data:
            c.is_hot = bool(data["is_hot"])
        db.session.commit()
        return jsonify(ok=True)

    db.session.delete(c)
    db.session.commit()
    return jsonify(ok=True)


# ========= 🏞️ 景点管理 =========
@admin_bp.route("/spots", methods=["GET", "POST"])
@admin_required
def admin_spots():
    if request.method == "POST":
        data = request.get_json()
        spot = Spot(
            name=data["name"], city_id=int(data["city_id"]),
            description=data.get("description", ""),
            img_url=data.get("img_url"),
            lat=float(data["lat"]), lng=float(data["lng"]),
            cost_time_extra=int(data.get("cost_time_extra", 120)),
        )
        db.session.add(spot)
        db.session.commit()
        return jsonify(ok=True, data={"id": spot.id})

    # GET
    city_id = request.args.get("city_id", type=int)
    kw = request.args.get("kw", "").strip()
    q = Spot.query
    if city_id:
        q = q.filter_by(city_id=city_id)
    if kw:
        q = q.filter(Spot.name.contains(kw))
    return jsonify(ok=True, data=[{
        "id": s.id, "name": s.name, "city_id": s.city_id,
        "city_name": s.city.name if s.city else None,
        "description": s.description, "img_url": s.img_url,
        "lat": float(s.lat), "lng": float(s.lng),
        "cost_time_extra": s.cost_time_extra,
    } for s in q.order_by(Spot.id.desc()).limit(300).all()])


@admin_bp.route("/spots/<int:sid>", methods=["PUT", "DELETE"])
@admin_required
def admin_spot_one(sid):
    s = Spot.query.get(sid)
    if not s:
        return jsonify(ok=False, msg="景点不存在"), 404

    if request.method == "PUT":
        data = request.get_json()
        for k in ("name", "description", "img_url"):
            if k in data:
                setattr(s, k, data[k])
        if "city_id" in data:
            s.city_id = int(data["city_id"])
        if "lat" in data:
            s.lat = float(data["lat"])
        if "lng" in data:
            s.lng = float(data["lng"])
        if "cost_time_extra" in data:
            s.cost_time_extra = int(data["cost_time_extra"])
        db.session.commit()
        return jsonify(ok=True)

    db.session.delete(s)
    db.session.commit()
    return jsonify(ok=True)


# ========= 💰 成本矩阵管理 =========
@admin_bp.route("/cost-matrix", methods=["GET", "POST"])
@admin_required
def admin_cost_matrix():
    if request.method == "POST":
        data = request.get_json()
        entry = CostMatrix(
            from_city_id=int(data["from_city_id"]),
            to_city_id=int(data["to_city_id"]),
            mode=data.get("mode", "综合"),
            time_cost=int(data["time_cost"]),
            money_cost=float(data["money_cost"]),
            transfer_times=int(data.get("transfer_times", 0)),
            discomfort=float(data.get("discomfort", 0)),
        )
        db.session.add(entry)
        db.session.commit()
        return jsonify(ok=True, data={"id": entry.id})

    # GET
    total_possible = City.query.count() * (City.query.count() - 1)
    covered = CostMatrix.query.count()
    return jsonify(
        ok=True,
        stats={
            "total_cities": City.query.count(),
            "covered_edges": covered,
            "total_possible_edges": total_possible,
            "coverage_pct": round(covered / total_possible * 100, 1) if total_possible else 0,
        },
        data=[{
            "id": c.id,
            "from_city": City.query.get(c.from_city_id).name if City.query.get(c.from_city_id) else None,
            "to_city": City.query.get(c.to_city_id).name if City.query.get(c.to_city_id) else None,
            "mode": c.mode,
            "time_cost": c.time_cost, "money_cost": float(c.money_cost),
            "transfer_times": c.transfer_times, "discomfort": float(c.discomfort),
        } for c in CostMatrix.query.order_by(CostMatrix.from_city_id, CostMatrix.to_city_id).limit(500).all()]
    )


@admin_bp.route("/cost-matrix/<int:mid>", methods=["PUT", "DELETE"])
@admin_required
def admin_cost_one(mid):
    c = CostMatrix.query.get(mid)
    if not c:
        return jsonify(ok=False, msg="成本记录不存在"), 404

    if request.method == "PUT":
        data = request.get_json()
        for k in ("from_city_id", "to_city_id", "mode"):
            if k in data:
                setattr(c, k, int(data[k]) if "id" in k else data[k])
        for k in ("time_cost", "transfer_times"):
            if k in data:
                setattr(c, k, int(data[k]))
        for k in ("money_cost", "discomfort"):
            if k in data:
                setattr(c, k, float(data[k]))
        db.session.commit()
        return jsonify(ok=True)

    db.session.delete(c)
    db.session.commit()
    return jsonify(ok=True)


# ========= 🔧 一键补全：调用高德驾车 API 填充缺失边 =========
@admin_bp.route("/cost-matrix/fill-from-amap", methods=["POST"])
@admin_required
def admin_cost_fill_amap():
    """
    用高德驾车 API 遍历所有缺失的城市对 → 写入 cost_matrix 表。
    同步执行（330 条约 1-2 分钟），前端会 loading。
    """
    import time as _time
    from app.utils.amap_router import driving as amap_drive, cache_stats

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "综合")
    max_edges = int(data.get("max_edges", 0))   # 0 = 全量
    skip_reverse = bool(data.get("skip_reverse", False))

    cities = City.query.order_by(City.id).all()
    N = len(cities)
    existing = set(
        (r.from_city_id, r.to_city_id, r.mode)
        for r in CostMatrix.query.filter_by(mode=mode).all()
    )
    total_pairs = N * (N - 1)
    missing = [
        (c1, c2) for c1 in cities for c2 in cities
        if c1.id != c2.id and (c1.id, c2.id, mode) not in existing
    ]
    if max_edges > 0:
        missing = missing[:max_edges]

    if not missing:
        return jsonify(ok=True, msg="无需补全", stats={
            "existing": len(existing), "missing_to_fill": 0,
            "total_possible": total_pairs,
            "coverage_pct": round(len(existing) / total_pairs * 100, 1),
        })

    success = 0
    failed = 0
    failed_pairs = []
    t0 = _time.time()

    for c1, c2 in missing:
        r = amap_drive(float(c1.lng), float(c1.lat),
                       float(c2.lng), float(c2.lat))
        if r is None:
            failed += 1
            failed_pairs.append(f"{c1.name}→{c2.name}")
        else:
            edge = CostMatrix(
                from_city_id=c1.id, to_city_id=c2.id, mode=mode,
                time_cost=int(r["duration_min"]),
                money_cost=round(r["tolls_yuan"] + r["distance_km"] * 0.3, 2),
                transfer_times=0,
                discomfort=round(r["distance_km"] * 0.03, 2),
            )
            db.session.add(edge)
            success += 1
            # 对称补（反向缺失直接用同一条数据）
            if not skip_reverse and (c2.id, c1.id, mode) not in existing:
                rev = CostMatrix(
                    from_city_id=c2.id, to_city_id=c1.id, mode=mode,
                    time_cost=edge.time_cost, money_cost=edge.money_cost,
                    transfer_times=0, discomfort=edge.discomfort,
                )
                db.session.add(rev)
                # 标记已存在，避免重复补
                existing.add((c2.id, c1.id, mode))
        _time.sleep(0.08)

    db.session.commit()
    elapsed = _time.time() - t0
    amap_stats = cache_stats()

    new_total = CostMatrix.query.filter_by(mode=mode).count()
    # 全 mode 总数（GET stats 用）
    all_mode_total = CostMatrix.query.count()

    return jsonify(
        ok=True,
        stats={
            "mode": mode,
            "filled_forward": success,
            "failed": failed,
            "failed_pairs": failed_pairs[:20],
            "api_calls": amap_stats["api_calls"],
            "cache_hits": amap_stats["cache_hits"],
            "elapsed_sec": round(elapsed, 1),
            "mode_total_after": new_total,
            "mode_coverage_pct": round(new_total / total_pairs * 100, 1),
            "all_mode_total_edges": all_mode_total,
        }
    )


# ========= 🗺️ 规划列表（只读 + 删除） =========
@admin_bp.route("/plans", methods=["GET"])
@admin_required
def admin_plans():
    kw = request.args.get("kw", "").strip()
    q = Plan.query
    if kw:
        q = q.filter(Plan.username.contains(kw) if hasattr(Plan, "username") else Plan.user.has(username=kw))
    plans = q.order_by(Plan.created_at.desc()).limit(100).all()
    return jsonify(ok=True, data=[{
        "id": p.id, "user_id": p.user_id, "username": p.user.username if p.user else None,
        "start_city_id": p.start_city_id, "end_city_id": p.end_city_id,
        "total_time": p.total_time, "total_money": float(p.total_money),
        "is_public": bool(p.is_public), "rating": p.rating,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in plans])


@admin_bp.route("/plans/<int:pid>", methods=["DELETE"])
@admin_required
def admin_plan_delete(pid):
    p = Plan.query.get(pid)
    if not p:
        return jsonify(ok=False, msg="规划不存在"), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify(ok=True)


# ===========================================================================
# 🆕 S4: 数据可视化仪表盘（论文 4.5 节）
#   - /dashboard/overview        总览（用户/规划/方案/迭代日志/平均HV/缓存）
#   - /dashboard/hv-convergence  某规划的 HV 收敛曲线
#   - /dashboard/pareto-scatter  某规划的帕累托散点
#   - /dashboard/recent-plans    最近规划（带方案数 + 最新HV）
#   - /dashboard/alg-stats       算法统计（HV 均值/帕累托解均值/运行次数）
# ===========================================================================
@admin_bp.route("/dashboard/overview", methods=["GET"])
@admin_required
def dashboard_overview():
    """总览统计：用户/规划/方案/迭代日志数 + 平均HV + 缓存命中"""
    from app.utils.amap_router import cache_stats
    avg_hv = db.session.query(func.Avg(IterationLog.hv)).scalar()
    return jsonify(ok=True, data={
        "users": User.query.count(),
        "admins": User.query.filter_by(role="admin").count(),
        "cities": City.query.count(),
        "spots": Spot.query.count(),
        "plans": Plan.query.count(),
        "public_plans": Plan.query.filter_by(is_public=True).count(),
        "solutions": Solution.query.count(),
        "iteration_logs": IterationLog.query.count(),
        "avg_hv": round(float(avg_hv), 2) if avg_hv else None,
        "amap_cache": cache_stats(),
    })


@admin_bp.route("/dashboard/hv-convergence", methods=["GET"])
@admin_required
def dashboard_hv_convergence():
    """某规划的 HV 收敛曲线（iteration_log 表）
    参数: plan_id（必填）"""
    plan_id = request.args.get("plan_id", type=int)
    if not plan_id:
        return jsonify(ok=False, msg="缺少 plan_id"), 400
    logs = IterationLog.query.filter_by(plan_id=plan_id).order_by(IterationLog.gen).all()
    return jsonify(ok=True, data={
        "plan_id": plan_id,
        "series": [{
            "gen": l.gen,
            "hv": float(l.hv) if l.hv is not None else 0,
            "pareto_count": l.pareto_count or 0,
            "best_time": float(l.best_time) if l.best_time is not None else None,
            "best_cost": float(l.best_cost) if l.best_cost is not None else None,
        } for l in logs],
    })


@admin_bp.route("/dashboard/pareto-scatter", methods=["GET"])
@admin_required
def dashboard_pareto_scatter():
    """某规划的帕累托散点（solution 表）
    参数: plan_id（必填）
    返回: [{time, cost, experience, label, rank}]"""
    plan_id = request.args.get("plan_id", type=int)
    if not plan_id:
        return jsonify(ok=False, msg="缺少 plan_id"), 400
    sols = Solution.query.filter_by(plan_id=plan_id).order_by(Solution.rank, Solution.id).all()
    return jsonify(ok=True, data=[{
        "id": s.id, "rank": s.rank, "label": s.label or "",
        "time": float(s.objectives.get("time", 0)) if s.objectives else 0,
        "cost": float(s.objectives.get("cost", 0)) if s.objectives else 0,
        "experience": float(s.objectives.get("experience", 0)) if s.objectives else 0,
        "elapsed": float(s.elapsed) if s.elapsed else 0,
    } for s in sols])


@admin_bp.route("/dashboard/recent-plans", methods=["GET"])
@admin_required
def dashboard_recent_plans():
    """最近规划列表（带方案数 + 最新HV + 用户名）
    参数: limit（默认 20）"""
    limit = request.args.get("limit", 20, type=int)
    plans = Plan.query.order_by(desc(Plan.created_at)).limit(limit).all()
    out = []
    for p in plans:
        sol_count = Solution.query.filter_by(plan_id=p.id).count()
        log_count = IterationLog.query.filter_by(plan_id=p.id).count()
        last_log = IterationLog.query.filter_by(plan_id=p.id).order_by(desc(IterationLog.gen)).first()
        out.append({
            "id": p.id,
            "user_id": p.user_id,
            "username": p.user.username if p.user else None,
            "total_time": p.total_time,
            "total_money": float(p.total_money),
            "is_public": bool(p.is_public),
            "solution_count": sol_count,
            "iteration_log_count": log_count,
            "last_hv": float(last_log.hv) if last_log and last_log.hv is not None else None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        })
    return jsonify(ok=True, data=out)


@admin_bp.route("/dashboard/alg-stats", methods=["GET"])
@admin_required
def dashboard_alg_stats():
    """算法总体统计：HV 均值/中位数/最大/最小、帕累托解均值、NSGA-II 运行次数"""
    hv_stats = db.session.query(
        func.Count(IterationLog.id).label("n"),
        func.Avg(IterationLog.hv).label("mean"),
        func.Max(IterationLog.hv).label("max"),
        func.Min(IterationLog.hv).label("min"),
    ).filter(IterationLog.hv.isnot(None)).first()

    sol_stats = db.session.query(
        func.Count(Solution.id).label("n"),
        func.Avg(Solution.elapsed).label("mean_elapsed"),
    ).first()

    # 每个 plan 的帕累托解数（取平均）
    sub = db.session.query(
        Solution.plan_id,
        func.Count(Solution.id).label("cnt")
    ).group_by(Solution.plan_id).subquery()
    avg_pareto = db.session.query(func.Avg(sub.c.cnt)).scalar()

    return jsonify(ok=True, data={
        "hv": {
            "n": int(hv_stats.n or 0),
            "mean": round(float(hv_stats.mean), 2) if hv_stats.mean else None,
            "max": round(float(hv_stats.max), 2) if hv_stats.max else None,
            "min": round(float(hv_stats.min), 2) if hv_stats.min else None,
        },
        "solutions": {
            "n": int(sol_stats.n or 0),
            "mean_elapsed": round(float(sol_stats.mean_elapsed), 3) if sol_stats.mean_elapsed else None,
        },
        "avg_pareto_per_plan": round(float(avg_pareto), 2) if avg_pareto else None,
        "total_plans": Plan.query.count(),
        "total_iteration_logs": IterationLog.query.count(),
    })
