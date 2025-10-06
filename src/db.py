import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import requests
from astrapy.client import DataAPIClient
from dotenv import load_dotenv

from reddit_insights_server import process_reddit_data

# Fix logger initialization
logger = logging.getLogger(__name__)



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
            
            # Configure Hugging Face API
            self.hf_token = os.getenv('HF_TOKEN')
            if not self.hf_token:
                raise ValueError("HF_TOKEN must be set in .env file")
            
            self.embedding_api_url = "https://api-inference.huggingface.co/models/sentence-transformers/all-MiniLM-L6-v2"
            self.similarity_api_url = "https://router.huggingface.co/hf-inference/models/sentence-transformers/all-MiniLM-L6-v2/pipeline/sentence-similarity"
            self.headers = {
                "Authorization": f"Bearer {self.hf_token}",            }
            
            self.vector_limit = 1000
            logger.info("Hugging Face API configured successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize: {str(e)}")
            raise

    def _chunk_vector(self, vector: List[float], chunk_size: int = 1000) -> List[List[float]]:
        """Split vector into chunks that fit within Astra DB limits"""
        return [vector[i:i + chunk_size] for i in range(0, len(vector), chunk_size)]

    async def _get_embedding(self, text: str) -> List[float]:
        """Get embedding from Hugging Face API"""
        try:
            response = requests.post(
                self.embedding_api_url,
                headers=self.headers,
                json={"inputs": text}
            )
            response.raise_for_status()
            embedding = response.json()
            
            # Handle different response formats
            if isinstance(embedding, list) and len(embedding) > 0:
                if isinstance(embedding[0], list):
                    return embedding[0]  # First embedding if batch
                return embedding
            return []
        except Exception as e:
            logger.error(f"Error getting embedding: {str(e)}")
            return []

    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using Hugging Face API"""
        try:
            payload = {
                "inputs": {
                    "source_sentence": text1,
                    "sentences": [text2]
                }
            }
            
            response = requests.post(
                self.similarity_api_url,
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
              # Extract similarity score
            if isinstance(result, list) and len(result) > 0:
                return float(result[0])
            return 0.0
        except Exception as e:
            logger.error(f"Error calculating similarity: {str(e)}")
            return 0.0

    async def save_session(self, session_id: str, query: str, youtube_results: List[Dict]):
        try:
            # Get embedding using Hugging Face API
            query_embedding = await self._get_embedding(query)
            
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
                "reddit_groq_insight": reddit_groq_insight,  # Add Groq insight
                "youtube_groq_analysis": None,  # Add field for YouTube analysis
                "analyses": {              # Combined analyses object
                    "youtube": None,
                    "reddit": reddit_groq_insight  # Already stored in same object
                }
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

            # Generate embedding if not provided
            if not embedding and transcript:
                embedding = await self._get_embedding(transcript)

            if embedding and len(embedding) > self.vector_limit:
                embedding = embedding[:self.vector_limit]
            
            if embedding:
                update_doc["embedding"] = embedding
                # Calculate similarity with search query using text similarity
                search = await self.get_search(search_id)
                if search and search.get("query"):
                    similarity = await self.calculate_similarity(
                        search["query"],
                        transcript
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

            if transcript:
                # Get analysis immediately
                analysis = await self.analyze_transcript(search_id, transcript)
                if analysis:
                    # Update analyses directly in searches collection
                    await self.update_search_analyses(search_id, youtube_analysis=analysis)
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
                "reddit_comments": reddit_comments,                "reddit_groq_insight": search.get("reddit_groq_insight"),  # Changed field name
                "youtube_transcript_analysis": search.get("youtube_transcript_analysis"),
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
            # Get all processed searches
            loop = asyncio.get_event_loop()
            searches = await loop.run_in_executor(
                None,
                lambda: list(self.searches.find({"processed": True}))
            )

            max_similarity = 0
            most_similar_search = None

            # Compare with each search using text similarity
            for search in searches:
                if search.get("query"):
                    similarity = await self.calculate_similarity(
                        query,
                        search["query"]
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
        """Save Reddit groq insight"""
        try:
            groq_analysis = process_reddit_data(product_query)
            if groq_analysis:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.searches.find_one_and_update(
                        {"_id": search_id},
                        {"$set": {"reddit_groq_insight": groq_analysis}}
                    )
                )
            return groq_analysis
        except Exception as e:
            logger.error(f"Error saving Reddit data: {e}")
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

    async def update_youtube_analysis(self, search_id: str, analysis: str):
        """Update YouTube analysis in searches collection"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.searches.find_one_and_update(
                    {"_id": search_id},
                    {"$set": {
                        "youtube_transcript_analysis": analysis,
                    }}
                )
            )
        except Exception as e:
            logger.error(f"Error updating YouTube analysis: {e}")
            raise

    async def analyze_transcript(self, search_id: str, transcript: str) -> str:
        """Simplified analysis for YouTube transcript using Groq."""
        try:
            from groq import Groq
            client = Groq(api_key=os.getenv('GROQ_API_KEY'))

            prompt = (
                f"Give me a concise summary and analysis for this ad setup.\n"
                f"Session ID: {search_id}\n"
                f"Transcript:\n{transcript}\n"
                "I want to run an ad."
            )

            # Create a non-streaming completion for simplicity
            response = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                model="llama-3.1-8b-instant",
                temperature=0.5,
                max_completion_tokens=512
            )

            analysis = response.choices[0].message.content
            logger.info(f"Groq analysis for {search_id}: {analysis}")
            return analysis
        except Exception as e:
            logger.error(f"Error analyzing transcript: {e}")
            return None

    async def update_search_analyses(self, search_id: str, youtube_analysis: Optional[str] = None):
        """Update analyses in the searches collection."""
        try:
            update_fields = {}
            if youtube_analysis:
                update_fields["youtube_groq_analysis"] = youtube_analysis

            if update_fields:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    lambda: self.searches.find_one_and_update(
                        {"_id": search_id},
                        {"$set": update_fields}
                    )
                )
                logger.info(f"Updated analyses for search {search_id}")
        except Exception as e:
            logger.error(f"Error updating search analyses: {e}")
            raise

    def __del__(self):
        # No need to explicitly close with Document API
        pass

