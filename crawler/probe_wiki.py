# -*- coding: utf-8 -*-
"""
维基百科 API 覆盖度探测
=====================================
高德 POI 无景点描述，需另找描述源。验证中文维基 API 对
贵州/云南景点的覆盖度。
API: https://zh.wikipedia.org/w/api.php?action=query&prop=extracts&exintro
     &explaintext=1&titles=景点名&format=json
"""
import requests
import json

WIKI_API = "https://zh.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "TravelPlannerBot/1.0 (educational project)"}

SAMPLES = [
    "黄果树瀑布", "黔灵山公园", "玉龙雪山", "西江千户苗寨",
    "大理古城", "丽江古城", "荔波小七孔", "梵净山",
    "石林风景区", "崇圣寺三塔",
]

for title in SAMPLES:
    params = {
        "action": "query",
        "prop": "extracts",
        "exintro": 1,
        "explaintext": 1,
        "titles": title,
        "format": "json",
        "redirects": 1,
    }
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=10)
    data = r.json()
    pages = data.get("query", {}).get("pages", {})
    for pid, page in pages.items():
        extract = page.get("extract", "")
        ok = "✓" if extract else "✗"
        preview = extract[:80].replace("\n", " ") if extract else "(无)"
        print(f"{ok} {title:<14} id={pid:<8} | {preview}")
