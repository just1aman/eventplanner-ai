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

    checklist_items = event.checklist_items.order_by(
        ChecklistItem.category, ChecklistItem.sort_order
    ).all()

    grouped = {}
    for item in checklist_items:
        grouped.setdefault(item.category, []).append(item)

    sections = event.plan.get_all_sections() if event.plan else {}

    return render_template('dashboard/event_detail.html',
                           event=event, sections=sections,
                           grouped_items=grouped)


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
