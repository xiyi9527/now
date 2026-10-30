import os
import requests
KEY = os.environ.get('AMAP_KEY', 'YOUR_AMAP_KEY')

# 高德 direction/transit - 公交规划（同城）
print("=== 公交 direction/transit ===")
r = requests.get('https://restapi.amap.com/v3/direction/transit', params={
    'key': KEY, 'output': 'JSON',
    'origin': '116.397,39.908',
    'destination': '116.410,39.882',
    'city': '北京',
}, timeout=10)
d = r.json()
print("status:", d.get("status"), "info:", d.get("info"))
print("count:", d.get("count", 0))
if d.get("transits"):
    t = d["transits"][0]
    print(f"推荐 duration={t.get('duration')}min distance={t.get('distance')}m")
    segs = t.get("segments", [])
    print(f"segments: {len(segs)}")
    for s in segs[:4]:
        bus = s.get("bus", {})
        bl = bus.get("buslines", [])
        if bl:
            b = bl[0]
            dep = bus.get("departure_stop", {}).get("name", "")
            arr = bus.get("arrival_stop", {}).get("name", "")
            print(f"  🚌 {b.get('name','')} {dep}→{arr} | {s.get('duration')}min | ¥{b.get('price','')}")
        walk = s.get("walking", {})
        if walk:
            print(f"  🚶 walk {walk.get('distance')}m {walk.get('duration')}min")

# 高德 direction/walking - 步行
print("\n=== 步行 direction/walking ===")
r2 = requests.get('https://restapi.amap.com/v3/direction/walking', params={
    'key': KEY, 'output': 'JSON',
    'origin': '116.397,39.908',
    'destination': '116.410,39.882',
}, timeout=10)
d2 = r2.json()
print("status:", d2.get("status"))
route = d2.get("route", {})
print(f"duration={route.get('duration')}s distance={route.get('distance')}m")
steps = route.get("steps", [])
print(f"steps: {len(steps)}")
for s in steps[:3]:
    print(f"  {s.get('instruction', '')[:60]} | {s.get('distance')}m")
