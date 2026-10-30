# -*- coding: utf-8 -*-
"""
高德 POI 城市类型搜索探测
=====================================
验证不传 keywords、仅按 city+types 能否拿到城市热门景点候选集。
types 组合：1101 风景名胜 + 1401 公园广场 + 0501 科教文化。
样本：贵阳/丽江/大理/安顺
"""
import os
import requests

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
BASE = "https://restapi.amap.com/v3/place/text"

CITIES = ["贵阳", "丽江", "大理", "安顺"]
TYPES = "1101,1401,0501"

for city in CITIES:
    params = {
        "key": AMAP_KEY,
        "city": city,
        "citylimit": "true",
        "types": TYPES,
        "extensions": "all",
        "offset": 25,
        "page": 1,
        "output": "json",
    }
    r = requests.get(BASE, params=params, timeout=10)
    data = r.json()
    pois = data.get("pois") or []
    print(f"\n=== {city} (count={data.get('count')}, 返回{len(pois)}条) ===")
    has_img = 0
    for p in pois[:10]:
        photos = p.get("photos") or []
        img = photos[0]["url"] if photos else ""
        if img:
            has_img += 1
        loc = p.get("location", "")
        t = (p.get("type") or "")[:20]
        print(f"  {p.get('name'):<22} | {t:<20} | img={'有' if img else '无'} | {loc}")
    print(f"  前10有图比例: {has_img}/10")
