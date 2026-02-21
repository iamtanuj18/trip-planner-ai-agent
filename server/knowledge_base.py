import json
import os as _os
from pathlib import Path

_DATA_FILE = Path(__file__).parent / "data" / "destinations.json"

with open(_DATA_FILE, "r", encoding="utf-8") as _f:
    _destinations: list[dict] = json.load(_f)

USD_TO_AUD: float = float(_os.getenv("USD_TO_AUD", "1.55"))

_BUDGET_RANK: dict[str, int] = {"budget": 1, "mid-range": 2, "luxury": 3}


def search_destinations(
    interests: list[str],
    budget_level: str | None = None,
    season: str | None = None,
    region: str | None = None,
    country: str | None = None,
    top_n: int = 5,
) -> list[dict]:
    """
    Score and return the top matching destinations.
    """
    interest_set = {i.lower() for i in interests}
    scored: list[tuple[int, dict]] = []

    for dest in _destinations:
        if country and dest.get("country", "").lower() != country.lower():
            continue

        score = 0

        activity_cats = {a["category"] for a in dest.get("activities", [])}
        score += len(interest_set & activity_cats) * 2

        if budget_level:
            dest_rank = _BUDGET_RANK.get(dest["budget_level"], 0)
            req_rank = _BUDGET_RANK.get(budget_level, 0)
            if dest_rank == req_rank:
                score += 2
            elif abs(dest_rank - req_rank) == 1:
                score += 1

        if season and season.lower() in dest.get("best_seasons", []):
            score += 2

        if region and region.lower() == dest.get("region", "").lower():
            score += 1

        # If the country filter matched but interest/budget/season scoring gave
        # nothing, guarantee at least score=1 so a valid city never silently
        # vanishes due to interest category mismatch.
        if score == 0 and country:
            score = 1

        if score > 0:
            scored.append((score, dest))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "id":                  d["id"],
            "name":                d["name"],
            "country":             d["country"],
            "region":              d["region"],
            "description":         d["description"],
            "budget_level":        d["budget_level"],
            "avg_daily_cost_aud":  round(d["avg_daily_cost_usd"] * USD_TO_AUD),
            "avg_flight_cost_aud": round(d["avg_flight_cost_usd"] * USD_TO_AUD),
            "best_seasons":        d["best_seasons"],
            "visa_notes":          d["visa_notes"],
            "score":               score,
        }
        for score, d in scored[:top_n]
    ]


def get_activities(
    destination_id: str,
    interests: list[str],
    max_results: int = 8,
) -> list[dict]:
    """
    Return activities for a destination, interest-matched activities first.
    """
    dest = get_destination_by_id(destination_id)
    if not dest:
        return []

    interest_set = {i.lower() for i in interests}
    activities = dest.get("activities", [])

    matched = [a for a in activities if a["category"] in interest_set]
    others  = [a for a in activities if a["category"] not in interest_set]

    return (matched + others)[:max_results]


def get_destination_by_id(destination_id: str) -> dict | None:
    return next((d for d in _destinations if d["id"] == destination_id), None)


def get_all_destinations() -> list[dict]:
    return list(_destinations)
