from urllib.parse import quote_plus
from flask import current_app


def amazon_search_url(item_name):
    """Generate Amazon search URL with affiliate tag."""
    tag = current_app.config.get('AMAZON_AFFILIATE_TAG', '')
    base = "https://www.amazon.com/s"
    params = f"?k={quote_plus(item_name)}"
    if tag:
        params += f"&tag={tag}"
    return base + params


def google_maps_search_url(query):
    """Generate Google Maps search URL."""
    return f"https://www.google.com/maps/search/{quote_plus(query)}"
