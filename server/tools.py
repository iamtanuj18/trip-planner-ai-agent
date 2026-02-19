import json

from langchain_core.tools import tool

import knowledge_base as kb
from knowledge_base import USD_TO_AUD

_STYLE_MULTIPLIER: dict[str, float] = {
    "budget":    0.7,
    "mid-range": 1.0,
    "luxury":    1.5,
}


@tool
def search_destinations(
    interests: list[str],
    budget_level: str | None = None,
    season: str | None = None,
    region: str | None = None,
    country: str | None = None,
) -> str:
    """
    Search the knowledge base for destinations matching the user's preferences.

    Call this first for any trip planning request. When the user names a country
    (e.g. "Japan", "Thailand"), pass it as `country` so only cities within that
    country are returned.

    Args:
        interests:    Categories the user enjoys. Valid values: culture, food,
                      adventure, nature, nightlife, shopping, relaxation.
        budget_level: Spending preference. Valid values: budget, mid-range, luxury.
        season:       Travel window. Valid values: spring, summer, autumn, winter.
        region:       Geographic area. Valid values: Asia, Europe, Americas,
                      Oceania, Africa, Middle East.
        country:      Country name filter (e.g. "Japan", "Thailand", "Vietnam").

    Returns:
        JSON list of up to 5 destinations  id, name, country, region,
        description, budget_level, avg_daily_cost_aud, avg_flight_cost_aud,
        best_seasons, visa_notes.
    """
    results = kb.search_destinations(
        interests=interests,
        budget_level=budget_level,
        season=season,
        region=region,
        country=country,
    )

    if not results:
        return json.dumps({
            "error": "No destinations matched. Try broader interests or remove filters."
        })

    return json.dumps(results)


@tool
def get_activities(
    destination_id: str,
    interests: list[str],
    days: int = 3,
) -> str:
    """
    Retrieve curated activities for a destination, prioritised by interests.

    Call this after search_destinations and before build_itinerary.

    Args:
        destination_id: The `id` from a search_destinations result (e.g. "tokyo").
        interests:      Categories to prioritise (same valid values as search_destinations).
        days:           Trip length  controls how many activities are returned (~3 per day).

    Returns:
        JSON list of activities  name, category, duration_hours, cost_usd, description.
    """
    activities = kb.get_activities(
        destination_id=destination_id,
        interests=interests,
        max_results=days * 3,
    )

    if not activities:
        return json.dumps({"error": f"No activities found for '{destination_id}'."})

    return json.dumps(activities)


@tool
def estimate_budget(
    destination_id: str,
    days: int,
    travel_style: str = "mid-range",
) -> str:
    """
    Estimate the total AUD cost for a trip.

    Call this before build_itinerary to anchor real costs. Also use it when
    the user asks whether their budget is achievable.

    Args:
        destination_id: The `id` from a search_destinations result.
        days:           Number of in-destination days (exclude travel days).
        travel_style:   Spending level. Valid values: budget, mid-range, luxury.

    Returns:
        JSON cost breakdown  flights_aud, accommodation_aud, food_aud,
        activities_aud, transport_aud, total_aud, daily_avg_aud, currency.
    """
    dest = kb.get_destination_by_id(destination_id)
    if not dest:
        return json.dumps({"error": f"Destination '{destination_id}' not found."})

    multiplier  = _STYLE_MULTIPLIER.get(travel_style, 1.0)
    daily_base  = dest["avg_daily_cost_usd"] * multiplier * USD_TO_AUD

    accommodation_aud = round(daily_base * 0.40 * days, 2)
    food_aud          = round(daily_base * 0.30 * days, 2)
    transport_aud     = round(daily_base * 0.15 * days, 2)
    activities_aud    = round(daily_base * 0.15 * days, 2)
    flights_aud       = round(dest["avg_flight_cost_usd"] * USD_TO_AUD, 2)
    total_aud         = round(
        flights_aud + accommodation_aud + food_aud + transport_aud + activities_aud, 2
    )

    return json.dumps({
        "destination":       dest["name"],
        "days":              days,
        "travel_style":      travel_style,
        "flights_aud":       flights_aud,
        "accommodation_aud": accommodation_aud,
        "food_aud":          food_aud,
        "activities_aud":    activities_aud,
        "transport_aud":     transport_aud,
        "total_aud":         total_aud,
        "daily_avg_aud":     round((total_aud - flights_aud) / days, 2),
        "currency":          "AUD",
    })


@tool
def build_itinerary(
    destination_id: str,
    days: int,
    interests: list[str],
    travel_style: str = "mid-range",
) -> str:
    """
    Build a structured day-by-day itinerary.

    Call this last  after search_destinations, get_activities, and
    estimate_budget  to produce the final schedule.

    Args:
        destination_id: The `id` from a search_destinations result.
        days:           Number of days in the itinerary.
        interests:      Categories to prioritise when selecting activities.
        travel_style:   Valid values: budget, mid-range, luxury.

    Returns:
        JSON itinerary  destination, days_total, travel_style, a list of day
        objects (day_number, theme, morning, afternoon, evening, tips), and a
        practical_info block (visa, language, currency, best_seasons).
    """
    dest = kb.get_destination_by_id(destination_id)
    if not dest:
        return json.dumps({"error": f"Destination '{destination_id}' not found."})

    activities = kb.get_activities(
        destination_id=destination_id,
        interests=interests,
        max_results=999,
    )

    slots = ["morning", "afternoon", "evening"]

    itinerary = []
    for day_num in range(1, days + 1):
        schedule: dict[str, str] = {}

        for i, slot in enumerate(slots):
            act  = activities[((day_num - 1) * 3 + i) % len(activities)] if activities else None
            if act:
                cost = round(act["cost_usd"] * USD_TO_AUD)
                schedule[slot] = (
                    f"{act['name']} ({act['category']}, ~{act['duration_hours']}h, A${cost})"
                )
            else:
                schedule[slot] = "Free time to explore the local area"

        first_act = activities[((day_num - 1) * 3) % len(activities)] if activities else None
        theme = first_act["category"].capitalize() if first_act else "Exploration"

        itinerary.append({
            "day_number": day_num,
            "theme":      theme,
            "morning":    schedule["morning"],
            "afternoon":  schedule["afternoon"],
            "evening":    schedule["evening"],
            "tips":       dest.get("tips", [])[:2],
        })

    return json.dumps({
        "destination":  dest["name"],
        "country":      dest["country"],
        "days_total":   days,
        "travel_style": travel_style,
        "itinerary":    itinerary,
        "practical_info": {
            "visa_notes":   dest["visa_notes"],
            "language":     dest["language"],
            "currency":     dest["currency"],
            "best_seasons": dest["best_seasons"],
        },
    })


@tool
def list_available_destinations() -> str:
    """
    Return all destinations in the knowledge base.

    Use when the user asks about a destination not found by search_destinations,
    or asks what destinations are available.

    Returns:
        JSON list  id, name, country, region, budget_level, short description.
    """
    return json.dumps([
        {
            "id":           d["id"],
            "name":         d["name"],
            "country":      d["country"],
            "region":       d["region"],
            "budget_level": d["budget_level"],
            "description":  d["description"][:120] + "...",
        }
        for d in kb.get_all_destinations()
    ])


TOOLS = [
    search_destinations,
    get_activities,
    estimate_budget,
    build_itinerary,
    list_available_destinations,
]
