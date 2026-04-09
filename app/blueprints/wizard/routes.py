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
        return redirect(url_for('wizard.step2_generate', event_id=event.id))

    return render_template('wizard/step1_basics.html', form=form)


@wizard_bp.route('/<int:event_id>/step/2')
@login_required
@require_event_owner
def step2_generate(event):
    if event.current_step > 2 and event.plan:
        return redirect(url_for('wizard.step3_review', event_id=event.id))
    return render_template('wizard/step2_generating.html', event=event)


@wizard_bp.route('/<int:event_id>/generate', methods=['POST'])
@login_required
@require_event_owner
def step2_do_generate(event):
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

    event.current_step = 3
    db.session.commit()

    return jsonify({
        'status': 'success',
        'redirect': url_for('wizard.step3_review', event_id=event.id)
    })


@wizard_bp.route('/<int:event_id>/step/3')
@login_required
@require_event_owner
def step3_review(event):
    if not event.plan:
        return redirect(url_for('wizard.step2_generate', event_id=event.id))

    sections = event.plan.get_all_sections()
    chat_messages = event.chat_messages.all()

    return render_template('wizard/step3_review.html',
                           event=event, sections=sections,
                           chat_messages=chat_messages)


@wizard_bp.route('/<int:event_id>/step/4')
@login_required
@require_event_owner
def step4_actions(event):
    if not event.plan:
        return redirect(url_for('wizard.step2_generate', event_id=event.id))

    checklist_items = event.checklist_items.order_by(
        ChecklistItem.category, ChecklistItem.sort_order
    ).all()

    # Group by category
    grouped = {}
    for item in checklist_items:
        grouped.setdefault(item.category, []).append(item)

    return render_template('wizard/step4_actions.html',
                           event=event, grouped_items=grouped)


@wizard_bp.route('/<int:event_id>/finalize', methods=['POST'])
@login_required
@require_event_owner
def finalize(event):
    event.status = 'planned'
    event.current_step = 4
    db.session.commit()
    flash('Your party plan has been saved!', 'success')
    return redirect(url_for('dashboard.event_detail', event_id=event.id))
