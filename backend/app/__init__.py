"""
应用工厂
"""
from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager

db = SQLAlchemy()
jwt = JWTManager()


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    # 扩展初始化
    db.init_app(app)
    jwt.init_app(app)
    CORS(app, supports_credentials=True)

    # 注册蓝图
    from app.views import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    # 🔐 管理员后台 API — 前缀 /api/admin
    from app.admin_bp import admin_bp
    app.register_blueprint(admin_bp, url_prefix="/api/admin")

    # 🆕 S5: 出行提示 — 前缀 /api/tip
    from app.tip_bp import tip_bp
    app.register_blueprint(tip_bp, url_prefix="/api/tip")

    return app
