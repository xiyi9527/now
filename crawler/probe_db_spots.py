# -*- coding: utf-8 -*-
"""查看现有 spots 表数据量和分布，判断补图还是重爬。"""
import pymysql
import config

conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config.DB_CONFIG)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) c FROM spots")
        print(f"spots 总数: {cur.fetchone()['c']}")

        cur.execute("""
            SELECT c.name city, COUNT(s.id) n,
                   SUM(CASE WHEN s.img_url IS NULL OR s.img_url='' THEN 1 ELSE 0 END) no_img,
                   SUM(CASE WHEN s.description IS NULL OR s.description='' OR s.description='高德导入' THEN 1 ELSE 0 END) no_desc
            FROM spots s JOIN cities c ON s.city_id=c.id
            GROUP BY c.name ORDER BY n DESC
        """)
        print(f"\n{'城市':<8} {'数量':>4} {'无图':>4} {'无描述':>4}")
        for r in cur.fetchall():
            print(f"{r['city']:<8} {r['n']:>4} {r['no_img']:>4} {r['no_desc']:>4}")

        print("\n样例景点(前15):")
        cur.execute("""
            SELECT s.name, c.name city, s.img_url, s.description, s.cost_time_extra
            FROM spots s JOIN cities c ON s.city_id=c.id
            ORDER BY s.id LIMIT 15
        """)
        for r in cur.fetchall():
            img = "有图" if r["img_url"] else "无图"
            desc = (r["description"] or "")[:20]
            print(f"  {r['city']:<6} {r['name']:<20} {img} | {desc}")
finally:
    conn.close()
