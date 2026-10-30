"""
NSGA-II 多目标遗传算法（核心逻辑）

三个优化目标（均为 MIN 方向）：
  1. total_time      总旅行时间（分钟），含景点游览额外时间
  2. total_money     总金钱花费（元）
  3. total_discomfort 总不适感 = 乘车距离折算 + 换乘次数权重

编码方案：
  Individual.genes = [mid_idx_1, mid_idx_2, ..., mid_idx_k]   # 中间停靠城市索引的排列
  最终路径 = [start_idx] + genes + [end_idx]
  起点终点在交叉/变异中永远不被触碰，保证路径合法。

缺失边处理：
  成本矩阵用 np.inf 填充，路径中出现 inf 段则整条路径的目标值 = inf，
  评估时被自然淘汰（NSGA-II 里 inf 支配 inf 不成立，合法路径会支配非法路径）。
"""

import random
import time
import numpy as np

# 导入数据加载器（Flask 应用工厂注册后才能正常导入，run_nsga2 内部按需创建）
from app.utils.data_loader import DataLoader


# ---------------------------------------------------------------------------
# Individual
# ---------------------------------------------------------------------------
class Individual:
    __slots__ = (
        "genes", "objectives",
        "rank", "crowding_distance",
        "domination_count", "dominated_solutions",
        "start_idx", "end_idx", "loader", "elapsed",   # run_nsga2 运行后附加的元信息
        "segments", "solution_label",   # 候选集版附加：各段选中的候选 / 四类标签
    )

    def __init__(self, genes):
        self.genes = list(genes)        # 中间停靠城市索引的排列（不含 start/end）
        self.objectives = None          # [time, money, discomfort]
        self.rank = 0                   # 非支配等级（越小越优）
        self.crowding_distance = 0.0
        self.domination_count = 0
        self.dominated_solutions = []
        self.segments = None            # 候选集版：List[dict] 各段选中的候选
        self.solution_label = ""        # 四类标签：最省时/最省钱/体验最优/均衡型

    # ---- 路径还原 -----------------------------------------------------------
    def full_path(self, start_idx, end_idx):
        """过滤掉占位符 -1 和重复的 start/end 节点后，返回完整路径 idx 列表。"""
        real = [g for g in self.genes if g != -1 and g != start_idx and g != end_idx]
        return [start_idx] + real + [end_idx]

    # ---- 支配关系 -----------------------------------------------------------
    @staticmethod
    def dominates(a, b):
        """a 是否支配 b：a 在所有目标上 <= b，且至少一个 < b。"""
        if a.objectives is None or b.objectives is None:
            return False
        at = a.objectives
        bt = b.objectives
        less_or_eq = all(at[i] <= bt[i] for i in range(len(at)))
        strictly_less = any(at[i] < bt[i] for i in range(len(at)))
        return less_or_eq and strictly_less

    def __repr__(self):
        return f"Ind(len={len(self.genes)}, obj={self.objectives})"


# ---------------------------------------------------------------------------
# 评估
# ---------------------------------------------------------------------------
def evaluate(individual, loader, start_idx, end_idx,
             spot_time_bonus=0, is_driving=False):
    """
    计算 individual 的三个目标值。
    loader:   DataLoader 实例（numpy 矩阵已缓存）
    spot_time_bonus: 景点游览附加时间（分钟）
    is_driving: 目前在评估中不改变成本，只在变异阶段使用
    """
    path = individual.full_path(start_idx, end_idx)

    total_time = 0.0
    total_money = 0.0
    total_discomfort = 0.0

    time_m = loader.time_matrix
    money_m = loader.money_matrix
    dis_m = loader.discomfort_matrix

    infeasible = False
    for i in range(len(path) - 1):
        a, b = path[i], path[i + 1]
        t = time_m[a][b]
        m = money_m[a][b]
        d = dis_m[a][b]
        if t == np.inf or m == np.inf:
            infeasible = True
            break
        total_time += t
        total_money += m
        total_discomfort += d

    if infeasible:
        individual.objectives = [np.inf, np.inf, np.inf]
        return

    total_time += spot_time_bonus
    individual.objectives = [total_time, total_money, total_discomfort]


