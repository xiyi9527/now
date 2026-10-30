"""
路线广场模块测试（论文 TC-100 ~ TC-120）
- TC-100: 分享路线到广场
- TC-101: 广场列表（推荐排序）
- TC-102: 路线详情
- TC-103: 点赞
- TC-104: 收藏（幂等切换）
- TC-105: 一键应用
- TC-106: 搜索
"""
from tests.base import BaseTestCase
from app import db
from app.models import Plan, SharedRoute


class TestPlaza(BaseTestCase):

    def _make_plan(self):
        p = Plan(
            user_id=self.user.id, start_city_id=1, end_city_id=2,
            spot_ids="1", total_time=120, total_money=60,
            total_discomfort=8, route_detail={
                "start_city_id": 1, "end_city_id": 2, "spot_ids": [1],
                "total_time": 120, "total_money": 60, "total_discomfort": 8,
                "steps": [{"mode": "驾车", "from_name": "A", "to_name": "B"}],
            }, is_public=False,
        )
        db.session.add(p)
        db.session.commit()
        return p

    def _share_route(self, title="S8测试路线"):
        p = self._make_plan()
        r = self.post("/api/plaza/share", json={
            "plan_id": p.id, "title": title,
            "description": "测试", "origin_name": "A", "dest_name": "B",
        }, headers=self.auth_header)
        return r.get_json()["data"]["id"]

    def test_tc100_share_route(self):
        """TC-100 分享路线成功"""
        sid = self._share_route()
        self.assertIsInstance(sid, int)

    def test_tc101_plaza_list(self):
        """TC-101 广场列表（推荐排序）"""
        self._share_route("S8排序测试")
        r = self.get("/api/plaza/list?sort=recommend")
        d = self.assert_ok(r)
        self.assertGreaterEqual(len(d["data"]), 1)
        # 推荐排序：score = favs*2 + likes 降序
        scores = [x["score"] for x in d["data"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_tc102_route_detail(self):
        """TC-102 路线详情含 route_data"""
        sid = self._share_route()
        r = self.get(f"/api/plaza/{sid}")
        d = self.assert_ok(r)
        self.assertIn("route_data", d["data"])
        self.assertIn("steps", d["data"]["route_data"])

    def test_tc103_like(self):
        """TC-103 点赞 +1"""
        sid = self._share_route()
        r = self.post(f"/api/plaza/{sid}/like", headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertEqual(d["likes"], 1)

    def test_tc104_favorite_toggle(self):
        """TC-104 收藏幂等切换"""
        sid = self._share_route()
        # 收藏
        r1 = self.post(f"/api/plaza/{sid}/favorite", headers=self.auth_header)
        d1 = self.assert_ok(r1)
        self.assertTrue(d1["favorited"])
        self.assertEqual(d1["favorites_count"], 1)
        # 再点取消
        r2 = self.post(f"/api/plaza/{sid}/favorite", headers=self.auth_header)
        d2 = self.assert_ok(r2)
        self.assertFalse(d2["favorited"])
        self.assertEqual(d2["favorites_count"], 0)

    def test_tc105_apply(self):
        """TC-105 一键应用生成新规划"""
        sid = self._share_route()
        r = self.post(f"/api/plaza/{sid}/apply", headers=self.auth_header)
        self.assertIn(r.status_code, (200, 201))
        d = r.get_json()
        self.assertTrue(d["ok"])
        self.assertIn("plan_id", d["data"])

    def test_tc106_search(self):
        """TC-106 关键词搜索"""
        self._share_route("S8搜索专用路线")
        r = self.get("/api/plaza/list?q=S8搜索专用")
        d = self.assert_ok(r)
        self.assertGreaterEqual(len(d["data"]), 1)
        self.assertTrue(any("S8搜索专用" in x["title"] for x in d["data"]))
