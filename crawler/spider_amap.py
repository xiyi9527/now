# -*- coding: utf-8 -*-
"""
景点数据爬虫 → spots 表（贵州 9 城 + 云南 16 城）
=====================================
数据源：高德 POI 搜索 /v3/place/text（开放接口，无反爬，返回真实图片直链）
  注：马蜂窝/携程/维基/百度百科均被反爬挡住，唯一稳定可用源为高德 POI。

策略（双轨）：
  1. SEEDS 核心景区清单（人工精选，约70个知名景区，含精炼描述+游览时长）
     → 按 keywords=景区名 + city 限定精确搜，拿真实图片直链 + 经纬度。
     覆盖跨县区知名景区（如黄果树在安顺下辖镇宁、西江苗寨在凯里下辖雷山）。
  2. 25 城城市热搜：keywords="城市 风景名胜" + citylimit=true
     → 每城取有图景点前 12 个，补充城市内热门景点。
  描述：核心景区用 SEEDS 人工描述；城市热搜景点用高德 type 字段拼简短描述。
  时长：核心景区用 SEEDS 人工值；其余默认 120 分钟。

写入：batch_upsert_spots 按 city_id+name 去重（已有同名景点自动补图补描述）。
      最后清理贵州+云南 25 城里 img_url 为空且 description="高德导入"的占位垃圾。
"""
import os
import time
import requests

import config
import db_writer

AMAP_KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")
BASE = "https://restapi.amap.com/v3/place/text"
UA = config.HEADERS["User-Agent"]

