"""
全局配置文件
"""
import os


class Config:
    # MySQL 连接（用户已建库 travel_planner2）
    SQLALCHEMY_DATABASE_URI = (
        "mysql+pymysql://root:123456@127.0.0.1:3306/travel_planner2?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_size": 10,
        "pool_recycle": 3600,
    }

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET", "travel_planner2_demo_secret")
    JWT_ACCESS_TOKEN_EXPIRES = 60 * 60 * 12  # 12h

    # NSGA-II 默认参数
    NSGA2_POP_SIZE = 100
    NSGA2_MAX_GEN = 150
    NSGA2_MUTATION_RATE = 0.15
    NSGA2_CROSSOVER_RATE = 0.9

    # 返回的 Pareto 解集上限（前端一次不展示太多）
    PARETO_TOP_N = 5
