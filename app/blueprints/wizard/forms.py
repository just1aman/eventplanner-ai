from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, DateField, SelectField,
                     TextAreaField, SubmitField)
from wtforms.validators import DataRequired, NumberRange, Optional, Length


class EventBasicsForm(FlaskForm):
    honoree_name = StringField('Who is the birthday for?',
                               validators=[DataRequired(), Length(max=100)])
    honoree_age = IntegerField('How old are they turning?',
                               validators=[DataRequired(), NumberRange(min=1, max=150)])
    event_date = DateField('Event Date', validators=[DataRequired()])
    event_time = StringField('Event Time (e.g., 2:00 PM)',
                             validators=[Optional(), Length(max=20)])
    location_pref = SelectField('Location Preference',
                                choices=[
                                    ('indoor', 'Indoor'),
                                    ('outdoor', 'Outdoor'),
                                    ('venue', 'Rented Venue'),
                                ],
                                validators=[DataRequired()])
    location_city = StringField('City / Area',
                                validators=[DataRequired(), Length(max=100)])
    guest_count = IntegerField('Expected Number of Guests',
                               validators=[DataRequired(), NumberRange(min=1, max=1000)])
    budget_min = IntegerField('Budget Minimum ($)',
                              validators=[DataRequired(), NumberRange(min=0)])
    budget_max = IntegerField('Budget Maximum ($)',
                              validators=[DataRequired(), NumberRange(min=0)])
    theme_vibe = TextAreaField('Theme / Vibe (e.g., tropical, princess, casual BBQ)',
                               validators=[Optional(), Length(max=500)])
    additional_notes = TextAreaField('Anything else we should know?',
                                     validators=[Optional(), Length(max=1000)])
    submit = SubmitField('Generate My Party Plan')