# ===========================================================================
# SEEDS：核心景区人工清单 (景区名, 所属城市, 描述, 游览时长分钟)
#   所属城市须与 config.ALL_CITIES 的 name 一致；描述精炼 1-2 句。
# ===========================================================================
SEEDS = [
    # ---------------- 贵州 9 城 ----------------
    # 安顺
    ("黄果树瀑布", "安顺", "亚洲最大瀑布，5A 级景区，含大瀑布、天星桥、陡坡塘三大景区", 240),
    ("龙宫", "安顺", "喀斯特溶洞奇观，5A 级景区，地下暗河与瀑布并存", 180),
    ("天龙屯堡", "安顺", "明代屯堡文化活化石，石头寨建筑群", 120),
    ("旧州古镇", "安顺", "安顺三大古镇之一，苗族风情古镇", 120),
    # 贵阳
    ("黔灵山公园", "贵阳", "贵阳城市绿肺，含弘福寺、黔灵湖、动物园", 180),
    ("甲秀楼", "贵阳", "贵阳地标，南明河上明代古阁", 60),
    ("青岩古镇", "贵阳", "5A 级军事古镇，明代屯堡，贵州四大古镇之一", 180),
    ("花溪公园", "贵阳", "城市湿地公园，花溪十里河滩", 120),
    ("天河潭", "贵阳", "喀斯特溶洞与瀑布组合景区", 120),
    # 遵义
    ("遵义会议会址", "遵义", "红色圣地，中国革命转折点", 90),
    ("赤水丹霞", "遵义", "世界自然遗产，丹霞地貌与瀑布群", 240),
    ("茅台镇", "遵义", "中国酒都，国酒茅台产地", 120),
    ("娄山关", "遵义", "红色遗址，黔北险关", 90),
    # 六盘水
    ("乌蒙大草原", "六盘水", "高原草场与喀斯特峰丛，云海日出", 240),
    ("梅花山", "六盘水", "高原滑雪胜地，四季观景", 180),
    # 毕节
    ("织金洞", "毕节", "中国最美溶洞，喀斯特地下宫殿", 180),
    ("百里杜鹃", "毕节", "世界最大天然花园，杜鹃花海", 180),
    ("草海", "毕节", "高原湿地，黑颈鹤越冬地", 120),
    # 铜仁
    ("梵净山", "铜仁", "世界自然遗产，5A 级，弥勒道场，蘑菇石奇观", 300),
    ("九龙洞", "铜仁", "喀斯特溶洞，地下暗河", 90),
    # 凯里（黔东南）
    ("西江千户苗寨", "凯里", "世界最大苗寨，夜景与苗族风情", 240),
    ("肇兴侗寨", "凯里", "侗乡第一寨，鼓楼与风雨桥", 180),
    ("郎德上寨", "凯里", "奥运圣火走过的苗寨，原生态民族风情", 120),
    ("镇远古镇", "凯里", "滇楚锁钥，舞阳河畔千年古城", 180),
    # 都匀（黔南）
    ("荔波小七孔", "都匀", "世界自然遗产，5A 级，喀斯特山水", 240),
    ("茂兰", "都匀", "喀斯特原始森林，世界遗产", 240),
    ("平塘甲茶", "都匀", "峡谷瀑布与田园风光", 120),
    # 兴义（黔西南）
    ("马岭河峡谷", "兴义", "地球美丽伤疤，喀斯特峡谷瀑布", 180),
    ("万峰林", "兴义", "徐霞客称天下奇山，喀斯特峰林", 180),

    # ---------------- 云南 16 城 ----------------
    # 昆明
    ("石林风景区", "昆明", "世界自然遗产，5A 级，喀斯特石林地貌", 240),
    ("滇池", "昆明", "高原明珠，海埂大坝观红嘴鸥", 120),
    ("西山", "昆明", "滇池畔，龙门石窟与绝壁", 180),
    ("云南民族村", "昆明", "25 个民族村寨风情展示", 180),
    ("九乡溶洞", "昆明", "喀斯特溶洞群，雄狮大厅", 120),
    # 曲靖
    ("罗平油菜花", "曲靖", "金色花海，九龙瀑布群", 120),
    ("多依河", "曲靖", "布依族风情，钙华瀑布", 120),
    # 玉溪
    ("抚仙湖", "玉溪", "高原深湖，水质清澈", 180),
    # 保山（腾冲）
    ("腾冲热海", "保山", "火山地热奇观，热海大滚锅", 180),
    ("和顺古镇", "保山", "中国魅力名镇，侨乡与图书馆", 180),
    ("腾冲火山", "保山", "火山公园，柱状节理", 120),
    # 昭通
    ("大山包", "昭通", "高原湿地，黑颈鹤与鸡公山", 180),
    # 丽江
    ("丽江古城", "丽江", "世界文化遗产，纳西古韵，木府与四方街", 240),
    ("玉龙雪山", "丽江", "5A 级，北半球最近赤道的冰川，13 峰终年积雪", 300),
    ("束河古镇", "丽江", "茶马古镇，纳西先民聚居地", 120),
    ("虎跳峡", "丽江", "世界最深峡谷之一，金沙江奔涌", 180),
    ("泸沽湖", "丽江", "高原明珠，摩梭母系氏族风情", 240),
    # 普洱
    ("那柯里", "普洱", "茶马古驿站，民族团结誓词碑", 90),
    ("梅子湖", "普洱", "高原湖泊，茶马古道节点", 90),
    # 临沧
    ("翁丁佤寨", "临沧", "中国最后原始部落，佤族茅草屋", 180),
    # 大理
    ("大理古城", "大理", "南诏古都，五华楼与洋人街", 180),
    ("苍山", "大理", "十九峰十八溪，云弄峰与玉局峰", 240),
    ("洱海", "大理", "高原明珠，环湖骑行与双廊", 240),
    ("崇圣寺三塔", "大理", "5A 级，南诏皇家寺院，三塔倒影", 120),
    ("喜洲古镇", "大理", "白族民居建筑群，严家大院", 120),
    # 楚雄
    ("禄丰恐龙谷", "楚雄", "恐龙化石遗址，1:1 仿真恐龙", 180),
    ("元谋土林", "楚雄", "土林奇观，元谋人遗址", 120),
    # 蒙自（红河）
    ("建水古城", "蒙自", "临安古城，朱家花园与双龙桥", 180),
    ("燕子洞", "蒙自", "亚洲最大溶洞，雨燕栖息地", 120),
    # 文山
    ("普者黑", "文山", "5A 级，喀斯特山水，荷花与溶洞", 240),
    ("坝美", "文山", "世外桃源，水洞入村", 180),
    # 景洪（西双版纳）
    ("西双版纳热带植物园", "景洪", "5A 级，最大热带植物王国", 240),
    ("野象谷", "景洪", "亚洲野象观测，雨林漫步", 120),
    ("曼听公园", "景洪", "傣王御花园，篝火晚会", 120),
    ("傣族园", "景洪", "五个傣族村寨组合，泼水体验", 180),
    # 芒市（德宏）
    ("勐巴娜西", "芒市", "珍奇园，古树名木与硅化木", 90),
    ("树包塔", "芒市", "百年榕树包佛塔，奇观", 60),
    ("一寨两国", "芒市", "中缅边境，一秋荡两国", 60),
    # 香格里拉（迪庆）
    ("普达措", "香格里拉", "5A 级，世界自然遗产，高原湖泊与原始森林", 240),
    ("松赞林寺", "香格里拉", "云南最大藏传佛教寺院，小布达拉宫", 120),
    ("独克宗古城", "香格里拉", "月光城，藏式古城，转经筒", 120),
    ("梅里雪山", "香格里拉", "藏区八大神山，卡瓦格博峰", 240),
    # 泸水（怒江）
    ("怒江大峡谷", "泸水", "东方大峡谷，傈僳族风情", 240),
    ("丙中洛", "泸水", "人神共居之地，怒江第一湾", 180),
]


