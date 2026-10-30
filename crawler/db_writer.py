# -*- coding: utf-8 -*-
"""
数据库写入模块（pymysql 直连 travel_planner2，不依赖 Flask）
=====================================
提供 4 类写入函数：
  1. ensure_cities()      — 把 config.ALL_CITIES 同步入 cities 表（已存在则更新 is_hot）
  2. get_city_id_map()    — 查 city name -> id 映射，供爬虫拼接外键
  3. upsert_cost_matrix() — 写入/更新 cost_matrix（按 from+to+mode 删旧插新）
  4. upsert_spot()        — 写入/更新 spots（按 city_id+name 去重）
  5. upsert_tip()         — 写入 tip（按 city+title 去重）

设计原则：幂等。多次运行不会产生重复数据，旧数据会被最新爬取结果覆盖。
"""
import pymysql
from pymysql.cursors import DictCursor

import config


# ===========================================================================
# 连接
# ===========================================================================
def get_conn():
    """获取 MySQL 连接（调用方负责 close）"""
    return pymysql.connect(
        host=config.DB_CONFIG["host"],
        port=config.DB_CONFIG["port"],
        user=config.DB_CONFIG["user"],
        password=config.DB_CONFIG["password"],
        database=config.DB_CONFIG["database"],
        charset=config.DB_CONFIG["charset"],
        cursorclass=DictCursor,
        autocommit=False,
    )


# ===========================================================================
# 1. 城市表同步
# ===========================================================================
def ensure_cities(verbose=True):
    """把 config.ALL_CITIES 同步进 cities 表。
    已存在（按 name 匹配）→ 更新 province/lat/lng/is_hot，保留原 id；
    不存在 → 插入。
    返回 {name: id} 映射。
    """
    conn = get_conn()
    id_map = {}
    inserted = updated = 0
    try:
        with conn.cursor() as cur:
            for name, province, lng, lat, is_hot, _q in config.ALL_CITIES:
                cur.execute(
                    "SELECT id FROM cities WHERE name=%s LIMIT 1", (name,)
                )
                row = cur.fetchone()
                if row:
                    cid = row["id"]
                    cur.execute(
                        "UPDATE cities SET province=%s, lat=%s, lng=%s, is_hot=%s "
                        "WHERE id=%s",
                        (province, lat, lng, 1 if is_hot else 0, cid),
                    )
                    updated += 1
                    id_map[name] = cid
                else:
                    cur.execute(
                        "INSERT INTO cities (name, province, hub_name, lat, lng, is_hot) "
                        "VALUES (%s, %s, %s, %s, %s, %s)",
                        (name, province, name, lat, lng, 1 if is_hot else 0),
                    )
                    id_map[name] = cur.lastrowid
                    inserted += 1
        conn.commit()
    finally:
        conn.close()

    if verbose:
        print(f"[cities] 新增 {inserted} 个，更新 {updated} 个，共 {len(id_map)} 个城市")
    return id_map


# ===========================================================================
# 2. 城市 name -> id 映射
# ===========================================================================
def get_city_id_map(verbose=False):
    """从 cities 表读取全部城市的 name -> id 映射。"""
    conn = get_conn()
    id_map = {}
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, province FROM cities")
            for row in cur.fetchall():
                id_map[row["name"]] = row["id"]
    finally:
        conn.close()
    if verbose:
        print(f"[cities] 当前数据库共 {len(id_map)} 个城市")
    return id_map


# ===========================================================================
# 3. cost_matrix 写入（删旧插新，保证最新数据）
# ===========================================================================
def upsert_cost_matrix(from_city_id, to_city_id, mode, time_cost,
                       money_cost, transfer_times=0, discomfort=None):
    """写入一条 cost_matrix 记录。
    若 (from_city_id, to_city_id, mode) 已存在则先删除再插入，保证数据为最新爬取结果。
    discomfort 为 None 时，按 config.MODE_DISCOMFORT 查表取默认系数。
    """
    if mode not in config.VALID_MODES:
        raise ValueError(f"非法交通方式: {mode}，允许: {config.VALID_MODES}")
    if discomfort is None:
        discomfort = config.MODE_DISCOMFORT.get(mode, 8)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM cost_matrix WHERE from_city_id=%s AND to_city_id=%s AND mode=%s",
                (from_city_id, to_city_id, mode),
            )
            cur.execute(
                "INSERT INTO cost_matrix "
                "(from_city_id, to_city_id, mode, time_cost, money_cost, transfer_times, discomfort) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (from_city_id, to_city_id, mode, time_cost, money_cost,
                 transfer_times, discomfort),
            )
        conn.commit()
    finally:
        conn.close()


