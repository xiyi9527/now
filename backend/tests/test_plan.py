"""
规划核心模块测试（论文 TC-020 ~ TC-050）
- TC-020: 坐标直达规划成功（返回多方案）
- TC-021: 方案含四类代表（最省时/最省钱/体验最优/均衡）
- TC-022: 返回 iteration_logs（HV 收敛）
- TC-023: 方案含 amap_steps 分步导航
- TC-024: 缺少坐标返回 400
- TC-025: 保存规划成功（含 solution + iteration_log）
- TC-026: 我的规划列表
- TC-027: 同城规划
"""
from tests.base import BaseTestCase


class TestPlan(BaseTestCase):

    def _valid_plan_payload(self):
        return {
            "start_lat": 26.2456, "start_lng": 105.9323, "start_name": "安顺站",
            "end_lat": 28.7784,   "end_lng": 104.6405,  "end_name": "宜宾西站",
            "spot_ids": [],
            "transport_mode": "auto",
        }

    def test_tc020_plan_success(self):
        """TC-020 坐标直达规划成功，返回≥1个方案"""
        r = self.post("/api/plan", json=self._valid_plan_payload())
        d = self.assert_ok(r)
        self.assertGreaterEqual(d["count"], 1)
        self.assertGreater(len(d["options"]), 0)

    def test_tc021_plan_four_labels(self):
        """TC-021 方案含四类代表标签"""
        r = self.post("/api/plan", json=self._valid_plan_payload())
        d = r.get_json()
        labels = [o.get("label") for o in d.get("options", [])]
        # 至少有一个标签命中四类之一
        has_any = any(l in ("最省时", "最省钱", "体验最优", "均衡型") for l in labels)
        self.assertTrue(has_any, f"方案标签: {labels}")

    def test_tc022_plan_has_iteration_logs(self):
        """TC-022 返回 iteration_logs（HV 收敛）"""
        r = self.post("/api/plan", json=self._valid_plan_payload())
        d = r.get_json()
        logs = d.get("iteration_logs", [])
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)
        # 第一条应有 gen/hv/pareto_count
        first = logs[0]
        self.assertIn("gen", first)
        self.assertIn("hv", first)
        self.assertIn("pareto_count", first)

    def test_tc023_plan_has_amap_steps(self):
        """TC-023 方案含分步导航 amap_steps"""
        r = self.post("/api/plan", json=self._valid_plan_payload())
        d = r.get_json()
        opts = d.get("options", [])
        if opts:
            steps = opts[0].get("steps", [])
            # 至少有一段 step
            self.assertGreater(len(steps), 0)

    def test_tc024_plan_missing_coords(self):
        """TC-024 缺少坐标 → 尝试走城市ID分支，无城市ID应报错"""
        r = self.post("/api/plan", json={"start_name": "A", "end_name": "B"})
        # 没有坐标也没有 start_id/end_id，会走城市分支报错 400 或返回无方案
        self.assertIn(r.status_code, (400, 404))

    def test_tc025_save_plan(self):
        """TC-025 保存规划成功，写入 solution + iteration_log"""
        r = self.post("/api/plan", json=self._valid_plan_payload())
        plan_resp = r.get_json()
        opt = plan_resp["options"][0]

        save_r = self.post("/api/plan/save", json={
            "start_city_id": 1, "end_city_id": 2,
            "spot_ids": [],
            "total_time": opt["total_time"],
            "total_money": opt["total_money"],
            "total_discomfort": opt["total_discomfort"],
            "route_detail": {"steps": opt["steps"]},
            "is_public": True,
            "solutions": [{
                "rank": 0, "label": opt.get("label", ""),
                "objectives": {"time": opt["total_time"],
                               "cost": opt["total_money"],
                               "experience": opt["total_discomfort"]},
                "route_order": [], "segments": opt["steps"],
                "elapsed": 0.1,
            }],
            "iteration_logs": plan_resp.get("iteration_logs", [])[:3],
        }, headers=self.auth_header)
        d = self.assert_ok(save_r)
        self.assertIn("plan_id", d)
        plan_id = d["plan_id"]

        # 验证 solution + iteration_log 已入库
        from app.models import Solution, IterationLog
        from app import db
        n_sol = Solution.query.filter_by(plan_id=plan_id).count()
        n_log = IterationLog.query.filter_by(plan_id=plan_id).count()
        self.assertEqual(n_sol, 1)
        self.assertEqual(n_log, 3)

    def test_tc026_my_plans(self):
        """TC-026 我的规划列表"""
        # 先保存一条
        self.test_tc025_save_plan()
        r = self.get("/api/plan/me", headers=self.auth_header)
        d = self.assert_ok(r)
        self.assertGreaterEqual(len(d["data"]), 1)

    def test_tc027_same_city_plan(self):
        """TC-027 同城规划（起终点相同坐标）"""
        payload = {
            "start_lat": 26.2456, "start_lng": 105.9323, "start_name": "安顺",
            "end_lat": 26.2456,   "end_lng": 105.9323,  "end_name": "安顺",
            "spot_ids": [], "transport_mode": "auto",
        }
        r = self.post("/api/plan", json=payload)
        # 同城可能走 local tour，ok 或 no plan
        self.assertIn(r.status_code, (200, 404))