# ===========================================================================
# 高德 POI 搜索
# ===========================================================================
def search_poi(keywords, city=None, citylimit=False, offset=20, retry=2):
    """高德 POI 搜索，返回 pois 列表。失败返回 []。"""
    params = {
        "key": AMAP_KEY,
        "keywords": keywords,
        "extensions": "all",
        "offset": offset,
        "page": 1,
        "output": "json",
    }
    if city:
        params["city"] = city
        params["citylimit"] = "true" if citylimit else "false"
    for _ in range(retry + 1):
        try:
            r = requests.get(BASE, params=params, headers={"User-Agent": UA}, timeout=15)
            data = r.json()
            if data.get("status") == "1":
                return data.get("pois") or []
        except Exception:
            time.sleep(0.5)
    return []


def normalize_img(url):
    """高德图片直链统一 https，去掉参数。"""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("http://"):
        url = "https://" + url[7:]
    return url


def parse_location(loc):
    """'lng,lat' → (lat, lng) float。失败返回 None。"""
    if not loc or "," not in loc:
        return None
    try:
        lng, lat = loc.split(",")
        return float(lat), float(lng)
    except Exception:
        return None


# 酒店/客栈/接待中心/商铺/行政区域等非景区 POI 排除词（pick_seed_poi 跳过这类）
EXCLUDE_WORDS = (
    "酒店", "客栈", "宾馆", "民宿", "饭店", "度假村", "度假酒店", "养生",
    "接待中心", "游客中心", "驿站", "旅馆", "公寓", "套房", "大床", "标间", "旅客",
    "门票代售", "售票处", "咨询中心", "咨询处", "售票点", "服务中心", "管理所",
    "管理站", "接待站", "管理局", "办事处", "居委会", "村委会",
    # 商铺/商业
    "批发", "服饰", "总汇", "商铺", "商店", "超市", "便利店", "购物中心",
    "批发部", "营业部", "宿舍", "小区", "大厦", "茶店", "茶馆", "酥油茶",
    # 行政区域（非景区）
    "自治州", "自治县", "地区行政", "行政公署",
)
# 关键词后缀剥离（"黄果树瀑布"→核心"黄果树"，"石林风景区"→核心"石林"）
NAME_SUFFIXES = (
    "风景名胜区", "风景区", "风景名胜", "景区", "瀑布", "溶洞", "湖泊",
    "峡谷", "雪山", "古镇", "古城", "公园", "寺院", "塔", "园",
)


