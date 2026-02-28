from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OrganicResult(BaseModel):
    """Represents a single organic search result"""
    position: int = Field(default=0, description="Position in search results")
    title: str = Field(default="", description="Title of the result")
    link: str = Field(default="", description="URL of the result")
    snippet: str = Field(default="", description="Snippet/description of the result")
    source: str = Field(default="", description="Source website name")
    date: Optional[str] = Field(default=None, description="Date if available")


class RelatedQuestion(BaseModel):
    """Represents a 'People also ask' question with answer"""
    question: str = Field(default="", description="The question")
    answer: str = Field(default="", description="The answer snippet")
    source_title: Optional[str] = Field(default=None, description="Source title")
    source_link: Optional[str] = Field(default=None, description="Source URL")


class AIOverview(BaseModel):
    """Represents Google's AI-generated overview"""
    snippets: List[str] = Field(default_factory=list, description="AI overview text snippets")
    key_points: List[str] = Field(default_factory=list, description="Key bullet points from AI overview")


class CategoryInsights(BaseModel):
    """Processed insights for a single search category"""
    category: str = Field(default="", description="Category name (product, competitor, etc.)")
    query: str = Field(default="", description="Original search query")
    total_results: int = Field(default=0, description="Total results found")
    
    # Processed data
    top_results: List[OrganicResult] = Field(default_factory=list, description="Top organic results")
    related_questions: List[RelatedQuestion] = Field(default_factory=list, description="Related Q&A")
    ai_overview: AIOverview = Field(default_factory=AIOverview, description="AI overview if available")
    
    # Extracted key information
    key_snippets: List[str] = Field(default_factory=list, description="Most relevant text snippets")
    sources: List[str] = Field(default_factory=list, description="Unique source domains")


class YouTubeVideoResult(BaseModel):
    """A YouTube video with transcript"""
    title: str = Field(default="", description="Video title")
    link: str = Field(default="", description="Video URL")
    channel: str = Field(default="", description="Channel name")
    published_date: str = Field(default="", description="Publication date")
    views: Optional[int] = Field(default=None, description="View count")
    length: str = Field(default="", description="Duration")
    description: str = Field(default="", description="Video description")
    video_id: str = Field(default="", description="YouTube video ID")
    transcript: str = Field(default="", description="Extracted transcript text")


class YouTubeShortResult(BaseModel):
    """A YouTube Short with transcript"""
    title: str = Field(default="", description="Short title")
    link: str = Field(default="", description="Short URL")
    views: Optional[int] = Field(default=None, description="View count")
    views_original: str = Field(default="", description="Views as displayed")
    video_id: str = Field(default="", description="YouTube video ID")
    transcript: str = Field(default="", description="Extracted transcript text")


class YouTubeInsights(BaseModel):
    """YouTube research: top videos and shorts with transcripts"""
    query: str = Field(default="", description="Search query used")
    videos: List[YouTubeVideoResult] = Field(default_factory=list, description="Top 3 videos with transcripts")
    shorts: List[YouTubeShortResult] = Field(default_factory=list, description="Top 5 shorts with transcripts")


class ProcessedSearchResults(BaseModel):
    """Complete processed search results across all categories"""
    product_insights: Optional[CategoryInsights] = Field(default=None)
    competitor_insights: Optional[CategoryInsights] = Field(default=None)
    audience_insights: Optional[CategoryInsights] = Field(default=None)
    campaign_insights: Optional[CategoryInsights] = Field(default=None)
    platform_insights: Optional[CategoryInsights] = Field(default=None)
    youtube_insights: Optional[YouTubeInsights] = Field(default=None, description="YouTube videos and shorts with transcripts")
    
    # Metadata
    total_sources: int = Field(default=0, description="Total unique sources across all categories")
    processing_summary: Dict[str, Any] = Field(default_factory=dict, description="Processing metadata")

    def get_all_insights(self) -> List[CategoryInsights]:
        """Get all non-null category insights as a list"""
        insights = []
        if self.product_insights:
            insights.append(self.product_insights)
        if self.competitor_insights:
            insights.append(self.competitor_insights)
        if self.audience_insights:
            insights.append(self.audience_insights)
        if self.campaign_insights:
            insights.append(self.campaign_insights)
        if self.platform_insights:
            insights.append(self.platform_insights)
        return insights

    def get_all_sources(self) -> List[str]:
        """Get all unique sources across all categories"""
        all_sources = set()
        for insight in self.get_all_insights():
            all_sources.update(insight.sources)
        return list(all_sources)
