# -*- coding: utf-8 -*-
"""调试高德按城市拿热门景点的正确参数组合。"""
import os
import requests

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
BASE = "https://restapi.amap.com/v3/place/text"

variants = [
    ("v1: types=1101 单个 + citylimit=true", {"city":"贵阳","citylimit":"true","types":"1101","extensions":"all","offset":25}),
    ("v2: types=1101 + citylimit=false",     {"city":"贵阳","citylimit":"false","types":"1101","extensions":"all","offset":25}),
    ("v3: keywords空 + types=1101",          {"keywords":"","city":"贵阳","citylimit":"true","types":"1101","extensions":"all","offset":25}),
    ("v4: keywords=贵阳 + types=1101",        {"keywords":"贵阳","citylimit":"true","types":"1101","extensions":"all","offset":25}),
    ("v5: keywords=景区 + city",              {"keywords":"景区","city":"贵阳","citylimit":"true","extensions":"all","offset":25}),
    ("v6: types=110100(6位)",                 {"city":"贵阳","citylimit":"true","types":"110100","extensions":"all","offset":25}),
    ("v7: keywords=贵阳 风景名胜",             {"keywords":"贵阳 风景名胜","extensions":"all","offset":25}),
]
for name, p in variants:
    p["key"] = AMAP_KEY
    p["output"] = "json"
    r = requests.get(BASE, params=p, timeout=10)
    d = r.json()
    pois = d.get("pois") or []
    first3 = [x.get("name","") for x in pois[:3]]
    print(f"{name:<38} count={d.get('count'):<4} 首3={first3}")
