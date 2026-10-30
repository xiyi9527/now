# -*- coding: utf-8 -*-
"""验证最终 spots 数据质量：核心景点图片可访问性+描述+坐标。"""
import pymysql, requests
import config

KEY_SPOTS = ["黄果树景区","黔灵山公园","玉龙雪山","梵净山风景区","丽江古城",
             "大理古城","石林风景区","西双版纳热带植物园","普达措","织金洞景区"]
conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config.DB_CONFIG)
try:
    with conn.cursor() as cur:
        ph = ",".join(["%s"]*len(KEY_SPOTS))
        cur.execute(f"""
            SELECT s.name, c.name city, s.img_url, s.description, s.lat, s.lng, s.cost_time_extra
            FROM spots s JOIN cities c ON s.city_id=c.id
            WHERE s.name IN ({ph})""", KEY_SPOTS)
        rows = cur.fetchall()
        print(f"找到 {len(rows)}/{len(KEY_SPOTS)} 个核心景点\n")
        for r in rows:
            img_ok = "?"
            if r["img_url"]:
                try:
                    rr = requests.head(r["img_url"], timeout=8, allow_redirects=True)
                    img_ok = f"HTTP {rr.status_code}"
                except Exception as e:
                    img_ok = f"ERR {str(e)[:30]}"
            print(f"{r['city']:<6} {r['name']:<24} 时长{r['cost_time_extra']}min")
            print(f"     图: {img_ok} | {r['img_url'][:60] if r['img_url'] else '无'}")
            print(f"     描述: {r['description']}")
            print(f"     坐标: {r['lat']},{r['lng']}")
finally:
    conn.close()
