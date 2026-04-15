"""
Google Maps Reviews API client.
Audience persona signals: local demand clusters, lifestyle indicators.
Use with data_id or place_id from Google Maps API.
Docs: https://serpapi.com/google-maps-reviews-api
"""
from typing import Any, Dict, List, Optional

from src.services.serpapi_service import SerpApiService

SORT_QUALITY = "qualityScore"
SORT_NEWEST = "newestFirst"
SORT_RATING_HIGH = "ratingHigh"
SORT_RATING_LOW = "ratingLow"


def get_maps_reviews(
    *,
    data_id: Optional[str] = None,
    place_id: Optional[str] = None,
    hl: Optional[str] = None,
    sort_by: Optional[str] = None,
    query: Optional[str] = None,
    topic_id: Optional[str] = None,
    num: Optional[int] = None,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get Google Maps reviews for a place (audience persona signals).

    Args:
        data_id: Google Maps data ID (from Google Maps API)
        place_id: Google Place ID (alternative to data_id)
        hl: Language code (en, es, fr, etc.)
        sort_by: qualityScore | newestFirst | ratingHigh | ratingLow
        query: Text filter for reviews
        topic_id: Topic filter (cannot use with query)
        num: Results per page (1-20, default 10)
        next_page_token: Pagination token

    Returns:
        place_info, reviews, topics
    """
    service = SerpApiService()
    return service.search_maps_reviews(
        data_id=data_id,
        place_id=place_id,
        hl=hl,
        sort_by=sort_by,
        query=query,
        topic_id=topic_id,
        num=num,
        next_page_token=next_page_token,
    )


def extract_reviews(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract reviews list from response."""
    return response.get("reviews", [])


def extract_place_info(response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract place_info (title, address, rating)."""
    return response.get("place_info")
