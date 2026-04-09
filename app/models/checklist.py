from app.extensions import db
from datetime import datetime, timezone


class ChecklistItem(db.Model):
    __tablename__ = 'checklist_items'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)

    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, default=False)
    due_date = db.Column(db.Date)
    sort_order = db.Column(db.Integer, default=0)

    external_url = db.Column(db.String(500))
    link_type = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
