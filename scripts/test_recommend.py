from backend import recommend

for q in ["rohini", "lakh", "rohni", "Rohini Sec", "", "  "]:
    res = recommend.recommend(q)
    print(f"{q!r:14} -> {len(res)} hits:", [(r["name"], r["score"]) for r in res[:4]])
print("total places:", len(recommend.load_places()))
