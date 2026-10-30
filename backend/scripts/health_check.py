import sys; sys.path.insert(0, '.')
from app import create_app, db
from app.models import City, Spot, CostMatrix, User, Plan

app = create_app()
with app.app_context():
    print(f"Cities: {City.query.count()}")
    print(f"Spots: {Spot.query.count()}")
    print(f"CostMatrix edges: {CostMatrix.query.count()}")
    print(f"Users: {User.query.count()}")
    print(f"Plans: {Plan.query.count()}")
    
    total_possible = City.query.count() * City.query.count()
    print(f"Edge coverage: {CostMatrix.query.count()}/{total_possible} = {CostMatrix.query.count()/total_possible*100:.1f}%")
    
    print("\n--- Spots per city ---")
    for c in City.query.all():
        spots = Spot.query.filter_by(city_id=c.id).all()
        if spots:
            print(f"  {c.name}(id={c.id}): {[s.name for s in spots]}")
    
    print("\n--- CostMatrix modes ---")
    from sqlalchemy import func
    rows = db.session.query(CostMatrix.mode, func.count(CostMatrix.id)).group_by(CostMatrix.mode).all()
    for mode, cnt in rows:
        print(f"  {mode}: {cnt} edges")
    
    print("\n--- Flask routes count ---")
    rules = list(app.url_map.iter_rules())
    print(f"  Total routes: {len(rules)}")
