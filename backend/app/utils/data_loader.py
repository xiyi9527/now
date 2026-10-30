"""
数据加载器
- 从 cost_matrix 表构建邻接矩阵（时间/金钱/不适感）
- 算法运行时只查一次，缓存到类属性中，避免每代查库
"""
import numpy as np
from app.models import City, CostMatrix


class DataLoader:
    """
    单例：所有算法共享一份缓存的矩阵
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def load(self):
        if self._initialized:
            return self

        # 1. 读所有城市，建立 city_id -> 索引 映射
        cities = City.query.order_by(City.id).all()
        self.city_ids = [c.id for c in cities]
        self.id_to_idx = {cid: i for i, cid in enumerate(self.city_ids)}
        self.id_to_city = {c.id: c for c in cities}
        self.city_count = len(cities)

        # city_id -> (lat, lng) 方便同城场景用
        self.city_coord = {c.id: (float(c.lat), float(c.lng)) for c in cities}

        # spot 缓存（同城场景用）
        from app.models import Spot
        spots = Spot.query.all()
        self.spot_cache = {
            s.id: {
                "id": s.id, "name": s.name,
                "city_id": s.city_id,
                "lat": float(s.lat), "lng": float(s.lng),
                "cost_time_extra": int(s.cost_time_extra),
            }
            for s in spots
        }

        # 2. 初始化三个成本矩阵 (N x N)
        N = self.city_count
        self.time_matrix = np.full((N, N), fill_value=np.inf, dtype=np.float64)
        self.money_matrix = np.full((N, N), fill_value=np.inf, dtype=np.float64)
        self.discomfort_matrix = np.full((N, N), fill_value=np.inf, dtype=np.float64)

        # 对角线 0（同城自环成本设为 avg of outgoing）
        # 但同城跨景点可能有真实成本，这里先保持 0，算法评估时不单独走 self-loop
        # Floyd-Warshall 会确保任意 i→i = 0（经过其他节点的路径）
        # 所以同城两个景点间的真实成本由 Floyd 算出来
        # 对角线本身保持 0 即可
        np.fill_diagonal(self.time_matrix, 0)
        np.fill_diagonal(self.money_matrix, 0)
        np.fill_diagonal(self.discomfort_matrix, 0)

        # 3. 填充 cost_matrix 中的已有数据
        rows = CostMatrix.query.all()
        for r in rows:
            if r.from_city_id in self.id_to_idx and r.to_city_id in self.id_to_idx:
                i = self.id_to_idx[r.from_city_id]
                j = self.id_to_idx[r.to_city_id]
                self.time_matrix[i][j] = float(r.time_cost)
                self.money_matrix[i][j] = float(r.money_cost)
                # transfer_times / discomfort 合并成不适感
                self.discomfort_matrix[i][j] = float(r.discomfort) + float(r.transfer_times) * 0.5

        # 4. 对缺失的边用对称近似填充（若 j->i 有值则复用）
        for i in range(N):
            for j in range(N):
                if i != j and self.time_matrix[i][j] == np.inf:
                    if self.time_matrix[j][i] != np.inf:
                        self.time_matrix[i][j] = self.time_matrix[j][i]
                        self.money_matrix[i][j] = self.money_matrix[j][i]
                        self.discomfort_matrix[i][j] = self.discomfort_matrix[j][i]

        # 5. Floyd-Warshall 计算最短时间路径（time 最优先，money/discomfort 跟随 time 的最短路径）
        #    这样即使 cost_matrix 稀疏，任意两个城市之间也有"最优可达"成本
        self.next_node = np.full((N, N), -1, dtype=np.int32)
        for i in range(N):
            for j in range(N):
                if i != j and self.time_matrix[i][j] != np.inf:
                    self.next_node[i][j] = j

        for k in range(N):
            for i in range(N):
                for j in range(N):
                    if self.time_matrix[i][k] + self.time_matrix[k][j] < self.time_matrix[i][j]:
                        self.time_matrix[i][j] = self.time_matrix[i][k] + self.time_matrix[k][j]
                        self.money_matrix[i][j] = self.money_matrix[i][k] + self.money_matrix[k][j]
                        self.discomfort_matrix[i][j] = self.discomfort_matrix[i][k] + self.discomfort_matrix[k][j]
                        self.next_node[i][j] = self.next_node[i][k]

        self._initialized = True
        return self

    def reconstruct_path(self, i_idx: int, j_idx: int) -> list:
        """
        还原 i→j 的实际跳点序列（**含 i 和 j**，用于前端展示完整分步导航）。
        正确的 Floyd next_node 回溯：
          next_node[i][j] = k 表示 i 到 j 的最短路径里，i 的下一跳是 k
        """
        if i_idx == j_idx:
            return [i_idx]
        if self.time_matrix[i_idx][j_idx] == np.inf:
            return []
        path = [i_idx]
        cur = i_idx
        # 安全保护：最多 N 步防止死循环
        safety = self.city_count + 1
        while cur != j_idx and safety > 0:
            nxt = int(self.next_node[cur][j_idx])
            if nxt == -1:
                break
            path.append(nxt)
            cur = nxt
            safety -= 1
        if path[-1] != j_idx:
            path.append(j_idx)
        return path

    def full_route(self, idx_list: list) -> list:
        """把 [idx0, idx1, idx2] 这种停靠序列展开成完整的跳点序列（含中间经过的所有城市）。
        同时过滤掉明显无意义的绕路（路径中同一 city 出现超过 1 次 = 绕回）。"""
        if len(idx_list) < 2:
            return list(idx_list)
        full = []
        for a, b in zip(idx_list, idx_list[1:]):
            seg = self.reconstruct_path(a, b)
            if not seg:
                continue
            if not full:
                full.extend(seg)
            else:
                full.extend(seg[1:])
        # 去绕路：去掉除起点外任何重复出现的 city
        seen = set()
        clean = []
        for i, idx in enumerate(full):
            if i == 0 or idx not in seen or idx == full[-1]:
                clean.append(idx)
                seen.add(idx)
        return clean

    def feasible_pool(self, start_idx: int, end_idx: int) -> list:
        """返回从 start 可达且到 end 可达的中间候选城市 idx 列表。"""
        pool = []
        for idx in range(self.city_count):
            if idx == start_idx or idx == end_idx:
                continue
            if (self.time_matrix[start_idx][idx] != np.inf
                    and self.time_matrix[idx][end_idx] != np.inf):
                pool.append(idx)
        return pool

    def city_name(self, city_id: int) -> str:
        c = self.id_to_city.get(city_id)
        return c.name if c else f"City#{city_id}"

    def coords(self, city_id: int):
        c = self.id_to_city.get(city_id)
        if c is None:
            return None
        return float(c.lat), float(c.lng)

    def idx(self, city_id: int) -> int:
        return self.id_to_idx[city_id]

    def fill_missing_from_amap(self, focus_city_ids=None, max_edges=200):
        """
        🆕 实时用高德驾车 API 填充 time_matrix / money_matrix / discomfort_matrix 中的 inf 边。
        focus_city_ids: list[int] — 如果给了，优先填这些城市的出入边（更精准、更快）
        max_edges: 最多填多少条，防止一次性调太多 API
        填完之后**自动重跑 Floyd-Warshall**，让所有可达路径都用真实数据。
        """
        from app.utils.amap_router import driving, cache_stats
        import numpy as np

        # 确定要填哪些边
        pairs_to_fill = []
        N = self.city_count

        if focus_city_ids:
            # 模式 A：只填和 focus 城市相关的边（更精准）
            focus_idx = {self.id_to_idx[c] for c in focus_city_ids if c in self.id_to_idx}
            all_idx = set(range(N))
            for i in range(N):
                if self.time_matrix[i][i] == np.inf: continue
                for j in range(N):
                    if i == j: continue
                    if self.time_matrix[i][j] != np.inf: continue
                    if i in focus_idx or j in focus_idx:
                        pairs_to_fill.append((i, j))
        else:
            # 模式 B：扫描所有 inf 边
            for i in range(N):
                for j in range(N):
                    if i != j and self.time_matrix[i][j] == np.inf:
                        pairs_to_fill.append((i, j))

        pairs_to_fill = pairs_to_fill[:max_edges]
        filled = 0
        for i_idx, j_idx in pairs_to_fill:
            ci = self.id_to_city[self.city_ids[i_idx]]
            cj = self.id_to_city[self.city_ids[j_idx]]
            r = driving(float(ci.lng), float(ci.lat),
                        float(cj.lng), float(cj.lat))
            if r:
                self.time_matrix[i_idx][j_idx] = r["duration_min"]
                self.money_matrix[i_idx][j_idx] = r["tolls_yuan"] + max(0, r["distance_km"] * 0.3)
                self.discomfort_matrix[i_idx][j_idx] = r["distance_km"] * 0.03
                # 反向如果也缺失（且还没填），一起填
                if self.time_matrix[j_idx][i_idx] == np.inf:
                    self.time_matrix[j_idx][i_idx] = r["duration_min"]
                    self.money_matrix[j_idx][i_idx] = r["tolls_yuan"] + max(0, r["distance_km"] * 0.3)
                    self.discomfort_matrix[j_idx][i_idx] = r["distance_km"] * 0.03
                    filled += 1
                filled += 1

        # 重跑 Floyd-Warshall，用新数据更新 next_node
        self.next_node = np.full((N, N), -1, dtype=np.int32)
        for i in range(N):
            for j in range(N):
                if i != j and self.time_matrix[i][j] != np.inf:
                    self.next_node[i][j] = j

        for k in range(N):
            for i in range(N):
                for j in range(N):
                    if self.time_matrix[i][k] + self.time_matrix[k][j] < self.time_matrix[i][j]:
                        self.time_matrix[i][j] = self.time_matrix[i][k] + self.time_matrix[k][j]
                        self.money_matrix[i][j] = self.money_matrix[i][k] + self.money_matrix[k][j]
                        self.discomfort_matrix[i][j] = self.discomfort_matrix[i][k] + self.discomfort_matrix[k][j]
                        self.next_node[i][j] = self.next_node[i][k]

        stats = cache_stats()
        return {"filled_edges": filled, "amap_api_calls": stats["api_calls"],
                "cache_hits": stats["cache_hits"], "remaining_inf": int(np.sum(self.time_matrix == np.inf))}

    def reset(self):
        """单元测试时重置"""
        self._initialized = False
