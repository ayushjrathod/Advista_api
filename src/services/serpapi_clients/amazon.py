"""
Amazon Search API client.
Purchase-intent intelligence: top sellers, price anchors, sponsored products.
Docs: https://serpapi.com/amazon-search-api
"""
from typing import Any, Dict, List, Optional

from src.services.serpapi_service import SerpApiService

# Sort options per SerpAPI docs
SORT_RELEVANCE = "relevanceblender"
SORT_PRICE_LOW = "price-asc-rank"
SORT_PRICE_HIGH = "price-desc-rank"
SORT_REVIEWS = "review-rank"
SORT_NEWEST = "date-desc-rank"
SORT_BEST_SELLERS = "exact-aware-popularity-rank"


def search_amazon(
    k: str,
    *,
    amazon_domain: Optional[str] = None,
    language: Optional[str] = None,
    delivery_zip: Optional[str] = None,
    shipping_location: Optional[str] = None,
    s: Optional[str] = None,
    node: Optional[str] = None,
    page: Optional[int] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search Amazon for products (purchase-intent intelligence).

    Args:
        k: Search query
        amazon_domain: amazon.com (default), amazon.co.uk, etc.
        language: en_US, es_US, ja_JP, etc.
        s: Sort - relevanceblender | price-asc-rank | review-rank | etc.
        node: Category ID filter
        page: Pagination (1-based)

    Returns:
        organic_results, product_ads, sponsored_brands, related_searches
    """
    service = SerpApiService()
    return service.search_amazon(
        k,
        amazon_domain=amazon_domain,
        language=language,
        delivery_zip=delivery_zip,
        shipping_location=shipping_location,
        s=s,
        node=node,
        page=page,
        device=device,
    )


def extract_asins(response: Dict[str, Any], max_count: int = 20) -> List[str]:
    """Extract ASINs from organic results and product_ads for Amazon Product API."""
    asins: List[str] = []
    seen: set = set()

    # organic_results: array of items with asin
    for item in response.get("organic_results", []):
        if isinstance(item, dict) and item.get("asin"):
            aid = item["asin"]
            if aid not in seen:
                seen.add(aid)
                asins.append(aid)
                if len(asins) >= max_count:
                    return asins

    # product_ads: dict with "products" array
    product_ads = response.get("product_ads", {})
    if isinstance(product_ads, dict):
        for item in product_ads.get("products", []):
            if isinstance(item, dict) and item.get("asin"):
                aid = item["asin"]
                if aid not in seen:
                    seen.add(aid)
                    asins.append(aid)
                    if len(asins) >= max_count:
                        return asins
    return asins
