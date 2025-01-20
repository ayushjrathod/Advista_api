import asyncio
import os
import json
from typing import List, Dict
import yt_dlp
from groq import Groq
import aiofiles
from concurrent.futures import ThreadPoolExecutor
import logging
from transcribe import Transcriber
import torch  # Add torch import

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, db):
        # Create absolute paths for directories
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.output_dir = os.path.join(self.base_dir, "downloaded_videos")
        
        # Create directories if they don't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.transcriber = Transcriber()
        self.db = db

    async def process_videos(self, video_details: List[Dict]) -> List[Dict]:
        tasks = []
        for video in video_details:
            tasks.append(self.process_single_video(video))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if r is not None]

    async def process_single_video(self, video: Dict, session_id: str) -> Dict:
        try:
            video_id = video['id']
            video_url = video['link']
            
            # Download video
            audio_path = await self.download_video_audio(video_url, video_id)
            if not audio_path:
                logger.error(f"Failed to download audio for video {video_id}")
                return None

            # Verify file exists before transcription
            if not os.path.exists(audio_path):
                logger.error(f"Audio file not found at {audio_path}")
                return None

            # Extract text using async transcription
            transcript = await self.transcriber.transcribe(audio_path)
            if not transcript:
                logger.error(f"Failed to transcribe video {video_id}")
                return None

            # Generate embedding from transcript using db's model
            try:
                with torch.no_grad():
                    transcript_embedding = self.db.model.encode(transcript).tolist()
            except Exception as e:
                logger.error(f"Failed to generate embedding for video {video_id}: {e}")
                transcript_embedding = None

            # Save transcript and embedding to youtube_insights
            await self.db.update_youtube_insight(
                session_id, 
                video_id, 
                transcript, 
                transcript_embedding
            )
            
            # Save Reddit data in background
            asyncio.create_task(self.db.save_reddit_data(session_id, video['title']))
            
            video['transcript'] = transcript
            video['embedding'] = transcript_embedding

            try:
                os.remove(audio_path)  # Clean up audio file after processing
            except OSError as e:
                logger.warning(f"Could not remove audio file {audio_path}: {e}")
            
            return video

        except Exception as e:
            logger.error(f"Error processing video {video['id']}: {str(e)}")
            return None

    async def download_video_audio(self, url: str, video_id: str) -> str:
        # Remove extension from output path as yt-dlp will add it
        output_path = os.path.join(self.output_dir, video_id)
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_path,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'quiet': True,
            'no_warnings': True
        }

        def _download():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                # Return the correct file path with extension
                return f"{output_path}.m4a"
            except Exception as e:
                logger.error(f"Download error for {video_id}: {str(e)}")
                return None

        # Run download in threadpool
        downloaded_path = await asyncio.get_event_loop().run_in_executor(None, _download)
        
        if downloaded_path and os.path.exists(downloaded_path):
            return downloaded_path
        return None