def pick_seed_poi(pois, keywords):
    """从精确搜结果选最佳 POI：优先 name 含关键词核心子串且有图，排除酒店/商铺类。"""
    if not pois:
        return None
    # 关键词核心子串：原词 + 去后缀的核心词（"黄果树瀑布"→"黄果树"）
    kws = [keywords]
    if " " in keywords:
        kws.append(keywords.split(" ")[-1])
    for suf in NAME_SUFFIXES:
        if keywords.endswith(suf) and len(keywords) > len(suf) + 1:
            kws.append(keywords[:-len(suf)])
    kws = list(dict.fromkeys(kws))  # 去重保序

    def is_excluded(name):
        return any(w in name for w in EXCLUDE_WORDS)

    # 第一轮：name 含关键词核心 + 有图 + 非酒店/商铺
    for p in pois:
        if not p.get("photos"):
            continue
        name = p.get("name", "")
        if is_excluded(name):
            continue
        if any(k in name for k in kws if len(k) >= 2):
            return p
    # 第二轮：有图 + 非酒店/商铺（关键词弱匹配）
    for p in pois:
        if not p.get("photos"):
            continue
        if not is_excluded(p.get("name", "")):
            return p
    # 退化：第一个有图且非排除词的
    for p in pois:
        if p.get("photos") and not is_excluded(p.get("name", "")):
            return p
    # 实在没有有图的，取第一个非排除词的（景区本身无图也保留，但不写酒店/行政区域）
    for p in pois:
        if not is_excluded(p.get("name", "")):
            return p
    return None  # 全是酒店/行政区域类，跳过该景区不写入错误数据


def type_to_desc(amap_type, city):
    """高德 type 字段拼简短描述。type 形如 '风景名胜;风景名胜;国家级景点'。"""
    if not amap_type:
        return f"{city}风景名胜"
    parts = [p for p in amap_type.split(";") if p]
    leaf = parts[-1] if parts else "风景名胜"
    return f"{leaf}，位于{city}"


# ===========================================================================
# 主流程
# ===========================================================================
def build_and_write():
    city_ids = db_writer.get_city_id_map()
    # 城市 name → province
    province_map = {n: p for n, p, _x, _y, _h, _q in config.ALL_CITIES}
    city_names = [c[0] for c in config.ALL_CITIES]

    spots = []          # 待写入 list[dict]
    seen = set()        # (city_id, name) 去重
    img_total = 0

    # -----------------------------------------------------------------------
    # 1. SEEDS 核心景区精确搜
    # -----------------------------------------------------------------------
    print(f"[1] 处理 {len(SEEDS)} 个核心景区（精确搜拿图+坐标）...")
    for kw, city, desc, duration in SEEDS:
        if city not in city_ids:
            print(f"  ✗ 跳过 {kw}（城市 {city} 不在库）")
            continue
        cid = city_ids[city]
        # 先 citylimit=true 限定本城；count=0 则放宽（跨县区如西江苗寨在雷山不属凯里市辖区）
        pois = search_poi(kw, city=city, citylimit=True)
        if not pois:
            pois = search_poi(kw, city=city, citylimit=False)
        if not pois:
            pois = search_poi(kw)  # 全局搜
        poi = pick_seed_poi(pois, kw)
        if not poi:
            print(f"  ✗ {kw} @ {city} 未找到")
            continue
        loc = parse_location(poi.get("location"))
        if not loc:
            continue
        lat, lng = loc
        photos = poi.get("photos") or []
        img = normalize_img(photos[0]["url"]) if photos else ""
        if img:
            img_total += 1
        key = (cid, poi.get("name", kw))
        if key in seen:
            continue
        seen.add(key)
        spots.append({
            "name": poi.get("name", kw),
            "city_id": cid, "lat": lat, "lng": lng,
            "description": desc, "img_url": img,
            "cost_time_extra": duration,
        })
        print(f"  ✓ {city:<6} {poi.get('name'):<22} 图={'有' if img else '无'} 时长{duration}min")
        time.sleep(0.35)
    print(f"   核心景区完成：{len(spots)} 个，有图 {img_total}")

    # -----------------------------------------------------------------------
    # 2. 25 城城市热搜
    # -----------------------------------------------------------------------
    print(f"\n[2] 处理 {len(city_names)} 城市热搜（keywords='城市 风景名胜'）...")
    for city in city_names:
        if city not in city_ids:
            continue
        cid = city_ids[city]
        pois = search_poi(f"{city} 风景名胜", city=city, citylimit=True, offset=25)
        added = 0
        for p in pois:
            if added >= 12:
                break
            photos = p.get("photos") or []
            if not photos:
                continue  # 城市热搜只取有图的
            loc = parse_location(p.get("location"))
            if not loc:
                continue
            lat, lng = loc
            img = normalize_img(photos[0]["url"])
            name = p.get("name", "")
            if not name or (cid, name) in seen:
                continue
            seen.add((cid, name))
            spots.append({
                "name": name, "city_id": cid, "lat": lat, "lng": lng,
                "description": type_to_desc(p.get("type"), city),
                "img_url": img, "cost_time_extra": 120,
            })
            img_total += 1
            added += 1
        print(f"  {city:<8} 热搜新增 {added} 个有图景点")
        time.sleep(0.35)

    # -----------------------------------------------------------------------
    # 3. 批量写入 spots
    # -----------------------------------------------------------------------
    print(f"\n[3] 待写入 spots {len(spots)} 个，有图 {img_total} ...")
    n = db_writer.batch_upsert_spots(spots)
    print(f"   ✅ 写入完成：{n} 条")

    # -----------------------------------------------------------------------
    # 4. 清理贵州+云南 25 城的"高德导入"占位垃圾（img_url 为空且 description='高德导入'）
    # -----------------------------------------------------------------------
    clean_old_garbage(city_ids, city_names)
    clean_hotels()

    # -----------------------------------------------------------------------
    # 5. 统计
    # -----------------------------------------------------------------------
    print_stats(city_names)


