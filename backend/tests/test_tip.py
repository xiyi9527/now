"""
出行提示模块测试（论文 TC-060 ~ TC-070）
- TC-060: 按城市匹配提示
- TC-061: 全国通用提示也返回
- TC-062: 按 category 过滤
- TC-063: 单城市推荐
- TC-064: 缺少 cities 参数 400
"""
from tests.base import BaseTestCase


class TestTip(BaseTestCase):

    def test_tc060_match_by_city(self):
        """TC-060 匹配安顺+宜宾的提示"""
        r = self.get("/api/tip/match?cities=安顺,宜宾")
        d = self.assert_ok(r)
        groups = d["data"]["groups"]
        self.assertIn("安顺", groups)
        self.assertIn("宜宾", groups)
        self.assertGreater(len(groups["安顺"]), 0)
        self.assertGreater(len(groups["宜宾"]), 0)

    def test_tc061_match_includes_national(self):
        """TC-061 全国通用提示也返回"""
        r = self.get("/api/tip/match?cities=安顺")
        d = r.get_json()
        groups = d["data"]["groups"]
        self.assertIn("全国", groups)
        self.assertGreater(len(groups["全国"]), 0)

    def test_tc062_match_by_category(self):
        """TC-062 按 category=transit 过滤"""
        r = self.get("/api/tip/match?cities=安顺&category=transit")
        d = r.get_json()
        groups = d["data"]["groups"]
        for tips in groups.values():
            for t in tips:
                self.assertEqual(t["category"], "transit")

    def test_tc063_recommend_single_city(self):
        """TC-063 单城市推荐（默认 limit=5）"""
        r = self.get("/api/tip/recommend?city=宜宾")
        d = self.assert_ok(r)
        self.assertLessEqual(len(d["data"]), 5)
        self.assertGreater(len(d["data"]), 0)
        # priority 降序
        pris = [t["priority"] for t in d["data"]]
        self.assertEqual(pris, sorted(pris, reverse=True))

    def test_tc064_match_missing_cities(self):
        """TC-064 缺少 cities 参数 → 400"""
        r = self.get("/api/tip/match")
        self.assertEqual(r.status_code, 400)
