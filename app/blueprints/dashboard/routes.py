from flask import render_template, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.blueprints.dashboard import dashboard_bp
from app.extensions import db
from app.models.event import Event
from app.models.checklist import ChecklistItem


@dashboard_bp.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('dashboard/landing.html')
    events = current_user.events.order_by(Event.created_at.desc()).all()
    return render_template('dashboard/index.html', events=events)


@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    events = current_user.events.order_by(Event.created_at.desc()).all()
    return render_template('dashboard/index.html', events=events)


@dashboard_bp.route('/event/<int:event_id>')
@login_required
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)

    # If still in draft, redirect to current wizard step
    if event.status == 'draft':
        step_map = {
            1: 'wizard.generate_loading',
            2: 'wizard.step_venue',
            3: 'wizard.step_food',
            4: 'wizard.step_decorations',
            5: 'wizard.step_entertainment',
        }
        return redirect(url_for(step_map.get(event.current_step, 'wizard.step_venue'),
                                event_id=event.id))

    sections = event.plan.get_all_sections() if event.plan else {}
    selections = event.plan.get_selections() if event.plan else {}

    # Compute the user's actual choices
    selected = {
        'venue': None,
        'food_style': selections.get('food_style'),
        'food_option': None,
        'diy_dishes': selections.get('diy_dishes', ''),
        'diy_shopping_list': selections.get('diy_shopping_list', []),
        'decorations': [],
        'entertainment': [],
    }

    venues = sections.get('venue_suggestions') or []
    venue_idx = selections.get('venue')
    if venue_idx is not None and 0 <= venue_idx < len(venues):
        selected['venue'] = venues[venue_idx]

    food = sections.get('food_catering') or {}
    if selected['food_style'] == 'catering':
        selected['food_option'] = food.get('catering_option')
    elif selected['food_style'] == 'diy':
        selected['food_option'] = food.get('diy_option')

    decorations = sections.get('decorations') or []
    deco_picked = selections.get('decorations_picked', [])
    from app.services.links import amazon_search_url
    for idx in deco_picked:
        if 0 <= idx < len(decorations):
            d = dict(decorations[idx])
            d['amazon_url'] = amazon_search_url(d.get('item', ''))
            selected['decorations'].append(d)

    entertainment = sections.get('entertainment') or []
    ent_picked = selections.get('entertainment_picked', [])
    for idx in ent_picked:
        if 0 <= idx < len(entertainment):
            selected['entertainment'].append(entertainment[idx])

    return render_template('dashboard/event_detail.html',
                           event=event, selected=selected)


@dashboard_bp.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    if event.user_id != current_user.id:
        abort(403)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'info')
    return redirect(url_for('dashboard.index'))
