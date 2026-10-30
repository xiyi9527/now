# -*- coding: utf-8 -*-
"""
携程景点页结构探测脚本
=====================================
马蜂窝被腾讯防水墙滑块验证码挡住（requests 无法绕过），改探携程。
探测目标：
  1. you.ctrip.com 景点列表页（PC 端）
  2. m.ctrip.com 移动端景点 API（通常更友好）
  3. 景点详情页（从列表页拿到真实链接后）
拿到字段：景点名 / 图片直链 / 描述 / 游览时长 / 评分
"""
import os
import re
import json
import time

import requests
from bs4 import BeautifulSoup

import config

DATA = config.DATA_DIR
os.makedirs(DATA, exist_ok=True)

UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
)
UA_PC = config.HEADERS["User-Agent"]

s = requests.Session()
s.headers.update({
    "User-Agent": UA_PC,
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "https://you.ctrip.com/",
})


def fetch(url, save_as=None, ua=None):
    headers = dict(s.headers)
    if ua:
        headers["User-Agent"] = ua
    try:
        r = s.get(url, headers=headers, timeout=config.REQUEST_TIMEOUT)
        print(f"  [{r.status_code}] {url[:90]}")
        if save_as:
            p = os.path.join(DATA, save_as)
            with open(p, "w", encoding="utf-8") as f:
                f.write(r.text)
            print(f"     已保存 -> data/{save_as} ({len(r.text)} 字节)")
        return r.status_code, r.text
    except Exception as e:
        print(f"  [ERR] {url[:90]} -> {e}")
        return None, str(e)


def analyze_list_html(text):
    """分析景点列表页 HTML，提取景点名/链接/图片。"""
    soup = BeautifulSoup(text, "lxml")
    title = soup.title.string if soup.title else "(无标题)"
    print(f"     标题: {title[:60]}")

    # 景点卡片常见结构（.list_mod_box, .rdtbox, .sight-item, dl dt dd）
    items = soup.select(".list_mod_box, .rdtbox, .sight-item, .list-item, .item")
    print(f"     候选卡片容器数: {len(items)}")
    if items:
        first = items[0]
        names = [a.get_text(strip=True) for a in first.select("a")][:3]
        print(f"     第1卡片链接文本: {names}")
        imgs = [img.get("src") or img.get("data-src") for img in first.select("img")][:2]
        print(f"     第1卡片图片: {imgs}")

    # 退化方案：直接找所有景点详情链接 /sight/.../数字.html
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        m = re.search(r"/sight/[^/]+/\d+\.html", href)
        if m and href not in links:
            links.append(href)
    print(f"     景点详情链接数(去重): {len(links)}，前3: {links[:3]}")
    return links


# ===========================================================================
# 1. 探测 you.ctrip.com 景点列表页（贵州/贵阳）
# ===========================================================================
def probe_list_pc():
    print("\n=== 1. 探测 you.ctrip.com 景点列表页（PC） ===")
    candidates = [
        # 贵州省 destId=34, 贵阳市 destId 候选 145/164
        ("https://you.ctrip.com/sight/guizhou/34.html", "ctrip_guizhou.html"),
        ("https://you.ctrip.com/sight/guiyang/145.html", "ctrip_guiyang.html"),
    ]
    all_links = []
    for url, fn in candidates:
        code, text = fetch(url, fn)
        if code == 200 and text:
            all_links = analyze_list_html(text)
        time.sleep(config.REQUEST_DELAY)
    return all_links


# ===========================================================================
# 2. 探测携程移动端景点 API
#    携程移动端常用接口（盲试几个常见路径）
# ===========================================================================
def probe_mobile_api():
    print("\n=== 2. 探测携程移动端景点 API ===")
    # 常见 destId：贵州 34, 贵阳 145（待确认）
    apis = [
        # 列表搜索接口
        ("GET", "https://m.ctrip.com/restapi/so1/so/sightList?keyword=贵阳&pageIndex=1"),
        # 目的地景点列表
        ("GET", "https://m.ctrip.com/restapi/so1/so/destSightList?destId=145&pageIndex=1"),
        # 另一种格式
        ("GET", "https://m.ctrip.com/restapi/so1/dest/sight?destId=145&pageIndex=1"),
    ]
    for method, url in apis:
        try:
            if method == "GET":
                r = s.get(url, headers={"User-Agent": UA_MOBILE}, timeout=config.REQUEST_TIMEOUT)
            print(f"  [{r.status_code}] {method} {url[:80]}")
            if r.text.startswith("{") or r.text.startswith("["):
                print(f"     JSON ✓ 样例: {r.text[:300]}")
            else:
                print(f"     非JSON样例: {r.text[:120]}")
        except Exception as e:
            print(f"  [ERR] {e}")
        time.sleep(config.REQUEST_DELAY)


# ===========================================================================
# 3. 探测景点详情页
# ===========================================================================
def probe_detail(link):
    print("\n=== 3. 探测景点详情页 ===")
    if not link.startswith("http"):
        link = "https://you.ctrip.com" + link
    code, text = fetch(link, "ctrip_detail.html")
    if code == 200 and text:
        soup = BeautifulSoup(text, "lxml")
        title = soup.title.string if soup.title else "(无标题)"
        print(f"     标题: {title[:60]}")
        # 描述（.box_info, .des, .summary, .normal-poi-info）
        desc = soup.select_one(".box_info, .des, .summary, .normal-poi-info, .poi-desc")
        if desc:
            print(f"     描述样例: {desc.get_text(' ', strip=True)[:120]}")
        # 游览时长（文本含"建议游玩"或"开放时间"）
        m = re.search(r"建议游玩[^0-9]*([\d.-]+)\s*[-~到至]?\s*([\d.]*)\s*小时", text)
        if m:
            print(f"     游览时长(正则): {m.group(0)}")
        # 图片
        imgs = [img.get("src") or img.get("data-src") for img in soup.select("img")]
        imgs = [i for i in imgs if i and ("http" in i or "//" in i)]
        print(f"     图片总数: {len(imgs)}，前3: {imgs[:3]}")


if __name__ == "__main__":
    print("=" * 60)
    print("携程景点页结构探测")
    print("=" * 60)
    links = probe_list_pc()
    probe_mobile_api()
    if links:
        probe_detail(links[0])
    else:
        print("\n[提示] 列表页未拿到景点详情链接，请人工查看 data/ctrip_*.html")
