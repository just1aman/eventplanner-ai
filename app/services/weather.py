import requests
from flask import current_app
from datetime import date


def get_forecast_for_date(event_date, location):
    """
    Fetch weather forecast for event date.
    OpenWeatherMap free tier provides 5-day/3-hour forecast.
    Returns a dict with forecast info, or None on failure.
    """
    api_key = current_app.config.get('OPENWEATHER_API_KEY')
    if not api_key:
        return {'available': False, 'message': 'Weather service not configured.'}

    days_until = (event_date - date.today()).days
    if days_until < 0:
        return {'available': False, 'message': 'Event date has passed.'}
    if days_until > 5:
        return {
            'available': False,
            'message': f'Weather forecast will be available about {days_until - 5} days before the event.'
        }

    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={
                'q': location,
                'appid': api_key,
                'units': 'imperial',
                'cnt': 40,
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return {'available': False, 'message': 'Could not fetch weather data.'}

        data = resp.json()
        date_str = event_date.isoformat()
        day_forecasts = [
            entry for entry in data.get('list', [])
            if entry.get('dt_txt', '').startswith(date_str)
        ]

        if not day_forecasts:
            return {'available': False, 'message': 'No forecast data for this date.'}

        midday = next(
            (f for f in day_forecasts if '12:00:00' in f.get('dt_txt', '')),
            day_forecasts[0]
        )

        return {
            'available': True,
            'temp': round(midday['main']['temp']),
            'description': midday['weather'][0]['description'].title(),
            'icon': midday['weather'][0]['icon'],
            'humidity': midday['main']['humidity'],
            'wind_speed': round(midday['wind']['speed']),
        }
    except Exception:
        return {'available': False, 'message': 'Weather service temporarily unavailable.'}
