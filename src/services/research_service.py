import asyncio
import logging
from typing import Any, Dict, List

from serpapi import GoogleSearch

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

from src.models.research_brief import ResearchBrief
from src.models.search_params import SearchParams
from src.models.search_results import (
    ResearchExecutionResult,
    SearchQueryResult,
    SearchResultsCollection,
)
from src.utils.config import settings
logger = logging.getLogger(__name__)


class ResearchService:
    def __init__(self):
        # Initialize chat model for structured output
        self.llm = init_chat_model(
            model_provider="groq",
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY2
        )
        
        # Initialize structured output LLM for search params extraction
        self.params_extractor_llm = self.llm.with_structured_output(SearchParams)

    async def create_research_query(self, research_brief: ResearchBrief) -> SearchParams:

        # Create prompt for extracting search queries
        brief_summary = f"""
        Product/Service: {research_brief.product_name}
        Description: {research_brief.product_description}
        Target Audience: {research_brief.target_audience}
        Competitors: {', '.join(research_brief.competitor_names) if research_brief.competitor_names else 'None specified'}
        Campaign Goals: {research_brief.campaign_goals}
        Preferred Platforms: {', '.join(research_brief.preferred_platforms) if research_brief.preferred_platforms else 'None specified'}
        Tone and Style: {research_brief.tone_and_style}
        Additional Notes: {research_brief.additional_notes}
        """
        
        extraction_prompt = f"""
        Based on the following research brief for an advertising campaign, generate comprehensive search query for google search
        that will help gather information for research. Create a single query for each category.
        
        Guidelines:
        1. Product Search Query: Generate a single query about the product/service, its features, market positioning, 
           industry trends, and similar products. Focus on: {research_brief.product_name}
        2. Competitor Search Query: Generate a single query about competitors, their marketing strategies, pricing, 
           customer reviews, and market share. Include queries about "{', '.join(research_brief.competitor_names) if research_brief.competitor_names else 'similar products in the market'}"
        3. Audience Insight Query: Generate a single query about the target audience demographics, interests, 
           behavior patterns, online presence, and purchasing habits. Focus on: {research_brief.target_audience}
        4. Campaign Strategy Query: Generate a single query about successful advertising campaigns, best practices, 
           case studies, and strategies for achieving: {research_brief.campaign_goals}
        5. Platform-Specific Query: Generate a single query for each preferred platform about best practices, 
           targeting options, ad formats, and success stories. Platforms: {', '.join(research_brief.preferred_platforms) if research_brief.preferred_platforms else 'general advertising platforms'}
        
        Make sure queries are specific, actionable, and will yield useful research results. Each query should be 
        distinct and cover different angles of the research topic.
        
        Research Brief:
        {brief_summary}
        """
        
        try:
            return await self.params_extractor_llm.ainvoke([
                HumanMessage(content=extraction_prompt)
            ])
        except Exception as e:
            logger.error(f"Error generating search params: {e}")
            return SearchParams()


research_service = ResearchService()
