"""
YouTube research service: search videos/shorts via SerpAPI and extract transcripts.
"""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from youtube_transcript_api import YouTubeTranscriptApi

from src.services.serpapi_service import SerpApiService

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=3)

TOP_VIDEOS_COUNT = 3
TOP_SHORTS_COUNT = 5


def _extract_video_id(link: str) -> Optional[str]:
    """Extract YouTube video ID from watch URL or shorts URL."""
    if not link:
        return None
    # watch URL: https://www.youtube.com/watch?v=VIDEO_ID
    match = re.search(r"[?&]v=([a-zA-Z0-9_-]{11})", link)
    if match:
        return match.group(1)
    # shorts URL: https://www.youtube.com/shorts/VIDEO_ID
    match = re.search(r"/shorts/([a-zA-Z0-9_-]{11})", link)
    if match:
        return match.group(1)
    return None


def _fetch_transcript(video_id: str) -> str:
    """Fetch transcript for a YouTube video. Returns empty string on failure."""
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id)
        if transcript:
            text = " ".join(s.text for s in transcript)
            # TODO: remove after debugging
            logger.info(f"[YT] Transcript fetched | video_id={video_id} | len={len(text)}")
            return text
        # TODO: remove after debugging
        logger.warning(f"[YT] Transcript empty | video_id={video_id}")
        return ""
    except Exception as e:
        logger.warning(f"Could not fetch transcript for {video_id}: {e}")
        # TODO: remove after debugging
        logger.warning(f"[YT] Transcript fetch failed | video_id={video_id} | error={e}")
        return ""


def _flatten_shorts(shorts_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flatten shorts_results sections into a single list. Each item has video_id or link."""
    flat = []
    for section in shorts_results or []:
        for short in section.get("shorts", []):
            vid = short.get("video_id") or _extract_video_id(short.get("link", ""))
            if vid:
                flat.append({**short, "video_id": vid})
    return flat


def run_youtube_research(search_query: str) -> Dict[str, Any]:
    """
    Search YouTube, get top 3 videos and top 5 shorts, fetch transcripts.
    Returns structure compatible with analysis/synthesis.
    """
    # TODO: remove after debugging
    logger.info(f"[YT] run_youtube_research starting | query={search_query[:80]}...")
    service = SerpApiService()
    raw = service.search_youtube(search_query)

    error = raw.get("error")
    if error:
        logger.error(f"YouTube API error: {error}")
        # TODO: remove after debugging
        logger.error(f"[YT] SerpAPI error | error={error}")
        return {"query": search_query, "videos": [], "shorts": [], "error": str(error)}

    video_results = raw.get("video_results", [])
    shorts_results = raw.get("shorts_results", [])
    flat_shorts = _flatten_shorts(shorts_results)
    # TODO: remove after debugging
    logger.info(f"[YT] Parsing results | video_results={len(video_results)} | flat_shorts={len(flat_shorts)}")

    videos_with_transcripts = []
    for idx, item in enumerate(video_results[:TOP_VIDEOS_COUNT]):
        link = item.get("link", "")
        video_id = _extract_video_id(link)
        if not video_id:
            continue
        transcript = _fetch_transcript(video_id)
        channel = item.get("channel", {}).get("name", "") if isinstance(item.get("channel"), dict) else ""
        # TODO: remove after debugging
        logger.info(f"[YT] Video[{idx+1}] | title={item.get('title', '')[:40]}... | channel={channel} | transcript_len={len(transcript)}")
        videos_with_transcripts.append({
            "title": item.get("title", ""),
            "link": link,
            "channel": channel,
            "published_date": item.get("published_date", ""),
            "views": item.get("views"),
            "length": item.get("length", ""),
            "description": item.get("description", ""),
            "video_id": video_id,
            "transcript": transcript,
        })

    shorts_with_transcripts = []
    for idx, item in enumerate(flat_shorts[:TOP_SHORTS_COUNT]):
        video_id = item.get("video_id")
        if not video_id:
            continue
        transcript = _fetch_transcript(video_id)
        # TODO: remove after debugging
        logger.info(f"[YT] Short[{idx+1}] | title={item.get('title', '')[:40]}... | video_id={video_id} | transcript_len={len(transcript)}")
        shorts_with_transcripts.append({
            "title": item.get("title", ""),
            "link": item.get("link", ""),
            "views": item.get("views"),
            "views_original": item.get("views_original", ""),
            "video_id": video_id,
            "transcript": transcript,
        })

    # TODO: remove after debugging
    logger.info(f"[YT] run_youtube_research complete | videos={len(videos_with_transcripts)} | shorts={len(shorts_with_transcripts)}")
    return {
        "query": search_query,
        "videos": videos_with_transcripts,
        "shorts": shorts_with_transcripts,
    }


async def run_youtube_research_async(search_query: str) -> Dict[str, Any]:
    """Run YouTube research asynchronously via thread pool."""
    # TODO: remove after debugging
    logger.info(f"[YT] run_youtube_research_async invoked | query={search_query[:80]}...")
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(executor, run_youtube_research, search_query)
    # TODO: remove after debugging
    logger.info(f"[YT] run_youtube_research_async done | videos={len(result.get('videos', []))} | shorts={len(result.get('shorts', []))}")
    return result
