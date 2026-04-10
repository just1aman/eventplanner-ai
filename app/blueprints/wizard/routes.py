from flask import render_template, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from app.blueprints.wizard import wizard_bp
from app.blueprints.wizard.forms import EventBasicsForm
from app.extensions import db
from app.models.event import Event, EventPlan
from app.models.checklist import ChecklistItem
from app.services.ai_planner import generate_party_plan, generate_checklist_from_plan
from app.services.links import amazon_search_url, google_maps_search_url
from functools import wraps


# Step numbering:
# 1 = Event Basics
# 2 = Select Venue
# 3 = Order Food
# 4 = Buy Decorations
# 5 = Book Entertainment
# 6 = Complete


def require_event_owner(f):
    @wraps(f)
    def decorated(event_id, *args, **kwargs):
        event = Event.query.get_or_404(event_id)
        if event.user_id != current_user.id:
            abort(403)
        return f(event=event, *args, **kwargs)
    return decorated


@wizard_bp.route('/new', methods=['GET', 'POST'])
@login_required
def step1_basics():
    form = EventBasicsForm()
    if form.validate_on_submit():
        event = Event(
            user_id=current_user.id,
            honoree_name=form.honoree_name.data,
            honoree_age=form.honoree_age.data,
            event_date=form.event_date.data,
            event_time=form.event_time.data,
            location_pref=form.location_pref.data,
            location_city=form.location_city.data,
            guest_count=form.guest_count.data,
            budget_min=form.budget_min.data,
            budget_max=form.budget_max.data,
            theme_vibe=form.theme_vibe.data,
            additional_notes=form.additional_notes.data,
            current_step=2,
        )
        db.session.add(event)
        db.session.commit()
        return redirect(url_for('wizard.generate_loading', event_id=event.id))

    return render_template('wizard/step1_basics.html', form=form)


@wizard_bp.route('/<int:event_id>/generating')
@login_required
@require_event_owner
def generate_loading(event):
    """Loading transition page that triggers AI generation."""
    if event.plan:
        return redirect(url_for('wizard.step_venue', event_id=event.id))
    return render_template('wizard/generating.html', event=event)


@wizard_bp.route('/<int:event_id>/generate', methods=['POST'])
@login_required
@require_event_owner
def do_generate(event):
    try:
        plan_dict, raw_response = generate_party_plan(event)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    plan = event.plan or EventPlan(event_id=event.id)
    for field in EventPlan.SECTION_FIELDS:
        if field in plan_dict:
            plan.set_section(field, plan_dict[field])
    plan.raw_ai_response = raw_response

    if not event.plan:
        db.session.add(plan)

    # Generate checklist items
    checklist_data = generate_checklist_from_plan(plan_dict, event)
    for item_data in checklist_data:
        item = ChecklistItem(event_id=event.id, **item_data)
        db.session.add(item)

    event.current_step = 2
    db.session.commit()

    return jsonify({
        'status': 'success',
        'redirect': url_for('wizard.step_venue', event_id=event.id)
    })


def _ensure_plan_exists(event):
    if not event.plan:
        return redirect(url_for('wizard.generate_loading', event_id=event.id))
    return None


@wizard_bp.route('/<int:event_id>/venue', methods=['GET', 'POST'])
@login_required
@require_event_owner
def step_venue(event):
    redir = _ensure_plan_exists(event)
    if redir:
        return redir

    venues = event.plan.get_section('venue_suggestions') or []
    selections = event.plan.get_selections()
    selected_idx = selections.get('venue')

    return render_template('wizard/step_venue.html',
                           event=event, venues=venues,
                           selected_idx=selected_idx,
                           current_step=2)


@wizard_bp.route('/<int:event_id>/food', methods=['GET'])
@login_required
@require_event_owner
def step_food(event):
    redir = _ensure_plan_exists(event)
    if redir:
        return redir

    food = event.plan.get_section('food_catering') or {}
    selections = event.plan.get_selections()

    return render_template('wizard/step_food.html',
                           event=event, food=food,
                           selected_style=selections.get('food_style'),
                           current_step=3)


@wizard_bp.route('/<int:event_id>/decorations', methods=['GET'])
@login_required
@require_event_owner
def step_decorations(event):
    redir = _ensure_plan_exists(event)
    if redir:
        return redir

    decorations = event.plan.get_section('decorations') or []
    selections = event.plan.get_selections()
    picked = set(selections.get('decorations_picked', []))

    # Add Amazon link to each
    for i, deco in enumerate(decorations):
        deco['_amazon_url'] = amazon_search_url(deco.get('item', ''))
        deco['_picked'] = i in picked

    return render_template('wizard/step_decorations.html',
                           event=event, decorations=decorations,
                           current_step=4)


@wizard_bp.route('/<int:event_id>/entertainment', methods=['GET'])
@login_required
@require_event_owner
def step_entertainment(event):
    redir = _ensure_plan_exists(event)
    if redir:
        return redir

    entertainment = event.plan.get_section('entertainment') or []
    selections = event.plan.get_selections()
    picked = set(selections.get('entertainment_picked', []))

    for i, ent in enumerate(entertainment):
        ent['_picked'] = i in picked

    return render_template('wizard/step_entertainment.html',
                           event=event, entertainment=entertainment,
                           current_step=5)


@wizard_bp.route('/<int:event_id>/finalize', methods=['POST'])
@login_required
@require_event_owner
def finalize(event):
    event.status = 'planned'
    event.current_step = 6
    db.session.commit()
    flash('Your event is all set!', 'success')
    return redirect(url_for('dashboard.event_detail', event_id=event.id))