def batch_upsert_cost_matrix(rows):
    """批量写入 cost_matrix。rows 为 list[dict]，每个 dict 含：
    from_city_id, to_city_id, mode, time_cost, money_cost,
    transfer_times(可选), discomfort(可选)。
    """
    conn = get_conn()
    n = 0
    try:
        with conn.cursor() as cur:
            for r in rows:
                mode = r["mode"]
                if mode not in config.VALID_MODES:
                    continue
                discomfort = r.get("discomfort")
                if discomfort is None:
                    discomfort = config.MODE_DISCOMFORT.get(mode, 8)
                cur.execute(
                    "DELETE FROM cost_matrix WHERE from_city_id=%s AND to_city_id=%s AND mode=%s",
                    (r["from_city_id"], r["to_city_id"], mode),
                )
                cur.execute(
                    "INSERT INTO cost_matrix "
                    "(from_city_id, to_city_id, mode, time_cost, money_cost, transfer_times, discomfort) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (r["from_city_id"], r["to_city_id"], mode,
                     r["time_cost"], r["money_cost"],
                     r.get("transfer_times", 0), discomfort),
                )
                n += 1
        conn.commit()
    finally:
        conn.close()
    return n


# ===========================================================================
# 4. spots 写入（按 city_id + name 去重，已存在则更新）
# ===========================================================================
def upsert_spot(name, city_id, lat, lng, description="", img_url="",
                cost_time_extra=120):
    """写入/更新一个景点。同名同城市则更新描述/图片/时长，否则插入。"""
    conn = get_conn()
    spot_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM spots WHERE name=%s AND city_id=%s LIMIT 1",
                (name, city_id),
            )
            row = cur.fetchone()
            if row:
                spot_id = row["id"]
                cur.execute(
                    "UPDATE spots SET description=%s, img_url=%s, lat=%s, lng=%s, "
                    "cost_time_extra=%s WHERE id=%s",
                    (description[:500], img_url, lat, lng, cost_time_extra, spot_id),
                )
            else:
                cur.execute(
                    "INSERT INTO spots (name, city_id, description, img_url, lat, lng, cost_time_extra) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (name, city_id, description[:500], img_url, lat, lng, cost_time_extra),
                )
                spot_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return spot_id


def batch_upsert_spots(spots):
    """批量写入景点。spots 为 list[dict]：name, city_id, lat, lng,
    description(可选), img_url(可选), cost_time_extra(可选,默认120)。
    """
    conn = get_conn()
    inserted = updated = 0
    try:
        with conn.cursor() as cur:
            for s in spots:
                cur.execute(
                    "SELECT id FROM spots WHERE name=%s AND city_id=%s LIMIT 1",
                    (s["name"], s["city_id"]),
                )
                row = cur.fetchone()
                desc = (s.get("description") or "")[:500]
                img = s.get("img_url", "")
                cte = s.get("cost_time_extra", 120)
                if row:
                    cur.execute(
                        "UPDATE spots SET description=%s, img_url=%s, lat=%s, lng=%s, "
                        "cost_time_extra=%s WHERE id=%s",
                        (desc, img, s["lat"], s["lng"], cte, row["id"]),
                    )
                    updated += 1
                else:
                    cur.execute(
                        "INSERT INTO spots (name, city_id, description, img_url, lat, lng, cost_time_extra) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (s["name"], s["city_id"], desc, img, s["lat"], s["lng"], cte),
                    )
                    inserted += 1
        conn.commit()
    finally:
        conn.close()
    print(f"[spots] 新增 {inserted} 个，更新 {updated} 个")
    return inserted + updated


# ===========================================================================
# 5. tip 写入（按 city+title 去重，已存在则更新）
# ===========================================================================
VALID_CATEGORIES = ("crowd", "transit", "tips", "general")


