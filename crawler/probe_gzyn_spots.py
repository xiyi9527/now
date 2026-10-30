# -*- coding: utf-8 -*-
"""查贵州+云南25城现有 spots 清单，评估质量。"""
import pymysql
import config

GUIZHOU = ["贵阳","安顺","遵义","六盘水","毕节","铜仁","凯里","都匀","兴义"]
YUNNAN = ["昆明","曲靖","玉溪","保山","昭通","丽江","普洱","临沧","大理",
          "楚雄","蒙自","文山","景洪","芒市","香格里拉","泸水"]
CITIES = GUIZHOU + YUNNAN

conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config.DB_CONFIG)
try:
    with conn.cursor() as cur:
        ph = ",".join(["%s"]*len(CITIES))
        cur.execute(f"""
            SELECT c.name city, s.name spot, s.img_url, s.description, s.cost_time_extra, s.lat, s.lng
            FROM spots s JOIN cities c ON s.city_id=c.id
            WHERE c.name IN ({ph})
            ORDER BY c.name, s.id
        """, CITIES)
        rows = cur.fetchall()
        print(f"贵州+云南 spots 总数: {len(rows)}")
        no_img = sum(1 for r in rows if not r["img_url"])
        no_desc = sum(1 for r in rows if not r["description"] or r["description"]=="高德导入")
        print(f"无图: {no_img}，无描述/占位: {no_desc}\n")
        cur_city = None
        for r in rows:
            if r["city"] != cur_city:
                cur_city = r["city"]
                print(f"\n--- {cur_city} ---")
            img = "有图" if r["img_url"] else "无图"
            desc = (r["description"] or "")[:24]
            print(f"  {r['spot']:<22} {img} | {desc}")
finally:
    conn.close()
