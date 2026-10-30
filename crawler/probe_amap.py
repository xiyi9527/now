# -*- coding: utf-8 -*-
"""
高德 POI 详情接口探测
=====================================
目的：确认高德 /v3/place/text (extensions=all) 能否返回景点图片直链。
  - keywords + city 查询指定景点
  - types=1101 风景名胜 / 1401 公园广场
  - extensions=all 返回 photos 字段（list[{url,title}]）
探测样本：黄果树瀑布(安顺)、黔灵山(贵阳)、玉龙雪山(丽江)
"""
import os
import requests
import json

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
BASE = "https://restapi.amap.com/v3/place/text"

SAMPLES = [
    ("黄果树瀑布", "安顺"),
    ("黔灵山公园", "贵阳"),
    ("玉龙雪山", "丽江"),
    ("西江千户苗寨", "凯里"),
    ("大理古城", "大理"),
]

for kw, city in SAMPLES:
    params = {
        "key": AMAP_KEY,
        "keywords": kw,
        "city": city,
        "citylimit": "true",
        "types": "1101",
        "extensions": "all",
        "offset": 3,
        "page": 1,
        "output": "json",
    }
    r = requests.get(BASE, params=params, timeout=10)
    data = r.json()
    print(f"\n--- {kw} @ {city} ---")
    print(f"  status={data.get('status')} count={data.get('count')}")
    pois = data.get("pois") or []
    for p in pois[:2]:
        print(f"  POI: {p.get('name')} | location={p.get('location')} | type={p.get('type')}")
        photos = p.get("photos") or []
        print(f"    photos数={len(photos)}", end="")
        if photos:
            print(f" | 首图url={photos[0].get('url')[:80]}")
        else:
            print(" (无图片)")
        # 其他有用字段
        biz = p.get("business") or p.get("tag") or ""
        print(f"    business/tag={biz[:60]}")