# ---------------------------------------------------------------------------
# 快速非支配排序
# ---------------------------------------------------------------------------
def non_dominated_sort(population):
    """
    对 population 进行快速非支配排序。
    给每个个体设置 rank 属性，返回 fronts 列表（fronts[0] = rank 0 的个体列表）。
    """
    for p in population:
        p.domination_count = 0
        p.dominated_solutions = []

    for i, p in enumerate(population):
        for j, q in enumerate(population):
            if i == j:
                continue
            if Individual.dominates(p, q):
                p.dominated_solutions.append(q)
            elif Individual.dominates(q, p):
                p.domination_count += 1

    fronts = [[]]
    for p in population:
        if p.domination_count == 0:
            p.rank = 0
            fronts[0].append(p)

    f = 0
    while fronts[f]:
        next_front = []
        for p in fronts[f]:
            for q in p.dominated_solutions:
                q.domination_count -= 1
                if q.domination_count == 0:
                    q.rank = f + 1
                    next_front.append(q)
        f += 1
        fronts.append(next_front)

    # 末尾可能有空列表，剔除
    while fronts and not fronts[-1]:
        fronts.pop()
    return fronts


# ---------------------------------------------------------------------------
# 拥挤度计算
# ---------------------------------------------------------------------------
def calculate_crowding_distance(front):
    """对一个 front 内的个体计算 crowding_distance。边界个体 = +inf 保证保留。"""
    n = len(front)
    if n == 0:
        return
    for p in front:
        p.crowding_distance = 0.0
    if n <= 2:
        for p in front:
            p.crowding_distance = float("inf")
        return

    n_obj = len(front[0].objectives)
    for m in range(n_obj):
        # 按第 m 个目标升序
        front.sort(key=lambda x: x.objectives[m])
        # 边界个体
        front[0].crowding_distance = float("inf")
        front[-1].crowding_distance = float("inf")

        obj_min = front[0].objectives[m]
        obj_max = front[-1].objectives[m]
        if obj_max == obj_min:
            continue
        norm = obj_max - obj_min

        for i in range(1, n - 1):
            prev = front[i - 1].objectives[m]
            nxt = front[i + 1].objectives[m]
            front[i].crowding_distance += (nxt - prev) / norm


# ---------------------------------------------------------------------------
# 选择（基于 rank + crowding_distance 的二元锦标赛）
# ---------------------------------------------------------------------------
def tournament_select(population, k=2):
    """二元锦标赛：随机挑 k 个，按 rank 选最优；rank 相同按 crowding_distance 选最大。"""
    cand = random.sample(population, k)
    best = min(cand, key=lambda x: (x.rank, -x.crowding_distance))
    return best


# ---------------------------------------------------------------------------
# OX 顺序交叉（Order Crossover）—— TSP 类问题的标准算子，天然保持排列性质
# ---------------------------------------------------------------------------
def crossover(parent1, parent2):
    """
    OX 交叉：child1 继承 parent1 的 [cut1, cut2) 片段，
    剩余位置按 parent2 中未出现过的元素依次填入。
    不会产生重复元素。
    """
    g1 = list(parent1.genes)
    g2 = list(parent2.genes)
    n = len(g1)
    if n != len(g2) or n < 2:
        return Individual(g1), Individual(g2)

    cut1, cut2 = sorted(random.sample(range(n), 2))
    if cut1 == cut2:
        cut2 = min(n, cut1 + 1)

    def _ox(g_from, g_template):
        """从 g_template 切 [cut1,cut2)，其余位置按 g_from 顺序填未出现过的。"""
        seg = g_template[cut1:cut2]
        seg_set = set(seg)
        fill = [x for x in g_from if x not in seg_set]
        # 需要填的数量 = n - len(seg)
        need = n - len(seg)
        # 如果 fill 不够，用 -1 补齐（允许占位符重复）
        while len(fill) < need:
            fill.append(-1)
        fill = fill[:need]
        child = [None] * n
        child[cut1:cut2] = seg
        j = 0
        for i in range(n):
            if child[i] is None:
                child[i] = fill[j]
                j += 1
        return child

    child1 = _ox(g2, g1)   # child1 模板是 parent1，从 parent2 填
    child2 = _ox(g1, g2)
    return Individual(child1), Individual(child2)


