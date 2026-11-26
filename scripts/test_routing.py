"""Routing smoke test (Prompt 4): origin -> destination on sample route 1."""

from backend import routing

ORIGIN = (28.71797103184126, 77.06389993096785)   # Rohini Sec 22 Terminal
DEST = (28.707677, 77.178164)                      # Azadpur Terminal
FAR = (28.95, 77.45)                               # >800 m from sample stops


def show(title: str, res: dict) -> None:
    print(f"\n=== {title}")
    for opt in res["options"]:
        print(f"  [{opt['label']}] {opt['duration_min']} min, "
              f"{opt['transfers']} transfers, walk {opt['walk_min']} min")
        for leg in opt["legs"]:
            if leg["type"] == "walk":
                print(f"     walk {leg['from']} -> {leg['to']} "
                      f"({leg['duration_min']} min)")
            else:
                print(f"     BUS {leg['route']}: {leg['from']} -> {leg['to']} "
                      f"({leg['duration_min']} min, {leg['stops']} segs, "
                      f"src={leg['source']})")


def main() -> None:
    res = routing.plan_journeys(*ORIGIN, *DEST)
    show("Rohini Sec 22 -> Azadpur", res)
    assert res["options"], "no options returned"
    opt = res["options"][0]
    assert opt["legs"], "no legs"
    bus = [l for l in opt["legs"] if l["type"] == "bus"]
    assert bus, "expected at least one bus leg"
    assert bus[0]["route"] == "1", bus[0]
    assert opt["duration_min"] > 0

    # same-stop short hop (walk-only candidate may appear)
    res2 = routing.plan_journeys(*ORIGIN, ORIGIN[0] + 0.0005,
                                 ORIGIN[1] + 0.0005)
    show("short hop", res2)

    # error: origin far from any stop
    try:
        routing.plan_journeys(*FAR, *DEST)
        raise AssertionError("expected ValueError for far origin")
    except ValueError as e:
        print(f"\nfar origin -> ValueError OK: {e}")

    # depart_at parsing
    res3 = routing.plan_journeys(*ORIGIN, *DEST, depart_at="08:30")
    assert res3["depart_at"].endswith("T08:30:00+05:30"), res3["depart_at"]
    print(f"depart_at parse OK: {res3['depart_at']}")

    print("\nPASS: routing smoke test")


if __name__ == "__main__":
    main()
