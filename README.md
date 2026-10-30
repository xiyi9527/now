# 基于 NSGA-Ⅱ 的智能旅行规划平台

面向自由旅行者的智能行程规划平台。以安顺、宜宾为示例场景，基于 **NSGA-Ⅱ 多目标优化算法**，综合游玩时间、总费用、路线紧凑度等多个目标，为用户生成多套可选的旅行方案（Pareto 解集），并支持在地图上查看行程路线。

## 功能概览

- **用户系统**：注册 / 登录，JWT 鉴权（Token 有效期 12h）
- **智能行程规划**：选择目的地、出行天数与偏好后，后端运行 NSGA-Ⅱ 算法，返回 Pareto 最优方案集（默认返回 Top 5），每个方案包含逐日行程安排、预计耗时与费用
- **地图可视化**：接入高德地图 JS API，行程点在地图上连线展示
- **数据看板**：基于 ECharts 的景点数据统计分析
- **管理后台**：景点数据的管理与维护
- **景点数据**：通过爬虫采集高德地图 POI 数据，清洗后入库

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 + Vite + Element Plus + Pinia + Vue Router |
| 可视化 | ECharts 6 + 高德地图 JS API |
| 后端 | Flask 3.0 + Flask-SQLAlchemy 2.0 + Flask-JWT-Extended |
| 数据库 | MySQL（PyMySQL） |
| 算法 | NSGA-Ⅱ（numpy / pandas 实现） |

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.0

### 1. 初始化数据库

创建数据库 `travel_planner2`（utf8mb4），并导入根目录下的 `travel_planner.sql`：

```sql
CREATE DATABASE travel_planner2 DEFAULT CHARACTER SET utf8mb4;
USE travel_planner2;
SOURCE travel_planner.sql;
```

然后修改 `backend/config.py` 中的数据库连接信息（用户名 / 密码）。

### 2. 配置高德地图 Key

项目中地图展示与路线规划功能依赖高德开放平台 API。请在[高德开放平台](https://lbs.amap.com/)免费申请一个 Web服务 + Web端(JS API) 类型的 Key，然后设置环境变量：

```bash
# Windows (PowerShell)
$env:AMAP_KEY = "你的高德Key"
```

代码中默认读取环境变量 `AMAP_KEY`（也可将 `YOUR_AMAP_KEY` 占位符替换为你的 Key）。

### 3. 启动后端（端口 5000）

```bash
cd backend
pip install -r requirements.txt
python run.py
```

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器访问前端开发服务器地址（默认 http://localhost:5173）。

> 也可以直接运行根目录下的 `start-all.bat` 一键启动前后端。

## 项目结构

```
├── backend/              # Flask 后端
│   ├── app/
│   │   ├── algorithms/   # NSGA-Ⅱ 算法实现
│   │   ├── models.py     # SQLAlchemy 数据模型
│   │   ├── views.py      # 业务接口
│   │   ├── admin_bp.py   # 管理后台接口
│   │   └── tip_bp.py     # 攻略/提示接口
│   ├── scripts/          # 数据导入、成本矩阵填充等脚本
│   ├── config.py         # 全局配置（数据库 / JWT / NSGA-Ⅱ 参数）
│   └── run.py            # 启动入口
├── frontend/             # Vue 3 前端
├── travel_planner.sql    # 数据库初始化脚本
└── start-all.bat         # 一键启动脚本
```

## NSGA-Ⅱ 参数（默认值）

| 参数 | 值 | 说明 |
|---|---|---|
| 种群规模 | 100 | 每代个体数 |
| 迭代代数 | 150 | 最大进化代数 |
| 交叉率 | 0.9 | — |
| 变异率 | 0.15 | — |
| 输出方案数 | 5 | Pareto 解集返回上限 |

参数可在 `backend/config.py` 中调整。

## 说明

本项目为本科毕业设计作品，代码完整开源，仅作学习交流使用。
