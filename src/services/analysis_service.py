import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.models.research_insights import (
    AIOverview,
    CategoryInsights,
    OrganicResult,
    ProcessedSearchResults,
    RelatedQuestion,
    YouTubeInsights,
    YouTubeShortResult,
    YouTubeVideoResult,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service to process and analyze raw SerpAPI search results"""

    def __init__(self, max_organic_results: int = 10, max_related_questions: int = 5):
        self.max_organic_results = max_organic_results
        self.max_related_questions = max_related_questions

    def process_search_results(self, raw_results: Dict[str, Any]) -> ProcessedSearchResults:
        """
        Process raw SerpAPI results from all categories into structured insights.
        
        Args:
            raw_results: Dict with keys like 'product', 'competitor', etc.
                        Each containing 'query' and 'results' from SerpAPI
        
        Returns:
            ProcessedSearchResults with insights for each category
        """
        processed = ProcessedSearchResults()
        all_sources = set()
        categories_processed = 0

        # Map category names to ProcessedSearchResults attributes
        category_mapping = {
            "product": "product_insights",
            "competitor": "competitor_insights",
            "audience": "audience_insights",
            "campaign": "campaign_insights",
            "platform": "platform_insights",
        }

        for category_key, attr_name in category_mapping.items():
            if category_key in raw_results:
                try:
                    category_data = raw_results[category_key]
                    insights = self._process_category(category_key, category_data)
                    setattr(processed, attr_name, insights)
                    all_sources.update(insights.sources)
                    categories_processed += 1
                    logger.info(f"Processed {category_key}: {len(insights.top_results)} results, {len(insights.related_questions)} questions")
                    # TODO: remove after debugging (audience/competitor use google_forums/Reddit)
                    if category_key in ("audience", "competitor"):
                        sources_preview = list(insights.sources)[:5]
                        logger.info(f"[REDDIT/FORUMS] Processed category={category_key} | top_results={len(insights.top_results)} | sources_sample={sources_preview}")
                except Exception as e:
                    logger.error(f"Error processing category {category_key}: {e}")

        # Process YouTube results if present
        if "youtube" in raw_results:
            try:
                youtube_data = raw_results["youtube"]
                # TODO: remove after debugging
                logger.info(f"[YT] Processing youtube_insights | videos={len(youtube_data.get('videos', []))} | shorts={len(youtube_data.get('shorts', []))}")
                processed.youtube_insights = self._process_youtube(youtube_data)
                for v in youtube_data.get("videos") or []:
                    all_sources.add(v.get("channel") or "YouTube")
                if youtube_data.get("shorts"):
                    all_sources.add("YouTube Shorts")
                categories_processed += 1
                logger.info(
                    f"Processed youtube: {len(processed.youtube_insights.videos)} videos, "
                    f"{len(processed.youtube_insights.shorts)} shorts"
                )
                # TODO: remove after debugging
                transcript_chars = sum(len(v.transcript) for v in processed.youtube_insights.videos) + sum(len(s.transcript) for s in processed.youtube_insights.shorts)
                logger.info(f"[YT] youtube_insights ready | total_transcript_chars={transcript_chars}")
            except Exception as e:
                logger.error(f"Error processing YouTube data: {e}")

        processed.total_sources = len(all_sources)
        processed.processing_summary = {
            "categories_processed": categories_processed,
            "total_unique_sources": len(all_sources),
            "categories_available": list(raw_results.keys()),
        }

        return processed

    def _process_youtube(self, youtube_data: Dict[str, Any]) -> YouTubeInsights:
        """Convert raw YouTube research data to YouTubeInsights."""
        videos = [
            YouTubeVideoResult(
                title=v.get("title", ""),
                link=v.get("link", ""),
                channel=v.get("channel", ""),
                published_date=v.get("published_date", ""),
                views=v.get("views"),
                length=v.get("length", ""),
                description=v.get("description", ""),
                video_id=v.get("video_id", ""),
                transcript=v.get("transcript", ""),
            )
            for v in youtube_data.get("videos", [])
        ]
        shorts = [
            YouTubeShortResult(
                title=s.get("title", ""),
                link=s.get("link", ""),
                views=s.get("views"),
                views_original=s.get("views_original", ""),
                video_id=s.get("video_id", ""),
                transcript=s.get("transcript", ""),
            )
            for s in youtube_data.get("shorts", [])
        ]
        return YouTubeInsights(
            query=youtube_data.get("query", ""),
            videos=videos,
            shorts=shorts,
        )

    def _process_category(self, category: str, category_data: Dict[str, Any]) -> CategoryInsights:
        """Process a single category's search results"""
        query = category_data.get("query", "")
        results = category_data.get("results", {})

        insights = CategoryInsights(
            category=category,
            query=query,
        )

        # Extract search information
        search_info = results.get("search_information", {})
        insights.total_results = search_info.get("total_results", 0)

        # Process organic results
        insights.top_results = self._extract_organic_results(results)

        # Process related questions (People Also Ask)
        insights.related_questions = self._extract_related_questions(results)

        # Process AI overview if available
        insights.ai_overview = self._extract_ai_overview(results)

        # Extract key snippets from top results
        insights.key_snippets = self._extract_key_snippets(insights)

        # Extract unique sources
        insights.sources = self._extract_unique_sources(insights.top_results)

        return insights

    def _extract_organic_results(self, results: Dict[str, Any]) -> List[OrganicResult]:
        """Extract and clean organic search results"""
        organic_results = []
        raw_organic = results.get("organic_results", [])

        for item in raw_organic[:self.max_organic_results]:
            try:
                # Google Forums uses displayed_meta (e.g. "40+ comments · 14 years ago") instead of date
                date = item.get("date") or item.get("displayed_meta")
                result = OrganicResult(
                    position=item.get("position", 0),
                    title=item.get("title", ""),
                    link=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source=item.get("source", ""),
                    date=date,
                )
                if result.title and result.link:  # Only add if has essential fields
                    organic_results.append(result)
            except Exception as e:
                logger.warning(f"Error parsing organic result: {e}")

        return organic_results

    def _extract_related_questions(self, results: Dict[str, Any]) -> List[RelatedQuestion]:
        """Extract 'People Also Ask' questions and answers"""
        related_questions = []
        raw_questions = results.get("related_questions", [])

        for item in raw_questions[:self.max_related_questions]:
            try:
                # Extract answer from various possible locations
                answer = self._extract_answer_from_question(item)
                
                question = RelatedQuestion(
                    question=item.get("question", ""),
                    answer=answer,
                    source_title=item.get("title"),
                    source_link=item.get("link"),
                )
                if question.question:  # Only add if has a question
                    related_questions.append(question)
            except Exception as e:
                logger.warning(f"Error parsing related question: {e}")

        return related_questions

    def _extract_answer_from_question(self, item: Dict[str, Any]) -> str:
        """Extract the answer text from a related question item"""
        # Check for direct snippet
        if "snippet" in item and item["snippet"]:
            return item["snippet"]

        # Check for text_blocks (AI overview style answers)
        text_blocks = item.get("text_blocks", [])
        answer_parts = []
        
        for block in text_blocks:
            block_type = block.get("type", "")
            
            if block_type == "paragraph":
                snippet = block.get("snippet", "")
                if snippet:
                    answer_parts.append(snippet)
            
            elif block_type == "list":
                list_items = block.get("list", [])
                for list_item in list_items:
                    if isinstance(list_item, dict):
                        snippet = list_item.get("snippet", "")
                        if snippet:
                            answer_parts.append(f"• {snippet}")
                    elif isinstance(list_item, str):
                        answer_parts.append(f"• {list_item}")

        return " ".join(answer_parts) if answer_parts else ""

    def _extract_ai_overview(self, results: Dict[str, Any]) -> AIOverview:
        """Extract Google's AI overview if available"""
        ai_overview = AIOverview()
        raw_ai = results.get("ai_overview", {})

        if not raw_ai:
            return ai_overview

        # AI overview is usually just a token/link in SerpAPI
        # The actual content comes from related_questions with type "ai_overview"
        related_questions = results.get("related_questions", [])
        
        for item in related_questions:
            if item.get("type") == "ai_overview":
                text_blocks = item.get("text_blocks", [])
                
                for block in text_blocks:
                    block_type = block.get("type", "")
                    
                    if block_type == "paragraph":
                        snippet = block.get("snippet", "")
                        if snippet:
                            ai_overview.snippets.append(snippet)
                    
                    elif block_type == "list":
                        list_items = block.get("list", [])
                        for list_item in list_items:
                            if isinstance(list_item, dict):
                                snippet = list_item.get("snippet", "")
                                if snippet:
                                    ai_overview.key_points.append(snippet)
                            elif isinstance(list_item, str):
                                ai_overview.key_points.append(list_item)

        return ai_overview

    def _extract_key_snippets(self, insights: CategoryInsights) -> List[str]:
        """Extract the most relevant text snippets from all sources"""
        snippets = []

        # Add AI overview snippets (highest quality)
        snippets.extend(insights.ai_overview.snippets)
        snippets.extend(insights.ai_overview.key_points)

        # Add related question answers
        for q in insights.related_questions:
            if q.answer:
                # Truncate very long answers
                answer = q.answer[:500] if len(q.answer) > 500 else q.answer
                snippets.append(answer)

        # Add top organic result snippets
        for result in insights.top_results[:5]:
            if result.snippet:
                snippets.append(result.snippet)

        # Deduplicate while preserving order
        seen = set()
        unique_snippets = []
        for snippet in snippets:
            snippet_lower = snippet.lower().strip()
            if snippet_lower not in seen and len(snippet) > 20:  # Skip very short snippets
                seen.add(snippet_lower)
                unique_snippets.append(snippet)

        return unique_snippets[:15]  # Limit to top 15 snippets

    def _extract_unique_sources(self, results: List[OrganicResult]) -> List[str]:
        """Extract unique source domains from results"""
        sources = set()
        
        for result in results:
            if result.source:
                sources.add(result.source)
            elif result.link:
                try:
                    parsed = urlparse(result.link)
                    domain = parsed.netloc.replace("www.", "")
                    if domain:
                        sources.add(domain)
                except Exception:
                    pass

        return list(sources)

    def get_youtube_context(self, processed: ProcessedSearchResults) -> str:
        """Generate YouTube transcript context for synthesis."""
        if not processed.youtube_insights:
            return ""
        parts = [f"\n## YOUTUBE RESEARCH\nQuery: {processed.youtube_insights.query}\n"]
        for v in processed.youtube_insights.videos:
            parts.append(f"\n### Video: {v.title} ({v.channel})")
            if v.transcript:
                parts.append(f"Transcript: {v.transcript[:2000]}{'...' if len(v.transcript) > 2000 else ''}")
        for s in processed.youtube_insights.shorts:
            parts.append(f"\n### Short: {s.title}")
            if s.transcript:
                parts.append(f"Transcript: {s.transcript[:1500]}{'...' if len(s.transcript) > 1500 else ''}")
        return "\n".join(parts)

    def get_combined_context(self, processed: ProcessedSearchResults) -> str:
        """
        Generate a combined text context from all processed results.
        Useful for feeding into an LLM for synthesis.
        """
        context_parts = []

        for insights in processed.get_all_insights():
            section = f"\n## {insights.category.upper()} RESEARCH\n"
            section += f"Query: {insights.query}\n"
            section += f"Total Results: {insights.total_results}\n\n"

            # Add AI overview if available
            if insights.ai_overview.snippets or insights.ai_overview.key_points:
                section += "### AI Overview:\n"
                for snippet in insights.ai_overview.snippets:
                    section += f"{snippet}\n"
                if insights.ai_overview.key_points:
                    section += "\nKey Points:\n"
                    for point in insights.ai_overview.key_points:
                        section += f"• {point}\n"
                section += "\n"

            # Add related questions
            if insights.related_questions:
                section += "### Related Questions & Answers:\n"
                for q in insights.related_questions:
                    section += f"Q: {q.question}\n"
                    section += f"A: {q.answer}\n\n"

            # Add top results
            if insights.top_results:
                section += "### Top Search Results:\n"
                for result in insights.top_results[:5]:
                    section += f"- {result.title}\n"
                    section += f"  {result.snippet}\n"
                    section += f"  Source: {result.source} | {result.link}\n\n"

            context_parts.append(section)

        youtube_ctx = self.get_youtube_context(processed)
        if youtube_ctx:
            context_parts.append(youtube_ctx)

        return "\n".join(context_parts)

    def get_category_summary(self, insights: CategoryInsights) -> Dict[str, Any]:
        """Generate a summary dict for a single category"""
        return {
            "category": insights.category,
            "query": insights.query,
            "total_results": insights.total_results,
            "num_organic_results": len(insights.top_results),
            "num_related_questions": len(insights.related_questions),
            "has_ai_overview": bool(insights.ai_overview.snippets or insights.ai_overview.key_points),
            "num_key_snippets": len(insights.key_snippets),
            "sources": insights.sources,
        }


# Singleton instance
analysis_service = AnalysisService()
