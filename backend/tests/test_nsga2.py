"""
NSGA-II 算法核心测试（论文 TC-300 ~ TC-313）
- TC-300: Individual 支配关系正确
- TC-301: 非支配排序分层正确
- TC-302: 拥挤度边界个体为 inf
- TC-303: 候选集版 NSGA-II 返回非空帕累托前沿
- TC-304: HV 指标计算正确
- TC-305: 四类代表方案提取正确
- TC-306: 体验惩罚公式（驾车/公交/步行）
- TC-307: 时间归一化（最快0 最慢40）
- TC-308: 用户打分修正（+2→-40, -2→+20）
- TC-309: NSGA-II 参数（pop20/gen15）
- TC-310: 迭代日志每代快照
- TC-311: 单段规划（无中间点）
- TC-312: 多段规划（有中间点）
- TC-313: 候选集为空时 NSGA-II 安全返回
"""
import random
from tests.base import BaseTestCase
from app.algorithms.nsga2 import (
    Individual, non_dominated_sort, calculate_crowding_distance,
    run_nsga2_candidates, extract_representative_solutions,
    _hypervolume_3d,
)
from app.utils.plan_service import (
    compute_discomfort, _apply_time_normalization,
    _apply_user_rating_correction, MODE_COMFORT,
)


class TestNSGA2(BaseTestCase):

    def test_tc300_dominance(self):
        """TC-300 支配关系：a 全<=b 且至少一个 <"""
        a = Individual([1, 2]); a.objectives = [10, 20, 30]
        b = Individual([1, 2]); b.objectives = [15, 25, 35]
        self.assertTrue(Individual.dominates(a, b))
        self.assertFalse(Individual.dominates(b, a))
        # 相等不算支配
        c = Individual([1, 2]); c.objectives = [10, 20, 30]
        self.assertFalse(Individual.dominates(a, c))

    def test_tc301_non_dominated_sort(self):
        """TC-301 非支配排序分层"""
        inds = []
        for obj in [[1, 5, 5], [5, 1, 5], [5, 5, 1],
                    [3, 3, 3], [6, 6, 6]]:
            ind = Individual([])
            ind.objectives = obj
            inds.append(ind)
        fronts = non_dominated_sort(inds)
        # rank0: [1,5,5],[5,1,5],[5,5,1],[3,3,3]（互不支配：[3,3,3] 与其他三个均不互相支配）
        self.assertEqual(len(fronts[0]), 4)
        # rank1: [6,6,6]（被所有 rank0 支配）
        self.assertGreaterEqual(len(fronts), 2)
        self.assertEqual(len(fronts[-1]), 1)

    def test_tc302_crowding_distance_boundary(self):
        """TC-302 拥挤度边界个体 = inf"""
        inds = []
        for obj in [[1, 1, 1], [2, 2, 2], [3, 3, 3]]:
            ind = Individual([]); ind.objectives = obj
            inds.append(ind)
        calculate_crowding_distance(inds)
        self.assertEqual(inds[0].crowding_distance, float("inf"))
        self.assertEqual(inds[-1].crowding_distance, float("inf"))

    def test_tc303_candidates_nsga2(self):
        """TC-303 候选集版 NSGA-II 返回非空帕累托前沿"""
        random.seed(42)
        segments = [
            [{"time": 30, "money": 50, "discomfort": 5, "mode": "驾车"},
             {"time": 60, "money": 30, "discomfort": 10, "mode": "公交"},
             {"time": 180, "money": 5, "discomfort": 15, "mode": "步行"}],
            [{"time": 20, "money": 40, "discomfort": 5, "mode": "驾车"},
             {"time": 50, "money": 25, "discomfort": 10, "mode": "公交"}],
        ]
        pareto, logs, pop = run_nsga2_candidates(segments, pop_size=20, max_gen=15,
                                            cross_prob=0.9, mut_prob=0.3)
        self.assertGreater(len(pareto), 0)
        # 每个个体 objectives 是 3 个值
        for ind in pareto:
            self.assertEqual(len(ind.objectives), 3)

    def test_tc304_hypervolume(self):
        """TC-304 HV 指标：3 点 [0,0,0],[1,1,1],[2,2,2] ref[3,3,3] = 27"""
        points = [[0, 0, 0], [1, 1, 1], [2, 2, 2]]
        ref = [3, 3, 3]
        hv = _hypervolume_3d(points, ref)
        self.assertAlmostEqual(hv, 27.0, places=2)

    def test_tc305_extract_representatives(self):
        """TC-305 四类代表方案提取"""
        random.seed(42)
        segments = [
            [{"time": 30, "money": 50, "discomfort": 5, "mode": "驾车"},
             {"time": 60, "money": 30, "discomfort": 10, "mode": "公交"},
             {"time": 180, "money": 5, "discomfort": 15, "mode": "步行"}],
            [{"time": 20, "money": 40, "discomfort": 5, "mode": "驾车"},
             {"time": 50, "money": 25, "discomfort": 10, "mode": "公交"}],
        ]
        pareto, _, _ = run_nsga2_candidates(segments, pop_size=20, max_gen=15)
        reps = extract_representative_solutions(pareto)
        labels = [ind.solution_label for ind in reps]
        # 代表方案去重：当多个目标最优集中在同一个体时，标签数可能 < 4
        valid_labels = {"最省时", "最省钱", "体验最优", "均衡型"}
        self.assertGreater(len(labels), 0)
        self.assertTrue(set(labels).issubset(valid_labels))
        self.assertIn("最省时", labels)

    def test_tc306_discomfort_formula(self):
        """TC-306 体验惩罚公式：舒适度+换乘惩罚"""
        # 驾车 base=5，无换乘
        self.assertEqual(compute_discomfort("驾车", 0, None, 0), 5)
        # 公交 base=10，2换乘=16
        self.assertEqual(compute_discomfort("公交", 2, None, 0), 10 + 16)
        # 步行 base=15
        self.assertEqual(compute_discomfort("步行", 0, None, 0), 15)

    def test_tc307_time_normalization(self):
        """TC-307 时间归一化：最快0 最慢40"""
        segments = [[
            {"time": 30, "discomfort": 5, "_base_discomfort": 5, "mode": "驾车"},
            {"time": 60, "discomfort": 10, "_base_discomfort": 10, "mode": "公交"},
            {"time": 180, "discomfort": 15, "_base_discomfort": 15, "mode": "步行"},
        ]]
        _apply_time_normalization(segments)
        # 驾车最快 → time_norm=0
        self.assertEqual(segments[0][0]["discomfort"], 5)
        # 步行最慢 → time_norm=40
        self.assertEqual(segments[0][2]["discomfort"], 15 + 40)
        # 公交中间 → time_norm = (60-30)/(180-30)*40 = 8
        self.assertAlmostEqual(segments[0][1]["discomfort"], 10 + 8, places=1)

    def test_tc308_user_rating_correction(self):
        """TC-308 用户打分修正：+2→-40, -2→+40"""
        segments = [[
            {"time": 30, "discomfort": 5, "_base_discomfort": 5, "mode": "驾车"},
            {"time": 60, "discomfort": 10, "_base_discomfort": 10, "mode": "公交"},
        ]]
        _apply_user_rating_correction(segments, {"驾车": 2, "公交": -2})
        # 驾车 rating+2 → -40
        self.assertEqual(segments[0][0]["discomfort"], 5 - 40)
        # 公交 rating-2 → +40
        self.assertEqual(segments[0][1]["discomfort"], 10 + 40)

    def test_tc309_nsga2_params(self):
        """TC-309 NSGA-II 参数 pop20/gen15"""
        random.seed(42)
        segments = [[
            {"time": 30, "money": 50, "discomfort": 5, "mode": "驾车"},
            {"time": 60, "money": 30, "discomfort": 10, "mode": "公交"},
        ]]
        _, logs, _ = run_nsga2_candidates(segments, pop_size=20, max_gen=15,
                                       cross_prob=0.9, mut_prob=0.3, collect_logs=True)
        # gen 从 0 到 15（含终代），共 16 条
        self.assertGreaterEqual(len(logs), 15)
        self.assertLessEqual(len(logs), 17)

    def test_tc310_iteration_logs(self):
        """TC-310 迭代日志每代含 hv/pareto_count/best_time/best_cost"""
        random.seed(42)
        segments = [[
            {"time": 30, "money": 50, "discomfort": 5, "mode": "驾车"},
            {"time": 60, "money": 30, "discomfort": 10, "mode": "公交"},
        ]]
        _, logs, _ = run_nsga2_candidates(segments, collect_logs=True)
        for log in logs:
            self.assertIn("gen", log)
            self.assertIn("hv", log)
            self.assertIn("pareto_count", log)
            self.assertIn("best_time", log)
            self.assertIn("best_cost", log)

    def test_tc311_single_segment(self):
        """TC-311 单段规划（无中间点）"""
        random.seed(42)
        segments = [[
            {"time": 30, "money": 50, "discomfort": 5, "mode": "驾车"},
            {"time": 60, "money": 30, "discomfort": 10, "mode": "公交"},
        ]]
        pareto, _, _ = run_nsga2_candidates(segments, pop_size=10, max_gen=5)
        self.assertGreater(len(pareto), 0)
        # 每个个体 1 个段
        for ind in pareto:
            self.assertEqual(len(ind.segments), 1)

    def test_tc312_multi_segment(self):
        """TC-312 多段规划（3 段）"""
        random.seed(42)
        segments = [
            [{"time": 10, "money": 5, "discomfort": 2, "mode": "步行"},
             {"time": 5, "money": 10, "discomfort": 1, "mode": "驾车"}],
            [{"time": 20, "money": 15, "discomfort": 3, "mode": "公交"},
             {"time": 15, "money": 20, "discomfort": 2, "mode": "驾车"}],
            [{"time": 30, "money": 25, "discomfort": 5, "mode": "驾车"},
             {"time": 40, "money": 10, "discomfort": 8, "mode": "公交"}],
        ]
        pareto, _, _ = run_nsga2_candidates(segments, pop_size=20, max_gen=10)
        self.assertGreater(len(pareto), 0)
        for ind in pareto:
            self.assertEqual(len(ind.segments), 3)

    def test_tc313_empty_candidates(self):
        """TC-313 候选集含空段时安全返回（过滤空段）"""
        random.seed(42)
        segments = [
            [{"time": 10, "money": 5, "discomfort": 2, "mode": "步行"}],
            [],  # 空段
        ]
        pareto, _, _ = run_nsga2_candidates(segments, pop_size=10, max_gen=5)
        # 应过滤掉空段后正常运行，或返回空
        self.assertIsInstance(pareto, list)