# ---------------------------------------------------------------------------
# 交换变异
# ---------------------------------------------------------------------------
def mutate(individual, driving_allowed=False, free_pool=None):
    """
    交换变异：随机选两个有效位置交换。
    开车模式（driving_allowed=True）下，变异只在前 70% 的有效基因范围内。
    新增：50% 概率执行"插入变异"—— 把一个 -1 占位符替换成 free_pool 里随机一个值，
    或把一个有效值改成 -1。这样让种群在 0~MAX_MID 之间自然演化中间停靠数。
    """
    genes = individual.genes
    n = len(genes)
    if n < 1:
        return

    # 找有效位置（非占位符 -1）
    valid_positions = [i for i in range(n) if genes[i] != -1]
    empty_positions = [i for i in range(n) if genes[i] == -1]

    # === 插入变异（让中间停靠数能增能减）===
    if free_pool and random.random() < 0.4:
        if empty_positions and random.random() < 0.5:
            # 变多：随机把一个空位置填上
            genes[random.choice(empty_positions)] = random.choice(free_pool)
        elif valid_positions:
            # 变少：随机把一个有效位置清空
            genes[random.choice(valid_positions)] = -1
        return

    # === 交换变异 ===
    if len(valid_positions) < 2:
        return

    # 变异作用范围（只在有效位置中选）
    if driving_allowed and len(valid_positions) >= 3:
        upper = max(2, int(len(valid_positions) * 0.7))
        sel_range = valid_positions[:upper]
    else:
        sel_range = valid_positions

    if len(sel_range) < 2:
        return
    i, j = random.sample(sel_range, 2)
    genes[i], genes[j] = genes[j], genes[i]


