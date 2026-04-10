"""
Agentic AI planner using Claude's tool-use API.

The agent is given a set of tools (search_places, get_weather_forecast,
build_amazon_search_url, submit_final_plan) and loops through:
  think → call tool → observe result → think → ...
until it calls submit_final_plan with the complete party plan.
"""
import json
import re
import anthropic
from flask import current_app
from app.services.tools import TOOL_SCHEMAS, execute_tool


MAX_AGENT_ITERATIONS = 15


SYSTEM_PROMPT = """You are EventPlanner.AI, an expert AI agent that plans real birthday parties.

You have access to tools that let you search for actual venues, check the weather, and build Amazon \
shopping links. Use them to create a plan grounded in real data, not just your training knowledge.

Your process:
1. Start by searching for real venues in the user's city that match their preferences and budget.
2. If the event is within 5 days, check the weather forecast — this affects whether outdoor options work.
3. Search for additional services as needed (caterers, party supply stores, entertainment providers).
4. Build Amazon URLs for the shopping list items.
5. When you have enough information, call submit_final_plan with the complete, structured plan.

Important rules:
- ALWAYS try search_places at least once before making venue recommendations.
- Respect the budget strictly. If the budget is tight, prioritize DIY and low-cost options.
- Consider the honoree's age when picking activities.
- For outdoor events within 5 days, ALWAYS check weather first.
- Call submit_final_plan EXACTLY ONCE at the end with the complete plan.
- If a tool returns an error (e.g., API not configured), continue with your general knowledge and note \
  that the data is estimated.
- Be specific and actionable. Include real venue names from search results when possible.
"""


def _build_initial_prompt(event):
    return f"""Plan a birthday party with these details:

- Honoree: {event.honoree_name}, turning {event.honoree_age}
- Date: {event.event_date.strftime('%Y-%m-%d')} ({event.event_date.strftime('%A, %B %d, %Y')}) at {event.event_time or 'afternoon'}
- Location preference: {event.location_pref}
- City/Area: {event.location_city or 'not specified'}
- Expected guests: {event.guest_count}
- Budget: ${event.budget_min} - ${event.budget_max}
- Theme/vibe: {event.theme_vibe or 'no specific theme'}
- Additional notes: {event.additional_notes or 'none'}

Start by searching for real venues, then build the complete plan. Call submit_final_plan when done."""


def _get_client():
    return anthropic.Anthropic(api_key=current_app.config['ANTHROPIC_API_KEY'])


def generate_party_plan(event):
    """Run the agentic planning loop. Returns (plan_dict, raw_trace_text).

    The raw trace captures all tool calls and responses for debugging.
    """
    client = _get_client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    messages = [{"role": "user", "content": _build_initial_prompt(event)}]
    trace_lines = []
    final_plan = None

    for iteration in range(MAX_AGENT_ITERATIONS):
        trace_lines.append(f"\n--- Iteration {iteration + 1} ---")

        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Log text blocks
        for block in response.content:
            if getattr(block, 'type', None) == 'text' and block.text.strip():
                trace_lines.append(f"[think] {block.text[:500]}")

        # If the model is done without calling a tool, break
        if response.stop_reason == "end_turn":
            trace_lines.append("[end_turn] Agent finished without calling submit_final_plan")
            break

        if response.stop_reason != "tool_use":
            trace_lines.append(f"[stop_reason] Unexpected: {response.stop_reason}")
            break

        # Process tool calls
        tool_results = []
        submitted = False

        for block in response.content:
            if getattr(block, 'type', None) != 'tool_use':
                continue

            tool_name = block.name
            tool_input = block.input or {}
            trace_lines.append(f"[tool_call] {tool_name}({json.dumps(tool_input)[:300]})")

            if tool_name == "submit_final_plan":
                # Capture the final plan and return a success result
                final_plan = tool_input
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": "Plan received. Thank you!",
                })
                submitted = True
            else:
                result = execute_tool(tool_name, tool_input)
                result_str = json.dumps(result)
                trace_lines.append(f"[tool_result] {result_str[:500]}")
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_str,
                })

        # Append assistant turn and tool results to conversation
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if submitted:
            trace_lines.append("[submit_final_plan] Plan submitted, exiting loop")
            break

    if final_plan is None:
        raise RuntimeError(
            "Agent did not submit a final plan within "
            f"{MAX_AGENT_ITERATIONS} iterations. Trace:\n" + "\n".join(trace_lines)
        )

    raw_trace = "\n".join(trace_lines)
    return final_plan, raw_trace


