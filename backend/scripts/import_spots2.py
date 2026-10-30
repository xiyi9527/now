"""简化版：直接批量导入"""
import os
import sys, os, time, requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import City, Spot

KEY = os.environ.get("AMAP_KEY", "YOUR_AMAP_KEY")

def search(city_name, keyword="景区", limit=25):
    r = requests.get("https://restapi.amap.com/v3/place/text", params={
        "key": KEY, "output": "JSON", "city": city_name, "citylimit": "true",
        "keywords": keyword, "offset": min(limit, 25), "page": 1,
    }, timeout=10)
    d = r.json()
    if d.get("status") != "1":
        return []
    result = []
    for p in d.get("pois", []):
        ll = p.get("location", "").split(",")
        if len(ll) != 2: continue
        try:
            lng = float(ll[0]); lat = float(ll[1])
        except:
            continue
        result.append({"name": p["name"], "lat": lat, "lng": lng,
                       "typecode": p.get("type", ""), "address": p.get("address", "")})
    return result[:limit]

app = create_app()
with app.app_context():
    cities = City.query.order_by(City.id).all()
    added = skipped = 0

    for city in cities:
        existing = {s.name for s in Spot.query.filter_by(city_id=city.id).all()}
        pois = search(city.name, "景区", 25)
        print(f"{city.name}: got {len(pois)}, adding ", end="")
        n = 0
        for poi in pois:
            if poi["name"] in existing:
                skipped += 1; continue
            db.session.add(Spot(
                name=poi["name"], city_id=city.id,
                description="高德导入" + ((" | " + poi["address"]) if poi["address"] else ""),
                lat=poi["lat"], lng=poi["lng"], cost_time_extra=120,
            ))
            added += 1; n += 1
        db.session.commit()
        print(f"{n} new")
        time.sleep(0.15)

    total = Spot.query.count()
    print(f"\n✅ Done! +{added}, skip {skipped}, total spots: {total}")