# ---------------------------------------------------------------------------
# NSGA-II 主循环
# ---------------------------------------------------------------------------
def run_nsga2(city_list, pop_size=100, max_gen=150,
              spot_time_bonus=0, is_driving=False):
    """
    运行 NSGA-II，返回 Pareto 最优解集（rank == 0 的所有个体）。

    参数
    ----
    city_list: [start_city_id, end_city_id]  或  [start_city_id, ...中间..., end_city_id]
               外部调用者可以传中间景点（此时中间景点固定出现在路径里），
               也可以只传起止点让算法自由选中间停靠。
    pop_size:  种群大小（建议 50~200）
    max_gen:   迭代代数（建议 80~300，150 对 20 城市够用）
    spot_time_bonus: 景点游览附加时间（分钟）
    is_driving: True 则变异受限（见 mutate 文档）

    返回
    ----
    pareto: List[Individual]，rank == 0 的所有个体（Pareto 最优）
    """
    # ---- 0. 加载数据 + 解析 city_list -----------------------------------
    loader = DataLoader().load()
    assert len(city_list) >= 2, "city_list 至少需要 [start, end]"

    start_idx = loader.idx(city_list[0])
    end_idx = loader.idx(city_list[-1])

    # 固定中间景点（如果有）：city_list[1:-1] 这些 idx 必须出现在所有个体里
    fixed_mid = [loader.idx(cid) for cid in city_list[1:-1]]
    # 可自由选择的候选中间城市：必须从 start 可达 且 可达 end
    free_pool = loader.feasible_pool(start_idx, end_idx)
    # 去掉 fixed_mid 里已经占用的
    free_pool = [idx for idx in free_pool if idx not in fixed_mid]

    # 最大中间停靠数（OX 交叉需要统一长度，所以用占位符 -1 填充）
    MAX_MID = 4
    fixed_count = len(fixed_mid)
    free_slots = max(1, MAX_MID - fixed_count)   # 留给自由选择的空位数量

    # 如果没有可行中间城市，直接返回只有起点终点的一条路径
    if not free_pool and not fixed_mid:
        dummy = Individual([])
        evaluate(dummy, loader, start_idx, end_idx, spot_time_bonus, is_driving)
        dummy.start_idx = start_idx
        dummy.end_idx = end_idx
        dummy.loader = loader
        dummy.elapsed = 0
        return [dummy]

    # ---- 1. 初始化种群（多样化：0~free_slots 个有效中间停靠 + 直达 baseline）
    population = []

    # 1a. 直达 baseline（genes 全是 -1），保证始终有一个最短时间参考
    baseline_genes = fixed_mid + [-1] * free_slots
    random.shuffle(baseline_genes)
    base_ind = Individual(baseline_genes)
    evaluate(base_ind, loader, start_idx, end_idx, spot_time_bonus, is_driving)
    population.append(base_ind)

    # 1b. 多样化初始化：随机 k = 0~free_slots 个有效中间停靠
    for _ in range(pop_size - 1):
        k = random.randint(0, free_slots)
        chosen = random.sample(free_pool, min(k, len(free_pool))) if k > 0 else []
        genes = fixed_mid + chosen + [-1] * (free_slots - len(chosen))
        random.shuffle(genes)
        ind = Individual(genes)
        evaluate(ind, loader, start_idx, end_idx, spot_time_bonus, is_driving)
        population.append(ind)

    # ---- 2. 主循环 -------------------------------------------------------
    start_ts = time.time()
    for gen in range(max_gen):
        # 2.1 非支配排序 + 拥挤度
        fronts = non_dominated_sort(population)
        for front in fronts:
            calculate_crowding_distance(front)

        # 2.2 选择 + 交叉 + 变异，生成 offspring
        offspring = []
        while len(offspring) < pop_size:
            p1 = tournament_select(population)
            p2 = tournament_select(population)
            if random.random() < 0.9:
                c1, c2 = crossover(p1, p2)
            else:
                c1, c2 = Individual(p1.genes[:]), Individual(p2.genes[:])
            for c in (c1, c2):
                if random.random() < 0.18:
                    mutate(c, driving_allowed=is_driving, free_pool=free_pool)
                # 确保固定中间景点一定在里面（且不重复）
                for fm in fixed_mid:
                    if fm not in c.genes:
                        # 优先替换 -1 占位符；没有则换一个有效基因位置
                        if -1 in c.genes:
                            idx = c.genes.index(-1)
                        else:
                            # 随机换一个位置（不要把其他 fixed_mid 换掉）
                            non_fixed = [i for i, g in enumerate(c.genes)
                                         if g not in fixed_mid]
                            idx = random.choice(non_fixed) if non_fixed else 0
                        c.genes[idx] = fm
                # 去重：如果基因里有重复值（非占位符），把重复的改成 -1
                _fix_duplicates(c.genes, fixed_mid, free_pool)
                evaluate(c, loader, start_idx, end_idx, spot_time_bonus, is_driving)
                offspring.append(c)

        offspring = offspring[:pop_size]

        # 2.3 精英合并 (R_t = P_t ∪ Q_t) 再做一次非支配排序，截断到 pop_size
        combined = population + offspring
        fronts = non_dominated_sort(combined)
        for front in fronts:
            calculate_crowding_distance(front)

        new_pop = []
        for front in fronts:
            if len(new_pop) + len(front) <= pop_size:
                new_pop.extend(front)
            else:
                front_sorted = sorted(front, key=lambda x: -x.crowding_distance)
                take = pop_size - len(new_pop)
                new_pop.extend(front_sorted[:take])
                break
        population = new_pop

    elapsed = time.time() - start_ts

    # ---- 3. 返回 Pareto 前沿（rank 0 的所有个体）------------------------
    fronts = non_dominated_sort(population)
    pareto = fronts[0] if fronts else []
    pareto.sort(key=lambda x: x.objectives[0])

    # 附加元信息
    for ind in pareto:
        ind.start_idx = start_idx
        ind.end_idx = end_idx
        ind.loader = loader
        ind.elapsed = elapsed

    return pareto


def _fix_duplicates(genes, fixed_mid, free_pool):
    """去重：保留第一个出现的非 -1 值，后续重复的改成 -1。"""
    seen = set()
    for i in range(len(genes)):
        g = genes[i]
        if g == -1:
            continue
        if g in seen:
            genes[i] = -1
        else:
            seen.add(g)


