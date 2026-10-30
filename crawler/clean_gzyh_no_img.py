# -*- coding: utf-8 -*-
"""清理贵州+云南 25 城里 img_url 为空的 spots（保留有图景点，删旧的无图/非景点）。"""
import pymysql
import config

GUIZHOU = ["贵阳","安顺","遵义","六盘水","毕节","铜仁","凯里","都匀","兴义"]
YUNNAN = ["昆明","曲靖","玉溪","保山","昭通","丽江","普洱","临沧","大理",
          "楚雄","蒙自","文山","景洪","芒市","香格里拉","泸水"]
CITIES = GUIZHOU + YUNNAN

conn = pymysql.connect(cursorclass=pymysql.cursors.DictCursor, **config.DB_CONFIG)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT id,name FROM cities WHERE name IN (%s)" % ",".join(["%s"]*len(CITIES)), CITIES)
        cids = [r["id"] for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) c FROM spots WHERE city_id IN (%s)" % ",".join(["%s"]*len(cids)), cids)
        before = cur.fetchone()["c"]
        cur.execute("DELETE FROM spots WHERE city_id IN (%s) AND (img_url IS NULL OR img_url='')" % ",".join(["%s"]*len(cids)), cids)
        deleted = cur.rowcount
        conn.commit()
        cur.execute("SELECT COUNT(*) c FROM spots WHERE city_id IN (%s)" % ",".join(["%s"]*len(cids)), cids)
        after = cur.fetchone()["c"]
        print(f"贵州+云南 spots: 清理前 {before} → 删除无图 {deleted} → 剩余 {after}")
        # 统计每城
        cur.execute("""
            SELECT c.name city, COUNT(*) n
            FROM spots s JOIN cities c ON s.city_id=c.id
            WHERE c.name IN (%s)
            GROUP BY c.name ORDER BY n DESC
        """ % ",".join(["%s"]*len(CITIES)), CITIES)
        print(f"\n{'城市':<8} {'景点数':>4}")
        for r in cur.fetchall():
            print(f"{r['city']:<8} {r['n']:>4}")
finally:
    conn.close()
