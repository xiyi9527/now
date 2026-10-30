"""
打分闭环模块测试（论文 TC-080 ~ TC-090）
- TC-080: 提交打分成功
- TC-081: score 超出范围 -2~+2 失败
- TC-082: 重复提交覆盖更新
- TC-083: 用户均分接口
- TC-084: 规划的打分查询
"""
from tests.base import BaseTestCase
from app import db
from app.models import Plan, Rating


class TestRating(BaseTestCase):

    def _make_plan(self):
        p = Plan(
            user_id=self.user.id, start_city_id=1, end_city_id=2,
            spot_ids="1", total_time=100, total_money=50,
            total_discomfort=10, route_detail={}, is_public=False,
        )
        db.session.add(p)
        db.session.commit()
        return p

    def test_tc080_submit_rating(self):
        """TC-080 提交打分成功"""
        p = self._make_plan()
        r = self.post("/api/rate", json={
            "plan_id": p.id, "mode": "驾车", "score": 2, "comment": "舒适",
        }, headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertEqual(d["data"]["score"], 2)
        self.assertEqual(d["data"]["mode"], "驾车")

    def test_tc081_score_out_of_range(self):
        """TC-081 score=3 超出范围 → 400"""
        p = self._make_plan()
        r = self.post("/api/rate", json={
            "plan_id": p.id, "mode": "驾车", "score": 3,
        }, headers=self.auth_header)
        self.assertEqual(r.status_code, 400)

    def test_tc082_rating_override(self):
        """TC-082 同一 plan+mode 重复提交覆盖更新"""
        p = self._make_plan()
        # 第一次 +2
        self.post("/api/rate", json={"plan_id": p.id, "mode": "驾车", "score": 2},
                  headers=self.auth_header)
        # 第二次 -1
        r = self.post("/api/rate", json={"plan_id": p.id, "mode": "驾车", "score": -1},
                      headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertEqual(d["data"]["score"], -1)
        # DB 只有一条
        cnt = Rating.query.filter_by(user_id=self.user.id, plan_id=p.id, mode="驾车").count()
        self.assertEqual(cnt, 1)

    def test_tc083_user_means(self):
        """TC-083 用户均分接口"""
        p = self._make_plan()
        self.post("/api/rate", json={"plan_id": p.id, "mode": "驾车", "score": 2},
                  headers=self.auth_header)
        self.post("/api/rate", json={"plan_id": p.id, "mode": "公交", "score": -1},
                  headers=self.auth_header)
        r = self.get("/api/rate/user-means", headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertIn("驾车", d["data"])
        self.assertIn("公交", d["data"])
        self.assertEqual(d["data"]["驾车"], 2.0)
        self.assertEqual(d["data"]["公交"], -1.0)

    def test_tc084_plan_ratings(self):
        """TC-084 查询某规划的打分"""
        p = self._make_plan()
        self.post("/api/rate", json={"plan_id": p.id, "mode": "驾车", "score": 1},
                  headers=self.auth_header)
        r = self.get(f"/api/rate/plan/{p.id}", headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertGreaterEqual(len(d["data"]), 1)
        self.assertEqual(d["data"][0]["mode"], "驾车")