# ===========================================================================
# 🆕 候选集版 NSGA-II（论文 4.3 节规格）
#
#   染色体：整数编码，genes[i] = 第 i 段选用的候选索引
#   三目标：f1 总耗时(分钟) f2 总费用(元) f3 体验惩罚(越小越好)
#   参数：pop_size=20, generations=15, cross_prob=0.9, mut_prob=0.3
#   高德 API 先取多种交通方式备选路线构成候选集，NSGA-II 在其上优化
# ===========================================================================

def _crossover_uniform(parent1, parent2):
    """均匀交叉：每个基因位等概率从父1或父2取（候选选择问题专用）。"""
    n = len(parent1.genes)
    if n == 0:
        return Individual(list(parent1.genes)), Individual(list(parent2.genes))
    g1, g2 = [], []
    for i in range(n):
        if random.random() < 0.5:
            g1.append(parent1.genes[i]); g2.append(parent2.genes[i])
        else:
            g1.append(parent2.genes[i]); g2.append(parent1.genes[i])
    return Individual(g1), Individual(g2)


def _mutate_random_reset(individual, candidate_counts, mut_prob=0.3):
    """随机重置变异：每个基因位以概率 mut_prob 重置为该段的随机有效候选索引。"""
    for i in range(len(individual.genes)):
        if candidate_counts[i] > 1 and random.random() < mut_prob:
            individual.genes[i] = random.randint(0, candidate_counts[i] - 1)


# ---------------------------------------------------------------------------
# 🆕 超体积指标（Hypervolume）— 论文 4.3.4 节迭代日志用
#   3 目标精确 HV（HSO 切片法 + 2D sweep）
# ---------------------------------------------------------------------------
def _hv_2d_union(points, ref_x, ref_y):
    """2D HV：points 矩形 [p, ref] 的并集面积。
    每个 point (x, y) 占据 [x, ref_x] × [y, ref_y]（最小化）。"""
    if not points:
        return 0.0
    arr = np.array(points, dtype=float)
    arr = arr[(arr[:, 0] < ref_x) & (arr[:, 1] < ref_y)]
    if len(arr) == 0:
        return 0.0
    arr = arr[np.argsort(arr[:, 0])]   # 按 x 升序

    total = 0.0
    prev_x = float(arr[0][0])
    min_y = ref_y   # 激活点中最小 y（矩形并集 = [min_y, ref_y]）
    for p in arr:
        x, y = float(p[0]), float(p[1])
        # 推进到 x 前，[prev_x, x] 段被覆盖（用当前 min_y，不含本点）
        if x > prev_x and min_y < ref_y:
            total += (x - prev_x) * (ref_y - min_y)
        min_y = min(min_y, y)
        prev_x = x
    if min_y < ref_y:
        total += (ref_x - prev_x) * (ref_y - min_y)
    return total


def _hypervolume_3d(pareto_objs, ref_point=None):
    """3D HV 精确计算（HSO 切片法）。
    pareto_objs: List[[f1, f2, f3]]（最小化）
    ref_point: 参考点（默认各目标最大值 *1.1 + 1，保证所有点在参考点之下）

    算法：按 f1 升序切片，每片 [f1_i, f1_{i+1}] 的 2D 区域 =
    所有点 j(f1_j <= f1_i) 在 (f2, f3) 平面矩形并集的面积。
    """
    if not pareto_objs:
        return 0.0
    arr = np.array(pareto_objs, dtype=float)
    if ref_point is None:
        ref = arr.max(axis=0) * 1.1 + 1.0
    else:
        ref = np.array(ref_point, dtype=float)

    # 过滤掉任何维度超过 ref 的点
    valid = arr[np.all(arr <= ref, axis=1)]
    if len(valid) == 0:
        return 0.0
    valid = valid[np.argsort(valid[:, 0])]   # 按 f1 升序

    hv = 0.0
    accumulated_2d = []   # 已扫过点的 (f2, f3)
    for i in range(len(valid)):
        f1_lo = valid[i][0]
        f1_hi = valid[i + 1][0] if i + 1 < len(valid) else ref[0]
        if f1_hi <= f1_lo:
            continue
        accumulated_2d.append([valid[i][1], valid[i][2]])
        area_2d = _hv_2d_union(accumulated_2d, ref[1], ref[2])
        hv += (f1_hi - f1_lo) * area_2d
    return round(hv, 4)


