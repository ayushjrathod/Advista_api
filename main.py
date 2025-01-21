from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import asyncio
from datetime import datetime
import json
import logging
from groq import Groq,AsyncGroq
import os
from scripts import search_youtube_videos,refine_ad_requirements,get_chat_response
from video_processor import VideoProcessor
import aiofiles
from db import AstraDB
from fastapi.responses import StreamingResponse

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    message: str
    is_complete: bool
    session_id: str
    youtube_results: Optional[List[dict]] = None
    processed: bool = False
    similar_search: Optional[Dict] = None  # Add this field

# Store active conversations
active_conversations = {}

# Add logger
logger = logging.getLogger(__name__)

# Initialize database with error handling
try:
    db = AstraDB()
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise

@app.post("/chat/start")
async def start_chat():
    """Initialize a new chat session"""
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    active_conversations[session_id] = {
        "conversation": [
            {
                "role": "system",
                "content": """You are an AI advertising assistant helping to gather detailed information about ad requirements. 
                Ask focused questions one at a time to understand the client's needs. After each user response, evaluate if you have 
                enough information to generate a 4-5 word YouTube search query. If you do, indicate with '[SUFFICIENT]' at the start 
                of your response and provide the suggested search query. Otherwise, ask another relevant question."""
            }
        ]
    }
    
    # Send initial greeting
    return {
        "message": "Hello! I'm here to help you create an effective advertisement. What would you like to create an ad for?",
        "session_id": session_id,
        "is_complete": False
    }

@app.post("/chat/message", response_model=ChatResponse)
async def chat_message(chat_input: ChatInput):
    """Handle chat messages and continue the conversation"""
    if not chat_input.session_id or chat_input.session_id not in active_conversations:
        raise HTTPException(status_code=400, detail="Invalid or missing session ID")
    
    try:
        conversation = active_conversations[chat_input.session_id]["conversation"]
        conversation.append({"role": "user", "content": chat_input.message})
        
        client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
        response = await get_chat_response(client, conversation)
        
        is_complete = '[SUFFICIENT]' in response
        
        youtube_results = []
        if is_complete:
            search_query = response.split('[SUFFICIENT]')[1].strip()
            youtube_results = search_youtube_videos(query=search_query)
            if not youtube_results:  # Added validation
                logger.warning("No YouTube results found for query.")
                return {
                    "message": response + "\nNo related YouTube videos found.",
                    "is_complete": True,
                    "session_id": chat_input.session_id,
                    "youtube_results": [],
                    "processed": False,
                    "similar_search": None
                }
            
            # Check for similar existing searches
            similar_search = await db.find_similar_search(search_query)
            if (similar_search and similar_search.get("processed")):
                return {
                    "message": f"{response}\n\nI found similar existing results that might be helpful!",
                    "is_complete": True,
                    "session_id": chat_input.session_id,
                    "youtube_results": similar_search.get("youtube_results", []),
                    "processed": True,
                    "similar_search": similar_search
                }
            
            # If no similar search found, continue with new search
            youtube_results = search_youtube_videos(query=search_query)
            await db.save_session(chat_input.session_id, search_query, youtube_results)
            
            # Start video and Reddit data processing in background
            asyncio.create_task(process_videos_background(
                chat_input.session_id, 
                search_query, 
                youtube_results, 
                conversation
            ))
            
            # Also save Reddit data for the search query
            asyncio.create_task(db.save_reddit_data(
                chat_input.session_id,
                search_query
            ))
            
            return {
                "message": response,
                "is_complete": is_complete,
                "session_id": chat_input.session_id,
                "youtube_results": youtube_results,
                "processed": False,
                "similar_search": None
            }
        else:
            conversation.append({"role": "assistant", "content": response})
            return {
                "message": response,
                "is_complete": is_complete,
                "session_id": chat_input.session_id,
                "youtube_results": None,
                "processed": False,
                "similar_search": None
            }
    except Exception as e:
        logger.error(f"Error in chat_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_videos_background(session_id: str, search_query: str, youtube_results: List[dict], conversation: List[dict]):
    """Process videos in background and save results"""
    try:
        processor = VideoProcessor(db)
        
        # Provide additional logging if no videos are processed
        if not youtube_results:
            logger.warning(f"No videos to process for session {session_id}.")
            return
        
        processed_results = await asyncio.gather(*[
            processor.process_single_video(video, session_id) 
            for video in youtube_results
        ])
        
        processed_results = [r for r in processed_results if r is not None]
        
        # Update session as processed using searches collection
        if processed_results:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: db.searches.find_one_and_update(
                    {"_id": session_id},
                    {"$set": {"processed": True}}
                )
            )
        
        # Clean up active conversation
        if session_id in active_conversations:
            del active_conversations[session_id]
            
    except Exception as e:
        logger.error(f"Error processing videos: {str(e)}")

@app.get("/results/{session_id}")
async def get_results(session_id: str):
    try:
        result = await db.get_search(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="Search not found")
        
        # Return analyses directly from the search document
        response = {
            **result,
            "analyses": result.get("analyses", {
                "youtube": result.get("youtube_groq_analysis"),
                "reddit": result.get("reddit_groq_insight")
            })
        }
        return response
    except Exception as e:
        logger.error(f"Error getting results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analyses/{session_id}")
async def get_analyses(session_id: str):
    try:
        result = await db.get_search(session_id)
        if not result:
            raise HTTPException(status_code=404, detail="Search not found")
        
        return {
            "youtube_groq_analysis": result.get("youtube_groq_analysis"),
            "reddit_groq_insight": result.get("reddit_groq_insight"),
            "processed": result.get("processed", False)
        }
    except Exception as e:
        logger.error(f"Error getting analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add new streaming endpoint
@app.get("/reddit-analysis-stream/{session_id}")
async def stream_reddit_analysis(session_id: str):
    """Stream Reddit analysis as it's being generated"""
    try:
        search = await db.get_search(session_id)
        if not search:
            raise HTTPException(status_code=404, detail="Search not found")

        # If we already have the analysis, return it immediately
        if search.get("reddit_groq_insight"):
            return StreamingResponse(
                iter([f"data: {json.dumps({'analysis': search['reddit_groq_insight']})}\n\n"]),
                media_type="text/event-stream"
            )

        # Otherwise get fresh analysis
        async def generate():
            analysis = await db.get_reddit_analysis_stream(search["query"])
            if analysis:
                yield f"data: {json.dumps({'analysis': analysis})}\n\n"
                # Save the analysis for future use
                await db.save_reddit_data(session_id, search["query"])

        return StreamingResponse(
            generate(),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"Error streaming Reddit analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
