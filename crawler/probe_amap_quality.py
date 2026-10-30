# -*- coding: utf-8 -*-
"""验证 keywords='城市 风景名胜' 返回景点的图片覆盖率与坐标。"""
import os
import requests

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
BASE = "https://restapi.amap.com/v3/place/text"

CITIES = [("贵阳","贵阳"),("安顺","安顺"),("丽江","丽江"),("大理","大理"),("凯里","凯里")]
for kw_city, city in CITIES:
    params = {
        "key": AMAP_KEY, "keywords": f"{kw_city} 风景名胜", "city": city,
        "citylimit": "true", "extensions": "all", "offset": 15, "page": 1, "output": "json",
    }
    r = requests.get(BASE, params=params, timeout=10)
    pois = r.json().get("pois") or []
    has_img = sum(1 for p in pois if p.get("photos"))
    print(f"\n=== {city} (返回{len(pois)}, 有图{has_img}) ===")
    for p in pois[:8]:
        photos = p.get("photos") or []
        img = photos[0]["url"][:50] if photos else "无图"
        t = (p.get("type") or "")[:18]
        print(f"  {p.get('name'):<22} | {p.get('location')} | {t:<18} | {img}")
