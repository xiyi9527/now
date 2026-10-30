"""
一键补全 CostMatrix 缺失边（179/529 → 529/529 = 100%）

遍历所有城市对，跳过已有记录，调用高德驾车 API 填充 time/money/discomfort。
跑完后 DB 里就有完整的城市-城市成本矩阵了，NSGA-II 再也不会遇到 inf 边。

使用方式:
    cd backend
    .venv\\Scripts\\python.exe scripts/fill_cost_matrix.py

可选参数:
    --mode 综合|高铁|自驾    默认 综合
    --dry-run               只统计缺失数量，不真正写入
    --limit N                最多填 N 条（测试用）
    --verbose               打印每条 API 返回
"""
import os
import sys, os, time, argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import City, CostMatrix
from app.utils.amap_router import driving as amap_drive, cache_stats


def main():
    parser = argparse.ArgumentParser(description="Fill cost_matrix from AMap driving API")
    parser.add_argument("--mode", default="综合", help="CostMatrix mode")
    parser.add_argument("--dry-run", action="store_true", help="Count missing only")
    parser.add_argument("--limit", type=int, default=0, help="Max edges to fill (0=all)")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        cities = City.query.order_by(City.id).all()
        N = len(cities)
        print(f"📊 Total cities: {N}")

        # 已有边 (from_city_id, to_city_id, mode) set
        existing = set(
            (r.from_city_id, r.to_city_id, r.mode)
            for r in CostMatrix.query.filter_by(mode=args.mode).all()
        )
        existing_count = len(existing)
        total_pairs = N * (N - 1)  # 排除自环
        missing = [
            (c1, c2)
            for c1 in cities for c2 in cities
            if c1.id != c2.id
            and (c1.id, c2.id, args.mode) not in existing
        ]

        print(f"📊 Existing edges (mode={args.mode}): {existing_count}/{total_pairs} "
              f"= {existing_count/total_pairs*100:.1f}%")
        print(f"📊 Missing edges to fill: {len(missing)}")

        if args.dry_run:
            print("\n🧪 DRY-RUN — no changes made. Done.")
            return

        if not missing:
            print("\n✅ Nothing missing! CostMatrix already 100% covered.")
            return

        if args.limit > 0:
            missing = missing[:args.limit]
            print(f"🔒 Limited to first {args.limit} edges")

        print(f"\n🚀 Starting AMap driving API fill for {len(missing)} edges...")
        print("   (Key: AMAP_KEY 变量, daily free quota: 5000 calls)")
        print()

        success = 0
        failed = 0
        failed_list = []
        t0 = time.time()

        for idx, (c1, c2) in enumerate(missing, 1):
            r = amap_drive(float(c1.lng), float(c1.lat),
                           float(c2.lng), float(c2.lat))
            if r is None:
                failed += 1
                failed_list.append(f"{c1.name}→{c2.name}")
                if args.verbose:
                    print(f"  [{idx}/{len(missing)}] ❌ FAIL  {c1.name} → {c2.name}")
            else:
                # 高德驾车 → time_cost / money_cost / discomfort
                # 单程只填正向（反向如果缺失可以之后再单独补，或用户再跑一次）
                duration_min = int(r["duration_min"])
                distance_km = r["distance_km"]
                tolls = r["tolls_yuan"]
                money = round(tolls + distance_km * 0.3, 2)   # 油费估算: ¥0.3/km
                discomfort = round(distance_km * 0.03, 2)     # 距离越长越累

                edge = CostMatrix(
                    from_city_id=c1.id,
                    to_city_id=c2.id,
                    mode=args.mode,
                    time_cost=duration_min,
                    money_cost=money,
                    transfer_times=0,
                    discomfort=discomfort,
                )
                db.session.add(edge)
                success += 1

                if args.verbose:
                    print(f"  [{idx}/{len(missing)}] ✅ {c1.name} → {c2.name} | "
                          f"{duration_min}min | ¥{money} | {distance_km:.1f}km")

            # 每 10 条 commit 一次，避免大事务
            if idx % 10 == 0:
                db.session.commit()
                elapsed = time.time() - t0
                rate = idx / elapsed if elapsed > 0 else 0
                print(f"   ... {idx}/{len(missing)} done | {success} ok | "
                      f"{failed} fail | {rate:.1f} edges/sec | {elapsed:.0f}s elapsed")

            # 高德 QPS 限制 ~10，sleep 0.1s 够了
            time.sleep(0.1)

        # 最后一次 commit
        db.session.commit()

        elapsed = time.time() - t0
        stats = cache_stats()

        print(f"\n{'='*50}")
        print(f"✅ Done in {elapsed:.1f}s")
        print(f"   Success: {success} edges written to DB")
        print(f"   Failed:  {failed}")
        print(f"   AMap API calls: {stats['api_calls']} (cache hits: {stats['cache_hits']})")
        if failed_list:
            print(f"\n   ⚠️  Failed pairs:")
            for f in failed_list:
                print(f"      - {f}")

        # 验证覆盖率
        new_total = CostMatrix.query.filter_by(mode=args.mode).count()
        after = (new_total, total_pairs, new_total / total_pairs * 100)
        print(f"\n📈 New coverage: {after[0]}/{after[1]} = {after[2]:.1f}%")

        # 反向对称补：如果 A→B 成功了但 B→A 还缺失，直接用同一条数据填上（双向成本近似）
        print(f"\n🔄 Checking reverse symmetry...")
        fill_reverse(missing, args.mode)


def fill_reverse(original_missing, mode):
    """对所有本次新填入的正向边，检查反向是否仍缺失，缺失则直接复制数据。
    这样只跑一次高德就能填满全部 529 条（除了那些真的调用失败的）。"""
    new_edges = CostMatrix.query.filter_by(mode=mode).all()
    new_map = {(r.from_city_id, r.to_city_id): r for r in new_edges}
    added = 0
    for (c1, c2) in original_missing:
        if (c1.id, c2.id) in new_map and (c2.id, c1.id) not in new_map:
            # 反向缺失 → 复制
            src = new_map[(c1.id, c2.id)]
            rev = CostMatrix(
                from_city_id=c2.id,
                to_city_id=c1.id,
                mode=mode,
                time_cost=src.time_cost,
                money_cost=src.money_cost,
                transfer_times=0,
                discomfort=src.discomfort,
            )
            db.session.add(rev)
            new_map[(c2.id, c1.id)] = rev
            added += 1
    if added > 0:
        db.session.commit()
        print(f"   ✅ Added {added} reverse edges from symmetry")
    else:
        print(f"   ✅ All reverse edges already covered")


if __name__ == "__main__":
    main()
