"""
Google Shopping API client.
Product search results with prices, ratings, sources.
Docs: https://serpapi.com/google-shopping-api
"""
from typing import Any, Dict, Optional

from src.services.serpapi_service import SerpApiService


def search_shopping(
    q: str,
    *,
    location: Optional[str] = None,
    uule: Optional[str] = None,
    google_domain: Optional[str] = None,
    gl: Optional[str] = None,
    hl: Optional[str] = None,
    device: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[int] = None,
    free_shipping: Optional[bool] = None,
    start: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Search Google Shopping for products.

    Args:
        q: Product search query
        location: Geographic location
        uule: Google encoded location (alternative to location)
        google_domain: Google domain
        gl: Country code
        hl: Language code
        device: desktop | tablet | mobile
        min_price: Lower price bound
        max_price: Upper price bound
        sort_by: 1 = low to high, 2 = high to low
        free_shipping: Filter for free shipping
        start: Result offset for pagination

    Returns:
        Response with shopping_results list (title, price, source, etc.)
    """
    service = SerpApiService()
    return service.search_shopping(
        q,
        location=location,
        uule=uule,
        google_domain=google_domain,
        gl=gl,
        hl=hl,
        device=device,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        free_shipping=free_shipping,
        start=start,
    )


def extract_shopping_results(response: Dict[str, Any]) -> list:
    """Extract shopping_results list from response."""
    return response.get("shopping_results", [])
