from pydantic import BaseModel, Field
from typing import ClassVar, Dict, Iterable, List, Tuple


class SearchParams(BaseModel):
    """Search parameters generated from research brief for SerpAPI queries"""
    product_search_query: str = Field(
        default="",
        description="Search queries to gather information about the product/service, market positioning, and features"
    )
    competitor_search_query: str = Field(
        default="",
        description="Search queries to analyze competitors, their strategies, pricing, and market presence"
    )
    audience_insight_query: str = Field(
        default="",
        description="Search queries to understand target audience behavior, preferences, demographics, and interests"
    )
    campaign_strategy_query: str = Field(
        default="",
        description="Search queries to find best practices, case studies, and strategies for similar campaigns"
    )
    platform_specific_query: str = Field(
        default="",
        description="Search queries specific to preferred advertising platforms (Google Ads, Facebook, etc.)"
    )

    def get_all_queries(self) -> List[str]:
        """Get all search queries as a list"""
        return [self.product_search_query, self.competitor_search_query, self.audience_insight_query, self.campaign_strategy_query, self.platform_specific_query]
