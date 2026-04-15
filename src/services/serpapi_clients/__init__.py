"""
Modular SerpAPI client facades for Google, Amazon, and Maps APIs.
Each module provides focused functions for a specific SerpAPI engine.

Available clients:
- autocomplete: Google Autocomplete suggestions
- related_questions: People-also-ask (initial from Google search, expand via token)
- trends: Google Trends (interest over time, by region, related topics/queries)
- shopping: Google Shopping product results
- ads_transparency: Google Ads Transparency Center
- amazon: Amazon Search (purchase-intent intelligence)
- amazon_reviews: Amazon Product/Reviews (pain-point mining)
- maps_reviews: Google Maps Reviews (audience persona signals)
"""
from src.services.serpapi_clients.autocomplete import get_autocomplete
from src.services.serpapi_clients.related_questions import (
    get_related_questions,
    expand_related_questions,
)
from src.services.serpapi_clients.trends import get_trends
from src.services.serpapi_clients.shopping import search_shopping
from src.services.serpapi_clients.ads_transparency import search_ads_transparency
from src.services.serpapi_clients.amazon import search_amazon
from src.services.serpapi_clients.amazon_reviews import get_amazon_product
from src.services.serpapi_clients.maps_reviews import get_maps_reviews

__all__ = [
    "get_autocomplete",
    "get_related_questions",
    "expand_related_questions",
    "get_trends",
    "search_shopping",
    "search_ads_transparency",
    "search_amazon",
    "get_amazon_product",
    "get_maps_reviews",
]