def refine_plan_section(event, section_name, user_message, chat_history_text):
    """Simple single-shot refinement (non-agentic) for backwards compatibility."""
    client = _get_client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    current_plan = json.dumps(event.plan.get_all_sections(), indent=2)

    prompt = f"""The user is refining their birthday party plan. Here is the current full plan:

{current_plan}

The user wants to change the "{section_name}" section. Their request:
"{user_message}"

Previous conversation about this plan:
{chat_history_text or 'No prior conversation.'}

Respond with ONLY the updated JSON for the "{section_name}" section, using the same schema as the original. Do not include other sections or any text outside the JSON."""

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system="You are EventPlanner.AI. Respond only with valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    # Try direct parse, then fallback to brace extraction
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
    if match:
        return json.loads(match.group(1))
    start = raw_text.index('{')
    end = raw_text.rindex('}') + 1
    return json.loads(raw_text[start:end])


def generate_diy_shopping_list(dishes_description, guest_count):
    """Generate a shopping list of ingredients for DIY food.

    Returns a list of dicts: [{"item": str, "quantity": str, "category": str}, ...]
    """
    client = _get_client()
    model = current_app.config.get('ANTHROPIC_MODEL', 'claude-sonnet-4-20250514')

    prompt = f"""I'm cooking food for {guest_count} guests at a birthday party. Here's what I want to make:

{dishes_description}

Generate a complete shopping list of ingredients I need to buy. Include realistic quantities for {guest_count} people.

Respond with ONLY valid JSON in this exact format:
{{
  "items": [
    {{"item": "ingredient name", "quantity": "e.g., 2 lbs or 1 jar", "category": "produce|meat|dairy|pantry|drinks|other"}}
  ]
}}
Do not include any text outside the JSON."""

    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system="You are a helpful cooking assistant. Respond only with valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_text)
        if match:
            data = json.loads(match.group(1))
        else:
            start = raw_text.index('{')
            end = raw_text.rindex('}') + 1
            data = json.loads(raw_text[start:end])

    return data.get('items', [])


def generate_checklist_from_plan(plan_dict, event):
    """Convert plan sections into ChecklistItem dicts."""
    from app.services.links import amazon_search_url, google_maps_search_url

    items = []
    order = 0

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

    for venue in plan_dict.get('venue_suggestions', []):
        items.append({
            'category': 'booking',
            'title': f"Check out: {venue.get('name', 'Venue')}",
            'description': venue.get('description', '') or venue.get('address', ''),
            'sort_order': order,
            'external_url': google_maps_search_url(
                f"{venue.get('name', '')} {event.location_city or ''}"
            ),
            'link_type': 'google_maps',
        })
        order += 1

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

    for ent in plan_dict.get('entertainment', []):
        items.append({
            'category': 'booking',
            'title': f"Arrange: {ent.get('activity', 'Activity')}",
            'description': f"{ent.get('description', '')} - Est. cost: {ent.get('estimated_cost', 'N/A')}",
            'sort_order': order,
        })
        order += 1

    food = plan_dict.get('food_catering', {})
    if food.get('catering_option'):
        items.append({
            'category': 'booking',
            'title': 'Book catering (if using caterer)',
            'description': food['catering_option'].get('description', ''),
            'sort_order': order,
        })
        order += 1

    for entry in plan_dict.get('day_timeline', []):
        items.append({
            'category': 'day_of',
            'title': f"{entry.get('time', '')} - {entry.get('activity', '')}",
            'description': entry.get('notes', ''),
            'sort_order': order,
        })
        order += 1

    return items
