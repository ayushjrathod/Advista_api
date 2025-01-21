import os
import json
from googleapiclient.discovery import build
from datetime import datetime
from groq import Groq,AsyncGroq
import asyncio
import os
from typing import List, Dict
from dotenv import load_dotenv

def search_youtube_videos(query, location=None, api_key="AIzaSyDWcpgnmYdYRiVGv5EmNwTYLX80ZNycyqA"):
    """
    Search YouTube videos with specific parameters
    Args:
        query (str): Search query
        location (tuple, optional): Tuple of (latitude, longitude)
        api_key (str, optional): YouTube API key
    Returns:
        list: List of video details
    """
    youtube = build('youtube', 'v3', developerKey=api_key or os.getenv("YOUTUBE_API_KEY"))
    
    # Base search parameters
    search_params = {
        'part': 'id,snippet',
        'q': query,
        'maxResults': 4,
        'type': 'video',
        'videoDimension': '2d',
        'videoDuration': 'medium',  # Between 4-20 minutes
        'videoCaption': 'closedCaption'
    }
    
    # Add location parameters if provided
    if location:
        search_params.update({
            'location': f'{location[0]},{location[1]}',
            'locationRadius': '15km'
        })
    
    # Perform search
    search_response = youtube.search().list(**search_params).execute()
    
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
                'has_captions': True,  # Since we filtered for videos with captions
                'duration': video['contentDetails']['duration']
            })
    
    return video_details


# Load environment variables
load_dotenv()

async def get_chat_response(client: AsyncGroq, messages: List[Dict[str, str]]) -> str:
    stream = await client.chat.completions.create(
        messages=messages,
        model="llama-3.3-70b-versatile",
        temperature=0.7,
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
    client = AsyncGroq(api_key=os.getenv('GROQ_API_KEY'))
    conversation = [
        {
            "role": "system",
            "content": """You are an AI advertising assistant helping to gather detailed information about ad requirements. 
            Ask focused questions one at a time to understand the client's needs. After each user response, evaluate if you have 
            enough information to generate a 4-5 word YouTube search query. If you do, respond ONLY with '[SUFFICIENT]' followed 
            by your suggested 4-5 word search query on a new line. Otherwise, ask another relevant question."""
        }
    ]

    print("Hello! I'm here to help you create an effective advertisement. What would you like to create an ad for?")
    user_input = input("You: ")
    
    while True:
        conversation.append({"role": "user", "content": user_input})
        
        response = await get_chat_response(client, conversation)
        print("\nAssistant:", response)
        
        if '[SUFFICIENT]' in response:
            # Extract the search query (everything after [SUFFICIENT])
            search_query = response.split('[SUFFICIENT]')[1].strip()
            return search_query
            
        conversation.append({"role": "assistant", "content": response})
        user_input = input("\nYou: ")
        
        # Add explicit stop condition
        if user_input.lower() in ['stop', 'quit', 'exit']:
            return None

async def llm_query():
    final_query = await refine_ad_requirements()
    if final_query:
        print("\nFinal query of Requirements:")
        print(final_query)
        results = search_youtube_videos(query=final_query)
        print(json.dumps(results, indent=2))
    else:
        print("\nSearch cancelled by user.")

if __name__ == "__main__":
    asyncio.run(llm_query())

# Example usage:
if __name__ == "__main__":
    # Example search with location (San Francisco coordinates)
    # async def llm_query():
    #     final_query = await refine_ad_requirements()
    #     print("\nFinal query of Requirements:")
    #     print(final_query)
    # asyncio.run(llm_query())
    # print("youtube_query",final_query)
    


    '''
    ok so the main task here is this :Task 1: Automated Research and Trigger Finder (ART Finder)

    Objective: The objective of ART Finder is to streamline the research phase of ad creation by automating data gathering and analysis. This tool will:

    Identify user pain points and triggers from YouTube
    Analyze competitor ads and strategies to uncover high-performing hooks, CTAs, and content formats.
    Generate actionable insights and suggestions to help marketers craft effective, user-centric ads.
    Key Features:

    Comprehensive Research Automation:
    Analyzes YouTube videos and competitor ads to identify trends, pain points, and effective solutions.
    Actionable Insights Generation:
    Summarizes key triggers and user problems. Suggests best-performing hooks, CTAs, and solutions tailored to the topic and audience.
    Reference Dashboard:
    Provides direct links to scraped YouTube videos and competitor ads for easy validation and inspiration. Visualizes insights with graphs, word clouds, and sentiment analysis.
    User-Centric Interface:
    Simple input fields for topics and brand guidelines. Intuitive dashboard showcasing insights and recommendations at a glance. But right now the 1st step or the 2nd stepo i am working on is to formulate proper search like if 
    '''

import yt_dlp

def download_youtube_video(url, output_path):

    try:
        ydl_opts = {
            'outtmpl': f'{output_path}/%(title)s.%(ext)s',  # Output path and filename template
            'format': 'bestvideo+bestaudio/best',  # Download the best available quality
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print(f"Downloaded video from '{url}' successfully!")
    except Exception as e:
        print(f"An error occurred: {e}")

'''Example usage
    video_url = "https://www.youtube.com/watch?v=L8ypSXwyBds&t=1046s"
    output_path = "./demo video3.mp4"  # Specify your desired output path
    download_youtube_video(video_url, output_path)
'''

# Initialize the Groq client
client = Groq()

# Specify the path to the audio file
filename = os.path.dirname(__file__) + "/sample_audio.m4a" # Replace with your audio file!

# Open the audio file
with open(filename, "rb") as file:
    # Create a translation of the audio file
    translation = client.audio.translations.create(
      file=(filename, file.read()), # Required audio file
      model="whisper-large-v3", # Required model to use for translation
      prompt="Specify context or spelling",  # Optional
      response_format="json",  # Optional
      temperature=0.0  # Optional
    )
    # Print the translation text
    print(translation.text)