def _gen_snapshot(population, ref_point=None):
    """收集当代迭代日志：HV / pareto_count / best_time / best_cost"""
    fronts = non_dominated_sort(population)
    pareto = fronts[0] if fronts else []
    pareto_objs = [ind.objectives for ind in pareto if ind.objectives is not None]
    hv = _hypervolume_3d(pareto_objs, ref_point) if pareto_objs else 0.0
    best_time = min((o[0] for o in pareto_objs), default=float("inf"))
    best_cost = min((o[1] for o in pareto_objs), default=float("inf"))
    return {
        "hv": hv,
        "pareto_count": len(pareto),
        "best_time": round(float(best_time), 2) if best_time != float("inf") else None,
        "best_cost": round(float(best_cost), 2) if best_cost != float("inf") else None,
    }


def run_nsga2_candidates(segments_candidates,
                         pop_size=20, max_gen=15,
                         cross_prob=0.9, mut_prob=0.3,
                         spot_time_bonus=0,
                         collect_logs=True):
    """
    候选集版 NSGA-II（论文规格）。

    参数
    ----
    segments_candidates: List[List[dict]]
        每段一个候选列表，候选 dict 至少含 keys:
          time(分钟), money(元), discomfort(越小越好), mode, steps, amap_steps,
          polyline, route_coords, distance_km, tolls_yuan, from_name, to_name
        单段行程：外层 list 长度为 1。
    pop_size: 20（论文）
    max_gen:  15（论文）
    cross_prob: 0.9, mut_prob: 0.3（论文）
    spot_time_bonus: 景点游览附加时间（分钟，加到总时间上）
    collect_logs: 是否收集每代迭代日志（HV/pareto_count/best_time/best_cost）

    返回
    ----
    pareto: List[Individual]，genes = 各段选用的候选索引；
            每个个体附 .segments（拼接好的候选 dict 列表）和 .elapsed
    iteration_logs: List[dict]（仅当 collect_logs=True），每代一条
                    {gen, hv, pareto_count, best_time, best_cost}
    """
    n_seg = len(segments_candidates)
    if n_seg == 0:
        return ([], [], []) if collect_logs else ([], [])
    candidate_counts = [len(c) for c in segments_candidates]
    if any(c == 0 for c in candidate_counts):
        return ([], [], []) if collect_logs else ([], [])

    def _evaluate(ind):
        total_time = 0.0
        total_money = 0.0
        total_dis = 0.0
        picks = []
        for i, cand_idx in enumerate(ind.genes):
            cand = segments_candidates[i][cand_idx]
            total_time += cand.get("time", 0)
            total_money += cand.get("money", 0)
            total_dis += cand.get("discomfort", 0)
            picks.append(cand)
        total_time += spot_time_bonus
        ind.objectives = [total_time, total_money, total_dis]
        ind.segments = picks

    # 参考点：用初始种群目标最大值估算（每代固定参考点保证 HV 可比）。
    # 注意：目标是各段求和，不能用单段候选最大值，否则参考点远小于实际目标。
    iteration_logs = []

    # ---- 1. 初始化种群 ----
    population = []
    base = Individual([0] * n_seg)
    _evaluate(base)
    population.append(base)

    for _ in range(pop_size - 1):
        genes = [random.randint(0, c - 1) for c in candidate_counts]
        ind = Individual(genes)
        _evaluate(ind)
        population.append(ind)

    # 参考点 = 初始种群各目标最大值 *1.1 + 1（在种群初始化后计算）
    init_objs = np.array([ind.objectives for ind in population if ind.objectives is not None],
                          dtype=float)
    ref_point = init_objs.max(axis=0) * 1.1 + 1.0

    # ---- 2. 主循环 ----
    start_ts = time.time()
    for gen in range(max_gen):
        if collect_logs:
            snap = _gen_snapshot(population, ref_point)
            snap["gen"] = gen
            iteration_logs.append(snap)

        fronts = non_dominated_sort(population)
        for front in fronts:
            calculate_crowding_distance(front)

        offspring = []
        while len(offspring) < pop_size:
            p1 = tournament_select(population)
            p2 = tournament_select(population)
            if random.random() < cross_prob:
                c1, c2 = _crossover_uniform(p1, p2)
            else:
                c1, c2 = Individual(p1.genes[:]), Individual(p2.genes[:])
            for c in (c1, c2):
                if random.random() < mut_prob:
                    _mutate_random_reset(c, candidate_counts, mut_prob)
                _evaluate(c)
                offspring.append(c)
        offspring = offspring[:pop_size]

        combined = population + offspring
        fronts = non_dominated_sort(combined)
        for front in fronts:
            calculate_crowding_distance(front)

        new_pop = []
        for front in fronts:
            if len(new_pop) + len(front) <= pop_size:
                new_pop.extend(front)
            else:
                front_sorted = sorted(front, key=lambda x: -x.crowding_distance)
                new_pop.extend(front_sorted[:pop_size - len(new_pop)])
                break
        population = new_pop

    # 终代快照
    if collect_logs:
        snap = _gen_snapshot(population, ref_point)
        snap["gen"] = max_gen
        iteration_logs.append(snap)

    elapsed = time.time() - start_ts

    # ---- 3. 返回 Pareto 前沿 ----
    fronts = non_dominated_sort(population)
    pareto = fronts[0] if fronts else []
    pareto.sort(key=lambda x: x.objectives[0])
    for ind in pareto:
        ind.elapsed = elapsed

    if collect_logs:
        return pareto, iteration_logs, population
    return pareto, population


