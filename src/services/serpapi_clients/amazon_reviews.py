"""
Amazon Product API client (includes reviews).
Pain-point mining: what customers hate, unmet needs, emotional triggers.
Converts: Complaint → Ad Hook (e.g., "Battery complaints" → "Lasts 2× longer").
Docs: https://serpapi.com/amazon-product-api
"""
from typing import Any, Dict, List, Optional

from src.services.serpapi_service import SerpApiService


def get_amazon_product(
    asin: str,
    *,
    amazon_domain: Optional[str] = None,
    language: Optional[str] = None,
    delivery_zip: Optional[str] = None,
    shipping_location: Optional[str] = None,
    other_sellers: Optional[bool] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get Amazon product details including reviews (pain-point mining).

    Args:
        asin: Amazon Standard Identification Number (from search results)
        amazon_domain: amazon.com (default), etc.
        language: en_US, etc.

    Returns:
        product_results, authors_reviews, reviews_information (top positive/negative)
    """
    service = SerpApiService()
    return service.search_amazon_product(
        asin,
        amazon_domain=amazon_domain,
        language=language,
        delivery_zip=delivery_zip,
        shipping_location=shipping_location,
        other_sellers=other_sellers,
        device=device,
    )


def extract_reviews(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract authors_reviews (individual customer reviews with title, text, rating)."""
    return response.get("product_results", {}).get("authors_reviews", [])


def extract_reviews_summary(response: Dict[str, Any]) -> Optional[str]:
    """Extract AI-generated summary of reviews (pain points, sentiment)."""
    info = response.get("product_results", {}).get("reviews_information", {})
    if isinstance(info, dict):
        summary = info.get("summary", {})
        return summary.get("text") if isinstance(summary, dict) else None
    return None


def extract_review_insights(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract topic insights (sentiment, mentions, examples) for pain-point mining."""
    info = response.get("product_results", {}).get("reviews_information", {})
    if isinstance(info, dict):
        summary = info.get("summary", {})
        return summary.get("insights", []) if isinstance(summary, dict) else []
    return []


def extract_negative_insights(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract negative-sentiment insights for pain-point → ad hook conversion."""
    return [i for i in extract_review_insights(response) if i.get("sentiment") == "negative"]


def extract_positive_insights(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract positive-sentiment insights for value-proposition signals."""
    return [i for i in extract_review_insights(response) if i.get("sentiment") == "positive"]
