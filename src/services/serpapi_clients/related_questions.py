"""
Google Related Questions (People Also Ask) API client.
Initial related_questions come from a regular Google search.
Use this client to expand and fetch more questions via next_page_token.
Docs: https://serpapi.com/related-questions
Docs: https://serpapi.com/google-related-questions-api
"""
from typing import Any, Dict, List, Optional

from src.services.serpapi_service import SerpApiService


def get_related_questions(
    query: str,
    *,
    gl: Optional[str] = None,
    hl: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get initial related questions (People also ask) via a Google search.
    The response includes a 'related_questions' block with optional next_page_token
    on each question for expanding.

    Args:
        query: Search query
        gl: Country code
        hl: Language code
        location: Geographic location

    Returns:
        Full Google search response including organic_results and related_questions
    """
    service = SerpApiService()
    params: Dict[str, Any] = {"q": query}
    if gl is not None:
        params["gl"] = gl
    if hl is not None:
        params["hl"] = hl
    if location is not None:
        params["location"] = location
    return service._execute_search("google", params)


def expand_related_questions(
    next_page_token: str,
    *,
    google_domain: Optional[str] = None,
    device: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch more related questions using a next_page_token from a prior
    related_question (simulates clicking a question to load more).

    Args:
        next_page_token: Token from a related_question's next_page_token field
        google_domain: Google domain (default google.com)
        device: desktop | tablet | mobile

    Returns:
        Response with additional related_questions
    """
    service = SerpApiService()
    return service.search_related_questions_expanded(
        next_page_token,
        google_domain=google_domain,
        device=device,
    )


def extract_related_questions(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract related_questions list from a Google or related-questions response."""
    return response.get("related_questions", [])
