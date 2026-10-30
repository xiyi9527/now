"""
🆕 S5: 出行提示 Blueprint（论文 4.6 节）
所有路由前缀: /api/tip
"""
from flask import Blueprint, request, jsonify
from sqlalchemy import or_, desc

from app import db
from app.models import Tip

tip_bp = Blueprint("tip", __name__)


@tip_bp.route("/match", methods=["GET"])
def tip_match():
    """根据途经城市匹配出行提示
    参数: cities（逗号分隔的城市列表，如 "安顺,宜宾"）
           category（可选，crowd/transit/tips/general）
    返回: 按城市分组的提示列表 + 全国通用提示"""
    cities_raw = request.args.get("cities", "").strip()
    category = request.args.get("category")
    if not cities_raw:
        return jsonify(ok=False, msg="缺少 cities 参数"), 400

    cities = [c.strip() for c in cities_raw.split(",") if c.strip()]
    if not cities:
        return jsonify(ok=False, msg="城市参数为空"), 400

    # 匹配条件：城市在列表里 OR 全国通用
    conds = [Tip.city.in_(cities), Tip.city == "全国"]
    q = Tip.query.filter(or_(*conds))
    if category:
        q = q.filter(Tip.category == category)
    tips = q.order_by(desc(Tip.priority)).all()

    # 按城市分组
    by_city = {c: [] for c in cities}
    by_city["全国"] = []
    for t in tips:
        c = t.city if t.city in by_city else "全国"
        by_city[c].append({
            "id": t.id, "category": t.category, "title": t.title,
            "content": t.content, "priority": t.priority,
        })

    return jsonify(ok=True, data={
        "cities": cities,
        "groups": by_city,
        "total": len(tips),
    })


@tip_bp.route("/recommend", methods=["GET"])
def tip_recommend():
    """推荐某城市的出行提示（按 priority 降序，默认前 5 条）
    参数: city（必填）, category（可选）, limit（默认 5）"""
    city = request.args.get("city", "").strip()
    category = request.args.get("category")
    limit = request.args.get("limit", 5, type=int)
    if not city:
        return jsonify(ok=False, msg="缺少 city 参数"), 400

    # 城市匹配 + 全国通用
    conds = [Tip.city == city, Tip.city == "全国"]
    q = Tip.query.filter(or_(*conds))
    if category:
        q = q.filter(Tip.category == category)
    tips = q.order_by(desc(Tip.priority)).limit(limit).all()

    return jsonify(ok=True, data=[{
        "id": t.id, "city": t.city, "category": t.category,
        "title": t.title, "content": t.content, "priority": t.priority,
    } for t in tips])


@tip_bp.route("/list", methods=["GET"])
def tip_list():
    """全量提示列表（带分页 + 城市过滤）"""
    city = request.args.get("city")
    category = request.args.get("category")
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)

    q = Tip.query
    if city:
        q = q.filter(Tip.city == city)
    if category:
        q = q.filter(Tip.category == category)
    total = q.count()
    tips = q.order_by(desc(Tip.priority), desc(Tip.id)) \
            .offset((page - 1) * size).limit(size).all()

    return jsonify(ok=True, data={
        "total": total,
        "list": [{
            "id": t.id, "city": t.city, "category": t.category,
            "title": t.title, "content": t.content, "priority": t.priority,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        } for t in tips],
    })


@tip_bp.route("/<int:tid>", methods=["GET"])
def tip_detail(tid):
    """单条提示详情"""
    t = Tip.query.get(tid)
    if not t:
        return jsonify(ok=False, msg="提示不存在"), 404
    return jsonify(ok=True, data={
        "id": t.id, "city": t.city, "category": t.category,
        "title": t.title, "content": t.content, "priority": t.priority,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    })


@tip_bp.route("/", methods=["POST"])
def tip_create():
    """新增提示（管理员/登录用户）"""
    from flask_jwt_extended import jwt_required, get_jwt
    try:
        from flask import current_app
        # 简单鉴权：要求 JWT 且 role=admin（不强制，方便后台填充）
    except Exception:
        pass
    data = request.get_json(force=True) or {}
    if not data.get("city") or not data.get("title") or not data.get("content"):
        return jsonify(ok=False, msg="city/title/content 必填"), 400
    t = Tip(
        city=data["city"],
        category=data.get("category", "general"),
        title=data["title"],
        content=data["content"],
        priority=int(data.get("priority", 50)),
    )
    db.session.add(t)
    db.session.commit()
    return jsonify(ok=True, data={"id": t.id}), 201