def clean_old_garbage(city_ids, city_names):
    """删除贵州+云南 25 城里 img_url 为空且 description='高德导入' 的占位垃圾景点。"""
    conn = db_writer.get_conn()
    try:
        cids = [city_ids[c] for c in city_names if c in city_ids]
        if not cids:
            return
        ph = ",".join(["%s"] * len(cids))
        with conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM spots WHERE city_id IN ({ph}) "
                f"AND (img_url IS NULL OR img_url='') AND description='高德导入'",
                cids,
            )
            n = cur.rowcount
        conn.commit()
        print(f"\n[4] 清理 '高德导入' 占位垃圾：{n} 条")
    finally:
        conn.close()


def clean_hotels():
    """删除误入 spots 的酒店/客栈/接待中心等非景点 POI（全表范围）。"""
    conn = db_writer.get_conn()
    try:
        # 拼接 LIKE 条件
        like = " OR ".join(["name LIKE %s"] * len(EXCLUDE_WORDS))
        params = [f"%{w}%" for w in EXCLUDE_WORDS]
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM spots WHERE {like}", params)
            n = cur.rowcount
        conn.commit()
        print(f"[4.1] 清理酒店/客栈类垃圾景点：{n} 条")
    finally:
        conn.close()


def print_stats(city_names):
    """打印贵州+云南 spots 最终分布。"""
    conn = db_writer.get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) c FROM spots")
            print(f"\n[5] spots 总数: {cur.fetchone()['c']}")
            cur.execute("""
                SELECT c.name city, COUNT(s.id) n,
                       SUM(CASE WHEN s.img_url IS NOT NULL AND s.img_url<>'' THEN 1 ELSE 0 END) has_img
                FROM spots s JOIN cities c ON s.city_id=c.id
                WHERE c.name IN (%s)
                GROUP BY c.name ORDER BY n DESC
            """ % ",".join(["%s"] * len(city_names)), city_names)
            print(f"\n{'城市':<8} {'总数':>4} {'有图':>4}")
            for r in cur.fetchall():
                print(f"{r['city']:<8} {r['n']:>4} {r['has_img']:>4}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("景点数据爬虫：贵州+云南 → spots（高德 POI，带图片+描述+时长）")
    print("=" * 60)
    build_and_write()
