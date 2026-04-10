import json
from flask import request, jsonify, render_template
from flask_login import login_required, current_user
from app.blueprints.api import api_bp
from app.extensions import db
from app.models.event import Event
from app.models.checklist import ChecklistItem
from app.models.chat import ChatMessage
from app.services.ai_planner import refine_plan_section
from app.services.weather import get_forecast_for_date


def _get_user_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        return None
    return event


@api_bp.route('/event/<int:event_id>/chat', methods=['POST'])
@login_required
def chat_refine(event_id):
    event = _get_user_event(event_id)
    if not event:
        return jsonify({'error': 'Forbidden'}), 403
    if not event.plan:
        return jsonify({'error': 'No plan exists yet'}), 400

    data = request.get_json()
    section = data.get('section', '')
    message = data.get('message', '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    # Save user message
    user_msg = ChatMessage(
        event_id=event.id,
        role='user',
        content=message,
        target_section=section,
    )
    db.session.add(user_msg)

    # Build chat history for this section
    history = event.chat_messages.filter_by(target_section=section).all()
    history_text = '\n'.join(
        f"{'User' if m.role == 'user' else 'AI'}: {m.content}" for m in history
    )

    try:
        updated_section = refine_plan_section(event, section, message, history_text)
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'AI refinement failed: {str(e)}'}), 500

    # Update the plan section
    event.plan.set_section(section, updated_section)
    event.plan.version += 1

    # Save AI response
    ai_msg = ChatMessage(
        event_id=event.id,
        role='assistant',
        content=f'Updated the {section.replace("_", " ")} section based on your feedback.',
        target_section=section,
    )
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'updated_section': updated_section,
        'ai_message': ai_msg.content,
    })


@api_bp.route('/checklist/<int:item_id>/toggle', methods=['POST'])
@login_required
def toggle_checklist(item_id):
    item = ChecklistItem.query.get_or_404(item_id)
    event = Event.query.get(item.event_id)
    if not event or event.user_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403

    item.is_completed = not item.is_completed
    db.session.commit()
    return jsonify({'status': 'success', 'completed': item.is_completed})


@api_bp.route('/event/<int:event_id>/weather')
@login_required
def get_weather(event_id):
    event = _get_user_event(event_id)
    if not event:
        return jsonify({'error': 'Forbidden'}), 403

    forecast = get_forecast_for_date(event.event_date, event.location_city or '')
    return jsonify(forecast or {'available': False, 'message': 'No forecast available.'})


@api_bp.route('/event/<int:event_id>/select', methods=['POST'])
@login_required
def save_selection(event_id):
    """Save a user selection for an action step.

    Body shapes:
      - Single value: {"key": "venue", "value": 0}
      - List add/remove: {"key": "decorations_picked", "value": 2, "action": "add"|"remove"}
    """
    event = _get_user_event(event_id)
    if not event or not event.plan:
        return jsonify({'error': 'Forbidden or no plan'}), 403

    data = request.get_json() or {}
    key = data.get('key')
    value = data.get('value')
    action = data.get('action')

    if not key:
        return jsonify({'error': 'Missing key'}), 400

    selections = event.plan.get_selections()

    if action in ('add', 'remove'):
        current_list = selections.get(key, [])
        if not isinstance(current_list, list):
            current_list = []
        if action == 'add' and value not in current_list:
            current_list.append(value)
        elif action == 'remove' and value in current_list:
            current_list.remove(value)
        selections[key] = current_list
    else:
        selections[key] = value

    event.plan.user_selections = json.dumps(selections)
    db.session.commit()

    return jsonify({'status': 'success', 'selections': selections})
