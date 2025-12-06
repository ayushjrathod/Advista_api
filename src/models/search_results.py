from typing import Any, ClassVar, Dict, List, Optional

from pydantic import BaseModel, Field

from src.models.search_params import SearchParams


class SearchQueryResult(BaseModel):
    """Represents the outcome of a single SerpAPI search invocation"""

    category: str = Field(..., description="Category of the search query (product, competitor, audience, campaign, platform)")
    query: str = Field(..., description="The search query string")
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters sent to SerpAPI")
    response: Optional[Dict[str, Any]] = Field(default=None, description="Raw SerpAPI response payload")
    error: Optional[str] = Field(default=None, description="Error information when the search fails")

    @property
    def has_error(self) -> bool:
        return self.error is not None


class SearchResultsCollection(BaseModel):
    """Aggregates SerpAPI search results grouped by category"""

    product_results: List[SearchQueryResult] = Field(default_factory=list)
    competitor_results: List[SearchQueryResult] = Field(default_factory=list)
    audience_results: List[SearchQueryResult] = Field(default_factory=list)
    campaign_results: List[SearchQueryResult] = Field(default_factory=list)
    platform_results: List[SearchQueryResult] = Field(default_factory=list)

    CATEGORY_TO_ATTR: ClassVar[Dict[str, str]] = {
        "product": "product_results",
        "competitor": "competitor_results",
        "audience": "audience_results",
        "campaign": "campaign_results",
        "platform": "platform_results",
    }

    def add_result(self, result: SearchQueryResult) -> None:
        attr = self.CATEGORY_TO_ATTR.get(result.category)
        if not attr:
            raise ValueError(f"Unsupported result category: {result.category}")
        getattr(self, attr).append(result)

    def is_empty(self) -> bool:
        return not any(getattr(self, attr) for attr in self.CATEGORY_TO_ATTR.values())


class ResearchExecutionResult(BaseModel):
    """Combined payload containing generated search params and corresponding results"""

    search_params: SearchParams
    search_results: SearchResultsCollection

