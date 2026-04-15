"""
Google Trends API client.
Interest over time, by region, related topics, related queries.
Docs: https://serpapi.com/google-trends-api
"""
from typing import Any, Dict, Optional

from src.services.serpapi_service import SerpApiService

# data_type options per SerpAPI docs
TRENDS_TIMESERIES = "TIMESERIES"  # Interest over time (default)
TRENDS_GEO_MAP = "GEO_MAP"  # Compared breakdown by region (multiple queries)
TRENDS_GEO_MAP_0 = "GEO_MAP_0"  # Interest by region (single query)
TRENDS_RELATED_TOPICS = "RELATED_TOPICS"
TRENDS_RELATED_QUERIES = "RELATED_QUERIES"


def get_trends(
    q: str,
    *,
    data_type: str = TRENDS_TIMESERIES,
    hl: Optional[str] = None,
    geo: Optional[str] = None,
    region: Optional[str] = None,
    date: Optional[str] = None,
    tz: Optional[int] = None,
    cat: Optional[int] = None,
    gprop: Optional[str] = None,
    csv: Optional[bool] = None,
    include_low_search_volume: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Get Google Trends data.

    Args:
        q: Query or comma-separated queries (max 5 for TIMESERIES/GEO_MAP)
        data_type: TIMESERIES | GEO_MAP | GEO_MAP_0 | RELATED_TOPICS | RELATED_QUERIES
        hl: Language code
        geo: Location (e.g., US, worldwide if empty)
        region: COUNTRY | REGION | DMA | CITY (for GEO_MAP types)
        date: e.g. 'today 12-m', 'now 7-d', 'today 5-y', or custom YYYY-MM-DD YYYY-MM-DD
        tz: Timezone offset in minutes (e.g., -540 for Asia/Tokyo)
        cat: Category ID (0 = All)
        gprop: Web Search (default) | images | news | froogle | youtube
        csv: Return CSV format
        include_low_search_volume: Include low-volume regions (GEO_MAP only)

    Returns:
        Response with interest_over_time, interest_by_region, related_topics,
        related_queries, or compared_breakdown_by_region depending on data_type
    """
    service = SerpApiService()
    return service.search_trends(
        q,
        data_type=data_type,
        hl=hl,
        geo=geo,
        region=region,
        date=date,
        tz=tz,
        cat=cat,
        gprop=gprop,
        csv=csv,
        include_low_search_volume=include_low_search_volume,
    )
