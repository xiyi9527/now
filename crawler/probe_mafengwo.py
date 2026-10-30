# -*- coding: utf-8 -*-
"""
马蜂窝景点页结构探测脚本
=====================================
目的：确认能从马蜂窝拿到哪些景点字段（名称/图片直链/描述/游览时长）
探测对象：
  1. 城市景点列表页（候选 URL 多个）
  2. 景点详情页（从列表页抓到的 POI）
  3. 异步 POI 接口（如有）
策略：抓 HTML 落盘到 data/ 便于人工核对，同时用 bs4 提取关键元素。
"""
import os
import re
import time
import json

import requests
from bs4 import BeautifulSoup

import config

DATA = config.DATA_DIR
os.makedirs(DATA, exist_ok=True)

UA = config.HEADERS["User-Agent"]
HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.mafengwo.cn/",
}

s = requests.Session()
s.headers.update(HEADERS)


def fetch(url, save_as=None):
    """抓 URL，返回 (status, text)；失败返回 (None, err)。"""
    try:
        r = s.get(url, timeout=config.REQUEST_TIMEOUT)
        print(f"  [{r.status_code}] {url[:80]}")
        if save_as:
            p = os.path.join(DATA, save_as)
            with open(p, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"     已保存 -> data/{save_as} ({len(r.text)} 字节)")
        return r.status_code, r.text
    except Exception as e:
        print(f"  [ERR] {url[:80]} -> {e}")
        return None, str(e)


# ===========================================================================
# 1. 探测贵阳景点列表页（多候选城市ID + 多候选路径）
# ===========================================================================
def probe_city_list():
    print("\n=== 1. 探测贵阳景点列表页 ===")
    candidates = [
        # 城市ID候选：10163 贵阳（待确认）
        ("https://www.mafengwo.cn/travel-scenic-spot/mafengwo/10163.html", "gy_list_a.html"),
        ("https://www.mafengwo.cn/jd/10163/gonglve.html", "gy_list_b.html"),
        ("https://www.mafengwo.cn/jd/10163/", "gy_list_c.html"),
        # 贵阳城市页（不带 gonglve）
        ("https://www.mafengwo.cn/cy/10163/", "gy_city.html"),
    ]
    for url, fn in candidates:
        code, text = fetch(url, fn)
        if code == 200 and text:
            soup = BeautifulSoup(text, "lxml")
            title = soup.title.string if soup.title else "(无标题)"
            print(f"     标题: {title[:60]}")
            # 找景点名（常见 class: .poi-list, .scenic, .att-list）
            poi_names = [a.get_text(strip=True) for a in soup.select(".poi-list a, .scenic-list a, .att-list a, .post-list a")][:5]
            if poi_names:
                print(f"     候选景点名(前5): {poi_names}")
            # 找图片
            imgs = [img.get("src") or img.get("data-src") for img in soup.select("img")][:5]
            imgs = [i for i in imgs if i and ("http" in i or "//" in i)][:5]
            if imgs:
                print(f"     候选图片直链(前5): {imgs}")
        time.sleep(config.REQUEST_DELAY)


# ===========================================================================
# 2. 探测景点详情页（先用一个已知POI示例，看结构）
#    马蜂窝景点详情页路径形如 /travel-scenic-spot/mafengwo/poi-XXX.html 或 /poi/XXX.html
#    先从列表页拿到真实POI链接再探测。
# ===========================================================================
def probe_poi_detail(poi_url):
    print("\n=== 2. 探测景点详情页 ===")
    print(f"  目标: {poi_url}")
    code, text = fetch(poi_url, "poi_detail.html")
    if code == 200 and text:
        soup = BeautifulSoup(text, "lxml")
        title = soup.title.string if soup.title else "(无标题)"
        print(f"     标题: {title[:60]}")
        # 景点描述（常见 .summary, .post-content, .poi-desc）
        desc = soup.select_one(".summary, .post-content, .poi-desc, .poi-detail-info")
        if desc:
            print(f"     描述样例: {desc.get_text(' ', strip=True)[:120]}")
        # 图片
        imgs = [img.get("src") or img.get("data-src") for img in soup.select("img")]
        imgs = [i for i in imgs if i and ("http" in i or "//" in i)]
        print(f"     图片总数: {len(imgs)}，前3: {imgs[:3]}")
        # 游览时长（常见 .post-meta, .poi-info, 文本含"建议游玩"）
        m = re.search(r"建议游玩[^0-9]*([\d.]+)\s*小时", text)
        if m:
            print(f"     游览时长(正则): {m.group(0)}")


# ===========================================================================
# 3. 异步接口探测（POI 列表可能是 ajax 加载的）
#    router.php 常见参数：sAct=getPoiList, iCityId=10163
# ===========================================================================
def probe_ajax_api():
    print("\n=== 3. 探测异步 POI 接口 ===")
    api = config.SOURCE_MAFENGWO["poi_api"]
    # 常见参数组合（盲试）
    payloads = [
        {"sAct": "getPoiList", "iCityId": "10163", "iPage": "1"},
        {"sAct": "scenicSpot", "iCityId": "10163", "iPage": "1"},
    ]
    for p in payloads:
        try:
            r = s.post(api, data=p, timeout=config.REQUEST_TIMEOUT)
            print(f"  POST {api} params={p} -> [{r.status_code}] len={len(r.text)}")
            # 是否 JSON
            if r.text.startswith("{") or r.text.startswith("["):
                print(f"     JSON 响应样例: {r.text[:200]}")
            else:
                print(f"     非JSON响应样例: {r.text[:120]}")
        except Exception as e:
            print(f"  [ERR] {e}")
        time.sleep(config.REQUEST_DELAY)


if __name__ == "__main__":
    print("=" * 60)
    print("马蜂窝景点页结构探测")
    print("=" * 60)
    probe_city_list()
    probe_ajax_api()
    # POI 详情探测：先留空，等列表页拿到真实 POI 链接再补
    print("\n[提示] 请人工查看 data/gy_list_*.html，确认贵阳城市ID 与 POI 链接后，")
    print("       再在 probe_poi_detail() 传入真实 POI URL 进行详情页探测。")
