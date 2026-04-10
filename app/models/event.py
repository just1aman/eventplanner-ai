import json
from app.extensions import db
from datetime import datetime, timezone


class Event(db.Model):
    __tablename__ = 'events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Step 1 — Event Basics
    honoree_name = db.Column(db.String(100), nullable=False)
    honoree_age = db.Column(db.Integer, nullable=False)
    event_date = db.Column(db.Date, nullable=False)
    event_time = db.Column(db.String(20))
    location_pref = db.Column(db.String(20))
    location_city = db.Column(db.String(100))
    guest_count = db.Column(db.Integer)
    budget_min = db.Column(db.Integer)
    budget_max = db.Column(db.Integer)
    theme_vibe = db.Column(db.Text)
    additional_notes = db.Column(db.Text)

    # Wizard state
    current_step = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default='draft')

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    plan = db.relationship('EventPlan', backref='event', uselist=False,
                           cascade='all, delete-orphan')
    checklist_items = db.relationship('ChecklistItem', backref='event', lazy='dynamic',
                                      cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', backref='event', lazy='dynamic',
                                     order_by='ChatMessage.created_at',
                                     cascade='all, delete-orphan')

    @property
    def budget_display(self):
        if self.budget_min and self.budget_max:
            return f"${self.budget_min} - ${self.budget_max}"
        return "Not specified"


class EventPlan(db.Model):
    __tablename__ = 'event_plans'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False, unique=True)

    venue_suggestions = db.Column(db.Text)
    decorations = db.Column(db.Text)
    food_catering = db.Column(db.Text)
    entertainment = db.Column(db.Text)
    day_timeline = db.Column(db.Text)
    shopping_list = db.Column(db.Text)
    cost_breakdown = db.Column(db.Text)

    # User's selections per action step
    # Example: {"venue": 0, "food_style": "catering", "decorations_picked": [0,1,3], "entertainment_picked": [0,2]}
    user_selections = db.Column(db.Text)

    raw_ai_response = db.Column(db.Text)
    version = db.Column(db.Integer, default=1)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    SECTION_FIELDS = [
        'venue_suggestions', 'decorations', 'food_catering',
        'entertainment', 'day_timeline', 'shopping_list', 'cost_breakdown'
    ]

    def get_section(self, name):
        raw = getattr(self, name, None)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def set_section(self, name, data):
        setattr(self, name, json.dumps(data))

    def get_all_sections(self):
        return {f: self.get_section(f) for f in self.SECTION_FIELDS}

    def get_selections(self):
        if self.user_selections:
            try:
                return json.loads(self.user_selections)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    def set_selection(self, key, value):
        sel = self.get_selections()
        sel[key] = value
        self.user_selections = json.dumps(sel)
