# -*- coding: utf-8 -*-
"""
交通数据爬虫 → cost_matrix（高铁/火车/大巴）
=====================================
数据源与策略说明：
  - 12306 station_name.js（真实）：抓取全国 3000+ 火车站电报码，用于判断
    贵州+云南各城市是否真实通铁路（有站即通火车）。
  - 12306 余票查询接口（实时历时/票价）：经实测被反爬挡住，返回 HTML 错误页
    而非 JSON，本科毕设攻克成本过高，故改用国铁标准规则估算。
  - 历时/票价估算规则：
      · 铁路距离 = 城市间 Haversine 直线距离 × 1.3（铁路弯曲系数）
      · 高铁：250 km/h，二等座 0.45 元/km
      · 普速火车：120 km/h，硬座 0.15 元/km
      · 大巴：70 km/h，票价 0.30 元/km
  - mode 真实性：通不通铁路基于 12306 站点码（真实）。高铁/普速的区分及
    历时/票价为估算值，部分城市对实际可能仅有普速或需中转，规划时用户可辨别。

写入范围：贵州 9 + 云南 16 = 25 城市两两组合（省内 + 跨省），双向。
"""
import math
import re
import urllib3
import requests

import config
import db_writer

urllib3.disable_warnings()


# ===========================================================================
# 1. 抓 12306 站点电报码
# ===========================================================================
STATION_JS = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"


def fetch_station_codes():
    """抓取 12306 station_name.js，返回 {站名: 电报码}。"""
    s = requests.Session()
    s.headers.update({"User-Agent": config.HEADERS["User-Agent"]})
    r = s.get(STATION_JS, verify=False, timeout=15)
    r.raise_for_status()
    m = re.search(r"station_names\s*=\s*'(.+?)'", r.text)
    if not m:
        raise RuntimeError("station_name.js 解析失败")
    codes = {}
    for part in m.group(1).split("@"):
        if not part:
            continue
        seg = part.split("|")
        if len(seg) >= 3:
            codes[seg[1]] = seg[2]  # 站名 -> 电报码
    return codes


# ===========================================================================
# 2. Haversine 直线距离
# ===========================================================================
def haversine(lat1, lng1, lat2, lng2):
    """两点间直线距离(km)。"""
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ===========================================================================
# 3. 判断城市是否通铁路
# ===========================================================================
def city_has_station(city_name, codes):
    """城市是否通铁路：站点码中存在含该城市名(或别名)的站。
    别名处理州府城市与站名不一致的情况（如景洪→西双版纳站）。"""
    aliases = CITY_STATION_ALIAS.get(city_name, (city_name,))
    return any(any(a in k for k in codes) for a in aliases)


# 州府城市名 → 站点匹配别名（站名与城市名不一致时）
CITY_STATION_ALIAS = {
    "景洪": ("景洪", "西双版纳"),   # 中老铁路西双版纳站位于景洪市
    "文山": ("文山", "普者黑", "广南", "富宁"),  # 南昆高铁文山州境内站
}


# ===========================================================================
# 4. 主流程：构建并写入 cost_matrix
# ===========================================================================
def build_and_write():
    codes = fetch_station_codes()
    print(f"[1] 站点码抓取成功：{len(codes)} 个站点")

    city_ids = db_writer.get_city_id_map()
    # 城市名 -> (lng, lat) 经纬度
    coords = {name: (lng, lat) for name, _prov, lng, lat, _h, _q in config.ALL_CITIES}
    names = [c[0] for c in config.ALL_CITIES]

    rail_cities = [n for n in names if city_has_station(n, codes)]
    no_rail = [n for n in names if n not in rail_cities]
    print(f"[2] 通铁路城市 {len(rail_cities)} 个: {rail_cities}")
    print(f"    不通铁路 {len(no_rail)} 个: {no_rail}（仅填大巴）")

    rows = []
    for a in names:
        for b in names:
            if a == b:
                continue
            if a not in city_ids or b not in city_ids:
                continue
            lng1, lat1 = coords[a]
            lng2, lat2 = coords[b]
            rail_km = haversine(lat1, lng1, lat2, lng2) * 1.3  # 铁路弯曲系数
            # 大巴：所有城市对都有客运大巴
            rows.append({
                "from_city_id": city_ids[a], "to_city_id": city_ids[b],
                "mode": "大巴",
                "time_cost": max(10, round(rail_km / 70 * 60)),
                "money_cost": round(rail_km * 0.30, 2),
                "transfer_times": 0,
            })
            # 火车 + 高铁：两城都通铁路
            if a in rail_cities and b in rail_cities:
                rows.append({
                    "from_city_id": city_ids[a], "to_city_id": city_ids[b],
                    "mode": "火车",
                    "time_cost": max(15, round(rail_km / 120 * 60)),
                    "money_cost": round(rail_km * 0.15, 2),
                    "transfer_times": 0,
                })
                rows.append({
                    "from_city_id": city_ids[a], "to_city_id": city_ids[b],
                    "mode": "高铁",
                    "time_cost": max(10, round(rail_km / 250 * 60)),
                    "money_cost": round(rail_km * 0.45, 2),
                    "transfer_times": 0,
                })

    print(f"[3] 待写入 {len(rows)} 条（高铁/火车/大巴，含双向）")
    n = db_writer.batch_upsert_cost_matrix(rows)
    print(f"[4] ✅ 写入完成：{n} 条 cost_matrix")

    # 统计验证
    conn = db_writer.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT mode, COUNT(*) c FROM cost_matrix GROUP BY mode ORDER BY c DESC"
            )
            print("[5] cost_matrix 各 mode 覆盖：")
            for row in cur.fetchall():
                print(f"    {row['mode']:<6} {row['c']} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("交通数据爬虫：贵州+云南 高铁/火车/大巴 → cost_matrix")
    print("=" * 60)
    build_and_write()
