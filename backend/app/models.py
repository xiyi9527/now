"""
SQLAlchemy ORM 模型
与 travel_planner2 数据库 7 张表一一对应
"""
from datetime import datetime
from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100))
    avatar_url = db.Column(db.String(255))
    role = db.Column(db.Enum("user", "admin"), default="user")  # 🔐 权限
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plans = db.relationship("Plan", backref="user", lazy=True)
    favorites = db.relationship("Favorite", backref="user", lazy=True)

    def is_admin(self):
        return self.role == "admin"


class City(db.Model):
    __tablename__ = "cities"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    province = db.Column(db.String(50))
    hub_name = db.Column(db.String(100))
    lat = db.Column(db.Numeric(10, 6), nullable=False)
    lng = db.Column(db.Numeric(10, 6), nullable=False)
    is_hot = db.Column(db.Boolean, default=False)


class Spot(db.Model):
    __tablename__ = "spots"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    description = db.Column(db.String(500))
    img_url = db.Column(db.String(255))
    lat = db.Column(db.Numeric(10, 6), nullable=False)
    lng = db.Column(db.Numeric(10, 6), nullable=False)
    cost_time_extra = db.Column(db.Integer, default=120)

    city = db.relationship("City", backref="spots")


class CostMatrix(db.Model):
    __tablename__ = "cost_matrix"

    id = db.Column(db.Integer, primary_key=True)
    from_city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    to_city_id = db.Column(db.Integer, db.ForeignKey("cities.id"), nullable=False)
    mode = db.Column(db.String(20), default="综合")
    time_cost = db.Column(db.Integer, nullable=False)      # 分钟
    money_cost = db.Column(db.Numeric(10, 2), nullable=False)  # 元
    transfer_times = db.Column(db.SmallInteger, default=0)
    discomfort = db.Column(db.Numeric(5, 2), default=0)


class Plan(db.Model):
    __tablename__ = "plans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_city_id = db.Column(db.Integer, nullable=False)
    end_city_id = db.Column(db.Integer, nullable=False)
    spot_ids = db.Column(db.String(100))          # "1,2,3"
    total_time = db.Column(db.Integer, nullable=False)
    total_money = db.Column(db.Numeric(10, 2), nullable=False)
    total_discomfort = db.Column(db.Numeric(5, 2), default=0)
    route_detail = db.Column(db.JSON, nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    rating = db.Column(db.SmallInteger, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    steps = db.relationship("PlanStep", backref="plan", lazy=True, cascade="all, delete-orphan")


class PlanStep(db.Model):
    __tablename__ = "plan_steps"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    from_name = db.Column(db.String(100), nullable=False)
    to_name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    cost = db.Column(db.Numeric(10, 2), default=0)
    instruction = db.Column(db.String(255))


class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("user_id", "plan_id", name="uk_user_plan"),)


class AmapCache(db.Model):
    """🆕 高德 API 结果缓存（持久化 + TTL）"""
    __tablename__ = "amap_cache"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(128), unique=True, nullable=False, index=True)
    value_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)   # TTL 到期时间

    def is_expired(self):
        return datetime.utcnow() > self.expires_at


# ===========================================================================
# 🆕 S2：NSGA-II 结果持久化（论文 4.3.3 节）
# ===========================================================================
class Solution(db.Model):
    """NSGA-II 帕累托解持久化（每个 plan 可关联多个解）"""
    __tablename__ = "solution"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    rank = db.Column(db.Integer, default=0)              # 非支配等级
    label = db.Column(db.String(20))                      # 四类标签：最省时/最省钱/体验最优/均衡型
    objectives = db.Column(db.JSON, nullable=False)      # {time, cost, experience}
    route_order = db.Column(db.JSON)                      # 候选索引序列 [seg1_idx, seg2_idx, ...]
    segments = db.Column(db.JSON)                          # 各段详情 JSON
    elapsed = db.Column(db.Numeric(10, 3))                 # NSGA-II 运行耗时(秒)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan", backref="solutions")


class IterationLog(db.Model):
    """NSGA-II 每代迭代日志（HV 收敛曲线、帕累托解数）"""
    __tablename__ = "iteration_log"

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    gen = db.Column(db.Integer, nullable=False)              # 代数
    hv = db.Column(db.Numeric(20, 4))                         # 超体积指标
    pareto_count = db.Column(db.Integer, default=0)           # 当代帕累托解数量
    best_time = db.Column(db.Numeric(10, 2))                   # 当代最短时间
    best_cost = db.Column(db.Numeric(10, 2))                   # 当代最低费用
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    plan = db.relationship("Plan", backref="iteration_logs")


# ===========================================================================
# 🆕 S5：出行提示（论文 4.6 节）— 按途经城市匹配提示卡
# ===========================================================================
class Tip(db.Model):
    """出行提示：按城市 + 分类（人群/交通/贴士/综合）匹配"""
    __tablename__ = "tip"

    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(40), nullable=False, index=True)        # 适用城市（或 "全国"）
    category = db.Column(db.String(20), nullable=False)                 # crowd/transit/tips/general
    title = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, default=50)                        # 1-100，越大越靠前
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ===========================================================================
# 🆕 S6：交通方式打分（论文 4.7 节）— 使用-打分-优化闭环
# ===========================================================================
class Rating(db.Model):
    """用户对某次规划中某交通方式的打分（-2~+2，0 中性）
    用于 NSGA-II 体验惩罚修正：均值打分 ±40"""
    __tablename__ = "rating"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("plans.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    mode = db.Column(db.String(20), nullable=False)                  # 驾车/公交/步行/高铁...
    score = db.Column(db.Integer, nullable=False)                     # -2 ~ +2，0 中性
    comment = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="ratings")
    plan = db.relationship("Plan", backref="ratings")


# ===========================================================================
# 🆕 S7：路线广场（论文 4.8 节）— 分享 + 点赞 + 收藏 + 推荐
# ===========================================================================
class SharedRoute(db.Model):
    """路线广场：用户分享的路线（可被点赞/收藏）"""
    __tablename__ = "shared_route"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    title = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(500))
    origin_name = db.Column(db.String(40))
    dest_name = db.Column(db.String(40))
    route_data = db.Column(db.JSON)                  # 完整路线数据（含 steps）
    likes = db.Column(db.Integer, default=0)
    favorites_count = db.Column(db.Integer, default=0)
    is_public = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="shared_routes")


class UserFavorite(db.Model):
    """用户收藏的共享路线（区别于 plans 的 favorites，专属于共享路线）"""
    __tablename__ = "user_favorite"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    shared_route_id = db.Column(db.Integer, db.ForeignKey("shared_route.id", ondelete="CASCADE"),
                                 nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "shared_route_id",
                                           name="uk_user_shared_route"),)

    route = db.relationship("SharedRoute", backref="favorited_by")
