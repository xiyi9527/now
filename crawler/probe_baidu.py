# -*- coding: utf-8 -*-
"""
百度百科词条描述探测
=====================================
维基国内不可用，改探百度百科。词条页 https://baike.baidu.com/item/景点名
目标：拿到词条摘要(.lemma-summary / .J-summary) 作为景点描述。
探测样本：黄果树瀑布/黔灵山/玉龙雪山/西江千户苗寨/大理古城
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

SAMPLES = ["黄果树瀑布", "黔灵山公园", "玉龙雪山", "西江千户苗寨", "大理古城"]

for title in SAMPLES:
    url = f"https://baike.baidu.com/item/{quote(title)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        print(f"\n[{r.status_code}] {title} | {url}")
        if r.status_code != 200:
            continue
        soup = BeautifulSoup(r.text, "lxml")
        # 摘要选择器（多候选）
        for sel in [".lemma-summary", ".J-summary", ".summary", ".main-content .para"]:
            node = soup.select_one(sel)
            if node:
                txt = node.get_text(" ", strip=True)
                if txt:
                    print(f"  ✓ {sel}: {txt[:120]}")
                    break
        else:
            # 退化：取第一个 .para
            para = soup.select_one(".para, .basic-info .name")
            if para:
                print(f"  ~ para: {para.get_text(' ', strip=True)[:100]}")
            else:
                print(f"  ✗ 未找到摘要块（页面 len={len(r.text)}）")
    except Exception as e:
        print(f"  [ERR] {e}")
