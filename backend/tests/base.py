"""
测试基类：提供 Flask app / test_client / 测试用户创建与清理
所有测试用例都应继承 BaseTestCase
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from app import create_app, db
from app.models import User, Plan, Rating, SharedRoute, UserFavorite, Solution, IterationLog

TEST_USERNAME = "test_case_user"
TEST_PASSWORD = "test123456"


class BaseTestCase(unittest.TestCase):
    """所有 API 测试的基类"""

    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app_context = cls.app.app_context()
        cls.app_context.push()

    @classmethod
    def tearDownClass(cls):
        cls.app_context.pop()

    def setUp(self):
        self.client = self.app.test_client()
        # 确保测试用户存在（可重复运行）
        self.user = User.query.filter_by(username=TEST_USERNAME).first()
        if not self.user:
            self.user = User(
                username=TEST_USERNAME,
                password_hash=generate_password_hash(TEST_PASSWORD, method="pbkdf2"),
                email="test@example.com",
                role="user",
            )
            db.session.add(self.user)
            db.session.commit()
        else:
            # 重置密码
            self.user.password_hash = generate_password_hash(TEST_PASSWORD, method="pbkdf2")
            db.session.commit()
        self.token = create_access_token(
            identity=str(self.user.id),
            additional_claims={"role": self.user.role or "user"},
        )
        self.auth_header = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        """清理本次测试产生的数据（用 test 用户关联的数据）"""
        uid = self.user.id
        # 按依赖顺序清理
        Solution.query.filter_by(plan_id=0).delete()  # 兜底
        IterationLog.query.filter(IterationLog.plan_id.in_(
            db.session.query(Plan.id).filter_by(user_id=uid)
        )).delete(synchronize_session=False)
        Solution.query.filter(Solution.plan_id.in_(
            db.session.query(Plan.id).filter_by(user_id=uid)
        )).delete(synchronize_session=False)
        Rating.query.filter_by(user_id=uid).delete()
        UserFavorite.query.filter_by(user_id=uid).delete()
        SharedRoute.query.filter_by(user_id=uid).delete()
        Plan.query.filter_by(user_id=uid).delete()
        db.session.commit()

    # ---- 辅助方法 ----
    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)

    def post(self, url, json=None, headers=None):
        return self.client.post(url, json=json, headers=headers)

    def assert_ok(self, resp, msg=None):
        data = resp.get_json()
        self.assertEqual(resp.status_code, 200, msg or f"期望 200 实际 {resp.status_code}: {resp.get_data(as_text=True)[:200]}")
        self.assertTrue(data.get("ok"), msg or f"ok 应为 True: {data}")
        return data
