import logging
from datetime import datetime

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from prisma import Json

from src.models.research_brief import ResearchBrief
from src.models.search_params import SearchParams
from src.utils.config import settings
from src.services.database_service import db

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

    async def create_research_query(self, research_brief: ResearchBrief, threadId: str) -> SearchParams:

        # Create prompt for extracting search queries
        brief_summary = f"""
        Company: {research_brief.company_name}
        Product/Service: {research_brief.product_description}
        Target Customers: {research_brief.target_customers}
        Competitors: {', '.join(research_brief.competitor_names) if research_brief.competitor_names else 'None specified'}
        Strategic Goals: {research_brief.strategic_goals}
        Primary Channels: {', '.join(research_brief.primary_channels) if research_brief.primary_channels else 'None specified'}
        Positioning: {research_brief.positioning_hypothesis}
        Additional Context: {research_brief.additional_context}
        """
        
        extraction_prompt = f"""
        Based on the following competitive intelligence brief, generate comprehensive search queries for google search
        that will help gather competitive intelligence. Create a single query for each category.
        
        Guidelines:
        1. Company Product Query: Generate a single query to research what {research_brief.company_name}'s product does 
           and how it's positioned in the market. Focus on features, capabilities, and market positioning.
        2. Competitor Landscape Query: Generate a single query to research competitor strengths, weaknesses, and recent moves.
           Include queries about "{', '.join(research_brief.competitor_names) if research_brief.competitor_names else 'key competitors in the market'}"
        3. Customer Sentiment Query: Generate a single query to research what customers say about this space — 
           forums, Reddit, reviews, complaints. Focus on: {research_brief.target_customers}
        4. Strategic Gap Query: Generate a single query to research market gaps, unmet needs, and whitespace 
           in the competitive landscape for: {research_brief.strategic_goals}
        5. Battlecard Query: Generate a single query to research how competitors position against each other 
           on primary channels. Channels: {', '.join(research_brief.primary_channels) if research_brief.primary_channels else 'general market channels'}
        
        Make sure queries are specific, actionable, and will yield useful competitive intelligence results. Each query should be 
        distinct and cover different angles of the competitive landscape.
        
        CI Brief:
        {brief_summary}
        """
        
        try:
            search_params_results = await self.params_extractor_llm.ainvoke([
                HumanMessage(content=extraction_prompt)
            ])

            active_session = await db.prisma.researchsession.find_first(
                where={'threadId': threadId},
                order={'createdAt': 'desc'}
            )
            if active_session:
                await db.prisma.researchsession.update(
                    where={'id': active_session.id},
                    data={
                        'searchParams': Json(search_params_results.model_dump() if search_params_results else {}),
                        'updatedAt': datetime.utcnow(),
                    }
                )

            return search_params_results
        except Exception as e:
            logger.error(f"Error generating search params: {e}")
            return SearchParams()


research_service = ResearchService()