def extract_representative_solutions(pareto, population=None):
    """
    从 Pareto 前沿提取四类差异化方案（论文 4.3.4 节）：
      - 最省时（耗时最小）
      - 最省钱（费用最小）
      - 体验最优（不适感最小）
      - 均衡型（三目标归一化后综合最接近均值）

    当帕累托前沿解目标值过于集中（去重后 < 4）时，从整个 population 中
    补充差异化方案，保证用户至少看到 3-4 种选择。

    population: 可选，整个最终种群（用于补充非帕累托但有差异的解）。
    返回 List[Individual]，每个个体附 .solution_label 标签。
    """
    if not pareto:
        return []

    def _pick(pareto_pop, key_fn, label):
        return min(pareto_pop, key=lambda x: key_fn(x.objectives))

    fastest = _pick(pareto, lambda o: o[0], "最省时")
    cheapest = _pick(pareto, lambda o: o[1], "最省钱")
    best_exp = _pick(pareto, lambda o: o[2], "体验最优")

    # 均衡型：归一化后离均值向量最近
    objs = np.array([ind.objectives for ind in pareto], dtype=float)
    mins = objs.min(axis=0)
    maxs = objs.max(axis=0)
    ranges = np.where(maxs - mins < 1e-6, 1.0, maxs - mins)
    norm = (objs - mins) / ranges
    mean_vec = norm.mean(axis=0)
    balanced_idx = int(np.argmin(np.linalg.norm(norm - mean_vec, axis=1)))
    balanced = pareto[balanced_idx]

    seen = set()
    reps = []
    for label, ind in [("最省时", fastest), ("最省钱", cheapest),
                       ("体验最优", best_exp), ("均衡型", balanced)]:
        if id(ind) in seen:
            continue
        ind.solution_label = label
        reps.append(ind)
        seen.add(id(ind))

    # 🆕 补充：帕累托去重后不足 4 个时，从种群找差异化方案补充
    if len(reps) < 4 and population:
        # 把已选方案的目标值记下来，从种群找目标值差异大的
        chosen_objs = {tuple(ind.objectives) for ind in reps}
        # 按目标值差异排序：选与已有差异最大的
        remaining = [ind for ind in population
                     if tuple(ind.objectives) not in chosen_objs
                     and ind.objectives != [float('inf')]*3]
        remaining.sort(key=lambda x: -min(
            np.linalg.norm(np.array(x.objectives) - np.array(ro))
            for ro in chosen_objs
        ))
        for ind in remaining[:4 - len(reps)]:
            ind.solution_label = "备选方案"
            reps.append(ind)
            chosen_objs.add(tuple(ind.objectives))

    return reps
