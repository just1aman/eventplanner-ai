import json
import re
import anthropic
from flask import current_app


SYSTEM_PROMPT = """You are EventPlanner.AI, an expert birthday party planner. You create detailed, \
actionable party plans tailored to the user's budget, preferences, and constraints.

Rules:
- Always respect the stated budget range. If the budget is tight, prioritize cost-effective options and DIY alternatives.
- Provide specific, actionable suggestions (not vague advice).
- Include price estimates in USD.
- Consider the age of the honoree when suggesting entertainment and themes.
- For outdoor events, note weather-dependent contingencies.
- Be enthusiastic but practical.

You MUST respond with valid JSON matching the requested schema. Do not include any text outside the JSON object."""


PLAN_GENERATION_PROMPT = """Create a comprehensive birthday party plan based on these details:

- Honoree: {honoree_name}, turning {honoree_age}
- Date: {event_date} at {event_time}
- Location preference: {location_pref}
- City/Area: {location_city}
- Expected guests: {guest_count}
- Budget: ${budget_min} - ${budget_max}
- Theme/vibe: {theme_vibe}
- Additional notes: {additional_notes}

Respond with a JSON object containing these exact keys:

{{
  "venue_suggestions": [
    {{"name": "...", "description": "...", "estimated_cost": "...", "pros": ["..."], "cons": ["..."]}}
  ],
  "decorations": [
    {{"item": "...", "description": "...", "estimated_cost": "...", "where_to_buy": "..."}}
  ],
  "food_catering": {{
    "menu_suggestions": [{{"item": "...", "serves": 10, "estimated_cost": "..."}}],
    "catering_option": {{"description": "...", "estimated_cost": "..."}},
    "diy_option": {{"description": "...", "estimated_cost": "..."}}
  }},
  "entertainment": [
    {{"activity": "...", "description": "...", "duration_minutes": 30, "estimated_cost": "..."}}
  ],
  "day_timeline": [
    {{"time": "...", "activity": "...", "notes": "..."}}
  ],
  "shopping_list": [
    {{"item": "...", "quantity": 1, "estimated_cost": "...", "category": "..."}}
  ],
  "cost_breakdown": {{
    "venue": "...",
    "decorations": "...",
    "food": "...",
    "entertainment": "...",
    "miscellaneous": "...",
    "total_estimated": "..."
  }}
}}"""


REFINEMENT_PROMPT = """The user is refining their birthday party plan. Here is the current full plan:

{current_plan}

The user wants to change the "{section}" section. Their request:
"{user_message}"

Previous conversation about this plan:
{chat_history}

Respond with ONLY the updated JSON for the "{section}" section, using the same schema as the original. Do not include other sections."""


def _get_client():
    return anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])


def _parse_json_response(text):
    """Extract JSON from AI response, handling potential markdown wrapping."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1))
    start = text.index('{')
    end = text.rindex('}') + 1
    return json.loads(text[start:end])


def generate_party_plan(event):
    """Generate a full party plan from event details. Returns (plan_dict, raw_text)."""
    client = _get_client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    user_prompt = PLAN_GENERATION_PROMPT.format(
        honoree_name=event.honoree_name,
        honoree_age=event.honoree_age,
        event_date=event.event_date.strftime('%B %d, %Y'),
        event_time=event.event_time or 'afternoon',
        location_pref=event.location_pref,
        location_city=event.location_city or 'not specified',
        guest_count=event.guest_count,
        budget_min=event.budget_min,
        budget_max=event.budget_max,
        theme_vibe=event.theme_vibe or 'no specific theme',
        additional_notes=event.additional_notes or 'none',
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw_text = response.content[0].text
    plan_dict = _parse_json_response(raw_text)
    return plan_dict, raw_text


def refine_plan_section(event, section_name, user_message, chat_history_text):
    """Refine a specific section of the plan. Returns updated section data."""
    client = _get_client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    current_plan = json.dumps(event.plan.get_all_sections(), indent=2)

    user_prompt = REFINEMENT_PROMPT.format(
        current_plan=current_plan,
        section=section_name,
        user_message=user_message,
        chat_history=chat_history_text or 'No prior conversation.',
    )

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw_text = response.content[0].text
    return _parse_json_response(raw_text)


def generate_checklist_from_plan(plan_dict, event):
    """Convert plan sections into ChecklistItem dicts."""
    from app.services.links import amazon_search_url, google_maps_search_url

    items = []
    order = 0

    # Shopping list items
    for item in plan_dict.get('shopping_list', []):
        items.append({
            'category': 'shopping',
            'title': f"{item.get('item', 'Item')} (x{item.get('quantity', 1)})",
            'description': f"Est. cost: {item.get('estimated_cost', 'N/A')}",
            'sort_order': order,
            'external_url': amazon_search_url(item.get('item', '')),
            'link_type': 'amazon',
        })
        order += 1

    # Venue items
    for venue in plan_dict.get('venue_suggestions', []):
        items.append({
            'category': 'booking',
            'title': f"Check out: {venue.get('name', 'Venue')}",
            'description': venue.get('description', ''),
            'sort_order': order,
            'external_url': google_maps_search_url(
                f"{venue.get('name', '')} {event.location_city or ''}"
            ),
            'link_type': 'google_maps',
        })
        order += 1

    # Decoration items
    for deco in plan_dict.get('decorations', []):
        items.append({
            'category': 'shopping',
            'title': deco.get('item', 'Decoration'),
            'description': f"Est. cost: {deco.get('estimated_cost', 'N/A')} - {deco.get('where_to_buy', '')}",
            'sort_order': order,
            'external_url': amazon_search_url(deco.get('item', '')),
            'link_type': 'amazon',
        })
        order += 1

    # Entertainment items
    for ent in plan_dict.get('entertainment', []):
        items.append({
            'category': 'booking',
            'title': f"Arrange: {ent.get('activity', 'Activity')}",
            'description': f"{ent.get('description', '')} - Est. cost: {ent.get('estimated_cost', 'N/A')}",
            'sort_order': order,
        })
        order += 1

    # Food/catering
    food = plan_dict.get('food_catering', {})
    if food.get('catering_option'):
        items.append({
            'category': 'booking',
            'title': 'Book catering (if using caterer)',
            'description': food['catering_option'].get('description', ''),
            'sort_order': order,
        })
        order += 1

    # Day-of prep items from timeline
    for entry in plan_dict.get('day_timeline', []):
        items.append({
            'category': 'day_of',
            'title': f"{entry.get('time', '')} - {entry.get('activity', '')}",
            'description': entry.get('notes', ''),
            'sort_order': order,
        })
        order += 1

    return items
