from app.extensions import db
from datetime import datetime, timezone


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, index=True)

    role = db.Column(db.String(10), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target_section = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
