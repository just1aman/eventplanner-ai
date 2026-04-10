"""
Tool implementations for the AI agent.

Each tool function takes keyword arguments matching its Claude tool schema
and returns a JSON-serializable dict. Tools should never raise exceptions to
the agent loop — they return {"error": "..."} on failure so Claude can
reason about the result.
"""
import requests
from flask import current_app
from urllib.parse import quote_plus
from datetime import date as date_cls


# ---------- Tool schemas for Claude tool use ----------

TOOL_SCHEMAS = [
    {
        "name": "search_places",
        "description": (
            "Search for real venues, restaurants, caterers, or event spaces in a specific city using "
            "Google Places. Returns a list of actual businesses with names, addresses, ratings, and "
            "price levels. Use this to find real venues for the party instead of guessing. "
            "You can call this multiple times with different queries (e.g., once for venues, once "
            "for caterers, once for party supply stores)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to search for, e.g., 'kids birthday party venue', 'restaurant with private room', "
                        "'catering service', 'party supply store', 'trampoline park'"
                    ),
                },
                "city": {
                    "type": "string",
                    "description": "City or area to search in, e.g., 'Austin, TX'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5, max 10)",
                    "default": 5,
                },
            },
            "required": ["query", "city"],
        },
    },
    {
        "name": "get_weather_forecast",
        "description": (
            "Get the weather forecast for the event date and location. Only works if the event is "
            "within the next 5 days. Use this to decide whether outdoor activities are feasible and "
            "whether contingency plans are needed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City to get weather for"},
                "date": {
                    "type": "string",
                    "description": "Event date in YYYY-MM-DD format",
                },
            },
            "required": ["city", "date"],
        },
    },
    {
        "name": "build_amazon_search_url",
        "description": (
            "Build an Amazon search URL for a shopping item. Use this for any decoration, supply, "
            "or product the user will need to buy. The URL includes an affiliate tag."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_name": {
                    "type": "string",
                    "description": "Product to search for, e.g., 'gold balloons pack'",
                }
            },
            "required": ["item_name"],
        },
    },
    {
        "name": "submit_final_plan",
        "description": (
            "Submit the final, complete party plan. Only call this ONCE, after you have gathered "
            "enough information via other tools. The plan must include all sections: venues, food, "
            "decorations, entertainment, timeline, shopping list, and cost breakdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "venue_suggestions": {
                    "type": "array",
                    "description": "List of 2-4 venue options the user can choose from",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "description": {"type": "string"},
                            "estimated_cost": {"type": "string"},
                            "pros": {"type": "array", "items": {"type": "string"}},
                            "cons": {"type": "array", "items": {"type": "string"}},
                            "address": {"type": "string", "description": "Real address if found via search_places, else empty"},
                            "rating": {"type": "number", "description": "Google rating if available, else 0"},
                        },
                        "required": ["name", "description", "estimated_cost", "pros", "cons"],
                    },
                },
                "food_catering": {
                    "type": "object",
                    "properties": {
                        "menu_suggestions": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item": {"type": "string"},
                                    "serves": {"type": "integer"},
                                    "estimated_cost": {"type": "string"},
                                },
                                "required": ["item", "serves", "estimated_cost"],
                            },
                        },
                        "catering_option": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "estimated_cost": {"type": "string"},
                            },
                            "required": ["description", "estimated_cost"],
                        },
                        "diy_option": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "estimated_cost": {"type": "string"},
                            },
                            "required": ["description", "estimated_cost"],
                        },
                    },
                    "required": ["menu_suggestions", "catering_option", "diy_option"],
                },
                "decorations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "description": {"type": "string"},
                            "estimated_cost": {"type": "string"},
                            "where_to_buy": {"type": "string"},
                        },
                        "required": ["item", "description", "estimated_cost", "where_to_buy"],
                    },
                },
                "entertainment": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "activity": {"type": "string"},
                            "description": {"type": "string"},
                            "duration_minutes": {"type": "integer"},
                            "estimated_cost": {"type": "string"},
                        },
                        "required": ["activity", "description", "duration_minutes", "estimated_cost"],
                    },
                },
                "day_timeline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time": {"type": "string"},
                            "activity": {"type": "string"},
                            "notes": {"type": "string"},
                        },
                        "required": ["time", "activity"],
                    },
                },
                "shopping_list": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "estimated_cost": {"type": "string"},
                            "category": {"type": "string"},
                        },
                        "required": ["item", "quantity", "estimated_cost", "category"],
                    },
                },
                "cost_breakdown": {
                    "type": "object",
                    "properties": {
                        "venue": {"type": "string"},
                        "decorations": {"type": "string"},
                        "food": {"type": "string"},
                        "entertainment": {"type": "string"},
                        "miscellaneous": {"type": "string"},
                        "total_estimated": {"type": "string"},
                    },
                    "required": ["venue", "decorations", "food", "entertainment", "miscellaneous", "total_estimated"],
                },
            },
            "required": [
                "venue_suggestions", "food_catering", "decorations",
                "entertainment", "day_timeline", "shopping_list", "cost_breakdown",
            ],
        },
    },
]


# ---------- Tool implementations ----------

def search_places(query, city, max_results=5):
    """Call Google Places Text Search API."""
    api_key = current_app.config.get('GOOGLE_PLACES_API_KEY')
    if not api_key:
        return {
            "error": "Google Places API is not configured. Fall back to generating suggestions from general knowledge.",
            "results": [],
        }

    max_results = min(int(max_results or 5), 10)
    full_query = f"{query} in {city}"

    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": full_query, "key": api_key},
            timeout=10,
        )
        if resp.status_code != 200:
            return {"error": f"Google Places returned HTTP {resp.status_code}", "results": []}
        data = resp.json()
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            return {
                "error": f"Google Places status: {data.get('status')} - {data.get('error_message', '')}",
                "results": [],
            }

        results = []
        for place in data.get("results", [])[:max_results]:
            results.append({
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating", 0),
                "total_ratings": place.get("user_ratings_total", 0),
                "price_level": place.get("price_level"),  # 0-4
                "types": place.get("types", [])[:3],
                "place_id": place.get("place_id"),
            })
        return {"query": full_query, "results": results}
    except requests.RequestException as e:
        return {"error": f"Network error: {str(e)}", "results": []}


def get_weather_forecast(city, date):
    """Wraps the existing weather service for agent use."""
    from app.services.weather import get_forecast_for_date
    try:
        parsed_date = date_cls.fromisoformat(date)
    except (ValueError, TypeError):
        return {"error": f"Invalid date format: {date}. Expected YYYY-MM-DD."}

    result = get_forecast_for_date(parsed_date, city)
    return result or {"available": False, "message": "No forecast data available."}


def build_amazon_search_url(item_name):
    """Build an Amazon affiliate search URL."""
    tag = current_app.config.get('AMAZON_AFFILIATE_TAG', '')
    url = f"https://www.amazon.com/s?k={quote_plus(item_name)}"
    if tag:
        url += f"&tag={tag}"
    return {"item": item_name, "url": url}


# ---------- Tool dispatcher ----------

TOOL_FUNCTIONS = {
    "search_places": search_places,
    "get_weather_forecast": get_weather_forecast,
    "build_amazon_search_url": build_amazon_search_url,
}


def execute_tool(name, inputs):
    """Execute a named tool with keyword inputs. Returns the tool's result dict."""
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**(inputs or {}))
    except TypeError as e:
        return {"error": f"Invalid tool arguments: {str(e)}"}
    except Exception as e:
        return {"error": f"Tool execution failed: {str(e)}"}
