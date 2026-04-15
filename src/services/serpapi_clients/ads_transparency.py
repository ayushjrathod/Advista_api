"""
Google Ads Transparency Center API client.
Scrape ads by advertiser ID or domain search.
Docs: https://serpapi.com/google-ads-transparency-center-api
"""
from typing import Any, Dict, Optional

from src.services.serpapi_service import SerpApiService

# Platform options per SerpAPI docs
PLATFORM_PLAY = "PLAY"
PLATFORM_MAPS = "MAPS"
PLATFORM_SEARCH = "SEARCH"
PLATFORM_SHOPPING = "SHOPPING"
PLATFORM_YOUTUBE = "YOUTUBE"

# Creative format options
FORMAT_TEXT = "text"
FORMAT_IMAGE = "image"
FORMAT_VIDEO = "video"


def search_ads_transparency(
    *,
    advertiser_id: Optional[str] = None,
    text: Optional[str] = None,
    platform: Optional[str] = None,
    political_ads: Optional[bool] = None,
    region: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    creative_format: Optional[str] = None,
    num: Optional[int] = None,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search Google Ads Transparency Center.
    Requires advertiser_id OR text.

    Args:
        advertiser_id: Google Advertiser ID (e.g., AR17828074650563772417) or comma-separated
        text: Free-text search (e.g., domain like apple.com)
        platform: PLAY | MAPS | SEARCH | SHOPPING | YOUTUBE
        political_ads: True for political ads only (requires region)
        region: Region code (e.g., 2840 for US)
        start_date: YYYYMMDD
        end_date: YYYYMMDD
        creative_format: text | image | video
        num: Max results (default 40)
        next_page_token: Pagination token

    Returns:
        Response with ad_creatives list
    """
    if not advertiser_id and not text:
        raise ValueError("Either advertiser_id or text is required")
    service = SerpApiService()
    return service.search_ads_transparency(
        advertiser_id=advertiser_id,
        text=text,
        platform=platform,
        political_ads=political_ads,
        region=region,
        start_date=start_date,
        end_date=end_date,
        creative_format=creative_format,
        num=num,
        next_page_token=next_page_token,
    )


def extract_ad_creatives(response: Dict[str, Any]) -> list:
    """Extract ad_creatives list from response."""
    return response.get("ad_creatives", [])
