import asyncio
import json
import os
from typing import Dict, List

from dotenv import load_dotenv
from googleapiclient.discovery import build
from groq import AsyncGroq, Groq

from utils.config import Config
config = Config()

def search_youtube_videos(query, location=None, api_key=config.YOUTUBE_API_KEY):
    """
    Search YouTube videos with specific parameters
    Args:
        query (str): Search query
        location (tuple, optional): Tuple of (latitude, longitude)
        api_key (str, optional): YouTube API key
    Returns:
        list: List of video details
    """
    youtube = build('youtube', 'v3', developerKey=api_key)
    
    # Base search parameters
    search_params = {
        'part': 'id,snippet',
        'q': query,
        'maxResults': 4,
        'order': 'viewCount',
        'type': 'video',
        'videoDimension': '2d',
        'videoDuration': 'medium',  # Between 4-20 minutes
        'videoCaption': 'closedCaption'
    }
    
    # Add location parameters if provided
    if location:
        search_params.update({
            'location': f'{location[0]},{location[1]}', #location is in the form of (latitude, longitude)
            'locationRadius': '30km'
        })
    
    # Perform search
    search_response = youtube.search().list(**search_params).execute() ## ** -> unpacks the dictionary into keyword arguments

    # Extract video details
    video_details = []
    for item in search_response['items']:
        video_id = item['id']['videoId']
        
        # Get detailed video information including captions
        video_response = youtube.videos().list(
            part='id,snippet,contentDetails',
            id=video_id
        ).execute()
        
        if video_response['items']:
            video = video_response['items'][0]
            video_details.append({
                'id': video_id,
                'title': video['snippet']['title'],
                'description': video['snippet']['description'],
                'link': f'https://www.youtube.com/watch?v={video_id}',
                'has_captions': True,
                'duration': video['contentDetails']['duration']
            })
    
    return video_details

async def get_chat_response(client: AsyncGroq, messages: List[Dict[str, str]]) -> str:
    stream = await client.chat.completions.create(
        messages=messages,
        model=config.LLM_MODEL,
        temperature=0.5,
        max_completion_tokens=1024,
        stream=True
    )
    
    response = ""
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            response += delta
    return response

async def refine_ad_requirements():
    # Initialize client with API key
    client = AsyncGroq(api_key=config.GROQ_API_KEY)
    conversation = [
        {
            "role": "system",
            "content": """
            You are an AI advertising assistant tasked with understanding a client’s advertising requirements in detail. Engage the client in a professional yet conversational manner.

            Ask one focused question at a time to gather precise information.

            Clarify responses if needed before moving to the next question.

            Collect information on key aspects such as: target audience, campaign goals, preferred platforms, budget, tone/style, creative assets, and timeline.

            Summarize information periodically to ensure accuracy and alignment with client needs.

            Maintain a helpful, professional, and approachable tone throughout.

            Your goal: Build a comprehensive understanding of the client’s ad requirements efficiently and accurately.
            """
        }
    ]

    # Initial user input
    print("👋 Hello! Let’s make an ad that grabs attention. Tell me, what are we promoting today?")
    user_input = input("You: ")
    
    while True:
        # Add user message to conversation
        conversation.append({"role": "user", "content": user_input})
        
        # Get AI response
        response = await get_chat_response(client, conversation)
        print("\nAssistant:", response)
        
        # Add assistant response to conversation history
        conversation.append({"role": "assistant", "content": response})
        
        # Check if we have gathered enough information
        if len(conversation) >= 8:
            summary = await get_chat_response(client, [
                {
                    "role": "system",
                    "content": "Condense the collected information into a clear, 5-6 word phrase optimized for YouTube search."
                },
                {
                    "role": "user",
                    "content": str(conversation)
                }
            ])
            return summary
            
        user_input = input("\nYou: ")

async def llm_query():
    final_query = await refine_ad_requirements()

    results = search_youtube_videos(
        query=final_query
    )
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    asyncio.run(llm_query())
