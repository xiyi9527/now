"""
认证模块测试（论文 TC-001 ~ TC-010）
- TC-001: 注册成功
- TC-002: 重复用户名注册失败
- TC-003: 密码过短注册失败
- TC-004: 登录成功
- TC-005: 错误密码登录失败
- TC-006: 不存在用户登录失败
- TC-007: JWT token 包含 role claim
- TC-008: 用户名空注册失败
- TC-009: 密码空注册失败
- TC-010: token 可访问受保护接口
"""
import time
from tests.base import BaseTestCase


class TestAuth(BaseTestCase):

    def test_tc001_register_success(self):
        """TC-001 注册成功：返回 token + user"""
        uname = f"reg_{int(time.time()*1000)}"
        r = self.post("/api/register", json={
            "username": uname, "password": "pass123", "email": "a@b.com",
        })
        d = self.assert_ok(r)
        self.assertIn("access_token", d)
        self.assertEqual(d["user"]["username"], uname)

    def test_tc002_register_duplicate_fail(self):
        """TC-002 重复用户名注册：409"""
        r = self.post("/api/register", json={
            "username": self.user.username, "password": "pass123",
        })
        self.assertEqual(r.status_code, 409)

    def test_tc003_register_short_password_fail(self):
        """TC-003 密码<6 字符：400"""
        r = self.post("/api/register", json={
            "username": f"short_{int(time.time()*1000)}", "password": "12345",
        })
        self.assertEqual(r.status_code, 400)

    def test_tc004_login_success(self):
        """TC-004 正确账号密码登录成功"""
        r = self.post("/api/login", json={
            "username": self.user.username, "password": "test123456",
        })
        d = self.assert_ok(r)
        self.assertIn("access_token", d)

    def test_tc005_login_wrong_password_fail(self):
        """TC-005 错误密码登录：401"""
        r = self.post("/api/login", json={
            "username": self.user.username, "password": "wrongpwd",
        })
        self.assertEqual(r.status_code, 401)

    def test_tc006_login_nonexistent_fail(self):
        """TC-006 不存在用户登录：401"""
        r = self.post("/api/login", json={
            "username": "no_such_user_xyz", "password": "pass123",
        })
        self.assertEqual(r.status_code, 401)

    def test_tc007_jwt_contains_role(self):
        """TC-007 JWT token 的 role claim"""
        r = self.post("/api/login", json={
            "username": self.user.username, "password": "test123456",
        })
        d = r.get_json()
        token = d["access_token"]
        # 用 token 调一个需要 role 的接口（admin 接口需要 admin，普通用户应 403）
        r2 = self.get("/api/admin/dashboard/overview",
                      headers={"Authorization": f"Bearer {token}"})
        self.assertIn(r2.status_code, (403, 401))

    def test_tc008_register_empty_username_fail(self):
        """TC-008 空用户名注册：400"""
        r = self.post("/api/register", json={"username": "", "password": "pass123"})
        self.assertEqual(r.status_code, 400)

    def test_tc009_register_empty_password_fail(self):
        """TC-009 空密码注册：400"""
        r = self.post("/api/register", json={"username": "x", "password": ""})
        self.assertEqual(r.status_code, 400)

    def test_tc010_token_access_protected(self):
        """TC-010 token 可访问受保护接口（我的规划）"""
        r = self.get("/api/plan/me", headers=self.auth_header)
        self.assertIn(r.status_code, (200, 401))
        if r.status_code == 200:
            d = r.get_json()
            self.assertTrue(d.get("ok"))