def upsert_tip(city, category, title, content, priority=50):
    """写入/更新一条出行提示。category ∈ crowd/transit/tips/general。"""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"非法 category: {category}，允许: {VALID_CATEGORIES}")
    conn = get_conn()
    tip_id = None
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM tip WHERE city=%s AND title=%s LIMIT 1",
                (city, title),
            )
            row = cur.fetchone()
            if row:
                tip_id = row["id"]
                cur.execute(
                    "UPDATE tip SET category=%s, content=%s, priority=%s WHERE id=%s",
                    (category, content, priority, tip_id),
                )
            else:
                cur.execute(
                    "INSERT INTO tip (city, category, title, content, priority) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (city, category, title, content, priority),
                )
                tip_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()
    return tip_id


def batch_upsert_tips(tips):
    """批量写入出行提示。tips 为 list[dict]：city, category, title, content,
    priority(可选,默认50)。
    """
    conn = get_conn()
    inserted = updated = 0
    try:
        with conn.cursor() as cur:
            for t in tips:
                cat = t["category"]
                if cat not in VALID_CATEGORIES:
                    continue
                cur.execute(
                    "SELECT id FROM tip WHERE city=%s AND title=%s LIMIT 1",
                    (t["city"], t["title"]),
                )
                row = cur.fetchone()
                pri = t.get("priority", 50)
                if row:
                    cur.execute(
                        "UPDATE tip SET category=%s, content=%s, priority=%s WHERE id=%s",
                        (cat, t["content"], pri, row["id"]),
                    )
                    updated += 1
                else:
                    cur.execute(
                        "INSERT INTO tip (city, category, title, content, priority) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (t["city"], cat, t["title"], t["content"], pri),
                    )
                    inserted += 1
        conn.commit()
    finally:
        conn.close()
    print(f"[tips] 新增 {inserted} 条，更新 {updated} 条")
    return inserted + updated


# ===========================================================================
# 6. 合并同地异名城市（一次性维护）
#    旧州名 → 州府城市名：cost_matrix 引用迁移后删除旧城市记录
# ===========================================================================
DUPLICATE_CITY_MAP = [("黔西南", "兴义"), ("黔南", "都匀")]


def merge_duplicate_cities(dry_run=False):
    """把旧州名城市的 cost_matrix 引用迁移到州府城市，再删除旧城市。
    映射: 黔西南→兴义, 黔南→都匀。迁移后按 (from,to,mode) 去重，保留 id 最小。
    """
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for old_name, new_name in DUPLICATE_CITY_MAP:
                cur.execute("SELECT id FROM cities WHERE name=%s", (old_name,))
                old = cur.fetchone()
                cur.execute("SELECT id FROM cities WHERE name=%s", (new_name,))
                new = cur.fetchone()
                if not old or not new:
                    print(f"  跳过 {old_name}/{new_name}: 城市缺失")
                    continue
                oid, nid = old["id"], new["id"]
                cur.execute(
                    "SELECT COUNT(*) AS c FROM cost_matrix "
                    "WHERE from_city_id=%s OR to_city_id=%s",
                    (oid, oid),
                )
                before = cur.fetchone()["c"]
                if dry_run:
                    print(f"  [DRY] {old_name}(id={oid})→{new_name}(id={nid}): 待迁移{before}条")
                    continue
                cur.execute(
                    "UPDATE cost_matrix SET from_city_id=%s WHERE from_city_id=%s",
                    (nid, oid),
                )
                cur.execute(
                    "UPDATE cost_matrix SET to_city_id=%s WHERE to_city_id=%s",
                    (nid, oid),
                )
                cur.execute(
                    "DELETE c1 FROM cost_matrix c1 "
                    "INNER JOIN cost_matrix c2 "
                    "WHERE c1.id > c2.id "
                    "AND c1.from_city_id = c2.from_city_id "
                    "AND c1.to_city_id = c2.to_city_id "
                    "AND c1.mode = c2.mode"
                )
                dedup = cur.rowcount
                cur.execute("DELETE FROM cities WHERE id=%s", (oid,))
                print(f"  {old_name}(id={oid})→{new_name}(id={nid}): "
                      f"迁移{before}条, 去重删除{dedup}条, 删除旧城市记录")
        conn.commit()
    finally:
        conn.close()


# ===========================================================================
# 自测
# ===========================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("【1】同步城市表")
    id_map = ensure_cities()
    print(f"城市映射: {id_map}")
    print()
    print("【2】查询城市 id 映射")
    print(get_city_id_map(verbose=True))
