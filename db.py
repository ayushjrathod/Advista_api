import os
from dotenv import load_dotenv
from astrapy.client import DataAPIClient
from sentence_transformers import SentenceTransformer
import torch
from typing import List, Dict, Iterable, Optional
import logging
from datetime import datetime
import numpy as np
import asyncio
from reddit_insights_server import (
    fetch_search_results,
    fetch_reddit_comments,
    is_valid_body,
    process_reddit_data  # Update import
)

# Fix logger initialization
logger = logging.getLogger(__name__)

# Configure torch to suppress dynamo errors
torch._dynamo.config.suppress_errors = True

class AstraDB:
    def __init__(self):
        load_dotenv()
        
        self.token = os.getenv('ASTRA_DB_TOKEN')
        self.api_endpoint = os.getenv('ASTRA_DB_ENDPOINT')

        if not self.token or not self.api_endpoint:
            raise ValueError("ASTRA_DB_TOKEN and ASTRA_DB_ENDPOINT must be set in .env file")

        try:
            # Initialize the client using DataAPIClient
            self.client = DataAPIClient()
            
            # Get database instance
            self.db = self.client.get_database(
                self.api_endpoint,
                token=self.token
            )
            
            # Initialize collections with new names
            self.searches = self.db.get_collection("searches")
            self.youtube_insights = self.db.get_collection("youtube_insights")
            self.reddit_insights = self.db.get_collection("reddit_insights")
            self.reddit_comments = self.db.get_collection("reddit_comments")
            
            # Configure model with device and compute settings
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            self.model = SentenceTransformer(
                "jxm/cde-small-v2",
                trust_remote_code=True,
                device=device
            )
            # Ensure model is in eval mode
            self.model.eval()
            
            self.vector_limit = 1000
            logger.info(f"Model loaded successfully on {device}")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {str(e)}")
            raise

    def _chunk_vector(self, vector: List[float], chunk_size: int = 1000) -> List[List[float]]:
        """Split vector into chunks that fit within Astra DB limits"""
        return [vector[i:i + chunk_size] for i in range(0, len(vector), chunk_size)]

    async def calculate_similarity(self, embeddings1: List[float], embeddings2: List[float]) -> float:
        """Calculate similarity between two embeddings"""
        try:
            with torch.no_grad():
                similarity = self.model.similarity(
                    [embeddings1],
                    [embeddings2]
                )
            return float(similarity[0][0])
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0

    async def save_session(self, session_id: str, query: str, youtube_results: List[Dict]):
        try:
            with torch.no_grad():
                query_embedding = self.model.encode(query).tolist()
            
            if len(query_embedding) > self.vector_limit:
                logger.warning(f"Truncating embedding from {len(query_embedding)} to {self.vector_limit}")
                query_embedding = query_embedding[:self.vector_limit]

            # Get Reddit insight immediately
            reddit_groq_insight = process_reddit_data(query)

            search_doc = {
                "_id": session_id,
                "query": query,
                "query_embedding": query_embedding,
                "timestamp": datetime.now().isoformat(),
                "processed": False,
                "reddit_groq_insight": reddit_groq_insight  # Add Groq insight
            }

            # Save to searches collection
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, 
                lambda: self.searches.insert_one(search_doc)
            )
            
            # Insert YouTube insights in batches
            batch_size = 100
            for i in range(0, len(youtube_results), batch_size):
                batch = youtube_results[i:i + batch_size]
                insight_docs = [
                    {
                        "_id": f"{session_id}_{video['id']}",
                        "search_id": session_id,
                        "video_id": video['id'],
                        "title": video['title'],
                        "description": video['description'],
                        "link": video['link'],
                        "has_captions": video.get('has_captions', False),
                        "duration": video.get('duration', ''),
                        "processed": False,
                        "embedding": None,
                        "similarity_score": None
                    }
                    for video in batch
                ]
                
                await loop.run_in_executor(
                    None,
                    lambda x: self.youtube_insights.insert_many(x, ordered=False),
                    insight_docs
                )
            
        except Exception as e:
            logger.error(f"Error saving search: {str(e)}")
            raise

    async def update_youtube_insight(self, search_id: str, video_id: str, transcript: str, embedding: List[float] = None):
        """Update youtube insight with transcript and embedding"""
        try:
            doc_id = f"{search_id}_{video_id}"
            
            # Truncate transcript to fit within 8000 byte limit
            if len(transcript.encode('utf-8')) > 8000:
                logger.warning(f"Truncating transcript from {len(transcript.encode('utf-8'))} bytes to 8000 bytes")
                while len(transcript.encode('utf-8')) > 8000:
                    transcript = transcript[:-100]
            
            update_doc = {
                "transcript": transcript,
                "processed": True,
                "transcript_truncated": len(transcript.encode('utf-8')) > 8000
            }

            if embedding and len(embedding) > self.vector_limit:
                embedding = embedding[:self.vector_limit]
            
            if embedding:
                update_doc["embedding"] = embedding
                # Calculate similarity with search query
                search = await self.get_search(search_id)
                if search and search.get("query_embedding"):
                    similarity = await self.calculate_similarity(
                        embedding,
                        search["query_embedding"]
                    )
                    update_doc["similarity_score"] = similarity

            # Update in youtube_insights collection
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self.youtube_insights.find_one_and_update(
                    {"_id": doc_id},
                    {"$set": update_doc}
                )
            )
            return result
            
        except Exception as e:
            logger.error(f"Error updating youtube insight: {str(e)}")
            raise

    async def get_search(self, search_id: str) -> Dict:
        """Get search by ID (renamed from get_session)"""
        try:
            loop = asyncio.get_event_loop()
            
            # Get from searches collection instead of sessions
            search = await loop.run_in_executor(
                None,
                lambda: self.searches.find_one({"_id": search_id})
            )
            
            if not search:
                return None
            
            # Fix find() arguments for youtube_insights
            videos = await loop.run_in_executor(
                None,
                lambda: list(self.youtube_insights.find({"search_id": search_id}))
            )
            
            # Get reddit data with aggregation
            reddit_insights = await loop.run_in_executor(
                None,
                lambda: list(self.reddit_insights.find({"search_id": search_id}))
            )
            
            reddit_comments = await loop.run_in_executor(
                None,
                lambda: list(self.reddit_comments.find({"search_id": search_id}))
            )
            
            return {
                "search_id": search["_id"],
                "query": search["query"],
                "query_embedding": search.get("query_embedding"),
                "youtube_results": videos,
                "reddit_insights": reddit_insights,
                "reddit_comments": reddit_comments,
                "reddit_groq_insight": search.get("reddit_groq_insight"),  # Changed field name
                "timestamp": search["timestamp"],
                "processed": search.get("processed", False),
                "reddit_processed": search.get("reddit_processed", False)  # Add this field
            }
            
        except Exception as e:
            logger.error(f"Error getting search: {str(e)}")
            raise

    async def find_similar_search(self, query: str, similarity_threshold: float = 0.85) -> Optional[Dict]:
        """Find similar processed search by query"""
        try:
            # Generate query embedding
            with torch.no_grad():
                query_embedding = self.model.encode(query).tolist()

            # Get all processed searches
            loop = asyncio.get_event_loop()
            searches = await loop.run_in_executor(
                None,
                lambda: list(self.searches.find({"processed": True}))
            )

            max_similarity = 0
            most_similar_search = None

            # Compare with each search
            for search in searches:
                if search.get("query_embedding"):
                    similarity = await self.calculate_similarity(
                        query_embedding,
                        search["query_embedding"]
                    )
                    if similarity > max_similarity and similarity >= similarity_threshold:
                        max_similarity = similarity
                        most_similar_search = search

            if most_similar_search:
                # Get complete search data
                return await self.get_search(most_similar_search["_id"])
            
            return None

        except Exception as e:
            logger.error(f"Error finding similar search: {str(e)}")
            return None

    async def save_reddit_data(self, search_id: str, product_query: str):
        """Save Reddit insights and comments with unique IDs"""
        try:
            # Get Reddit insights directly
            groq_analysis = process_reddit_data(product_query)
            if not groq_analysis:
                return
            
            loop = asyncio.get_event_loop()
            
            # Update searches collection with Reddit insights using search_id
            await loop.run_in_executor(
                None,
                lambda: self.searches.find_one_and_update(
                    {"_id": search_id},  # Use _id for finding the document
                    {"$set": {
                        "reddit_groq_insight": groq_analysis,
                        "reddit_processed": True
                    }}
                )
            )
            
            # Log the analysis using search_id instead of session_id
            logger.info(f"Reddit Groq Analysis for {search_id}: {groq_analysis}")
            
            return groq_analysis
            
        except Exception as e:
            logger.error(f"Error saving Reddit data: {str(e)}")
            raise

    async def get_reddit_analysis_stream(self, query: str) -> str:
        """Get Reddit analysis in real-time"""
        try:
            # Get Reddit insights directly without saving
            analysis = process_reddit_data(query)
            if analysis:
                # Log the analysis
                logger.info(f"Streaming Reddit Analysis: {analysis}")
                return analysis
            return None
        except Exception as e:
            logger.error(f"Error getting Reddit analysis stream: {e}")
            return None

    def __del__(self):
        # No need to explicitly close with Document API
        pass

