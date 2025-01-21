import asyncio
import json
from dotenv import load_dotenv
from video_processor import VideoProcessor
import os

async def test_video_processor():
    # Test video details
    test_videos = [
        {
            'id': 'test_video_1',
            'link': 'https://www.youtube.com/watch?v=tfwZAsEhJ5A',  # Replace with your test video URL
            'title': 'Test Video 1'
        }
    ]

    try:
        # Initialize processor with optional ffmpeg path
        ffmpeg_path = os.getenv('FFMPEG_PATH')  # You can set this in .env file
        processor = VideoProcessor(
            output_dir="test_downloads",
            ffmpeg_location=ffmpeg_path
        )
        
        print(f"Using ffmpeg from: {processor.ffmpeg_location}")
        # Process videos
        print("Starting video processing...")
        results = await processor.process_videos(test_videos)
        
        # Print results
        print("\nProcessing Results:")
        print(json.dumps(results, indent=2))
        
        return results

    except Exception as e:
        print(f"Error during testing: {str(e)}")
        return None

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Run the test
    results = asyncio.run(test_video_processor())
