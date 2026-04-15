"""
Google Autocomplete API client.
Returns search suggestions for a keyword.
Docs: https://serpapi.com/google-autocomplete-api
"""
from typing import Any, Dict, List, Optional

from src.services.serpapi_service import SerpApiService


def get_autocomplete(
    q: str,
    *,
    gl: Optional[str] = None,
    hl: Optional[str] = None,
    cp: Optional[int] = None,
    client: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get Google Autocomplete suggestions for a query.

    Args:
        q: Search query for completion options
        gl: Country code (e.g., us, uk)
        hl: Language code (e.g., en, es)
        cp: Cursor position (0 = before query, default end)
        client: Autocomplete client (e.g., chrome, gws-wiz)

    Returns:
        Raw SerpAPI response with 'suggestions' list
    """
    service = SerpApiService()
    return service.search_autocomplete(q, gl=gl, hl=hl, cp=cp, client=client)


def extract_suggestions(response: Dict[str, Any]) -> List[str]:
    """Extract suggestion values from autocomplete response."""
    suggestions = response.get("suggestions", [])
    return [s.get("value", "") for s in suggestions if isinstance(s, dict) and s.get("value")]
