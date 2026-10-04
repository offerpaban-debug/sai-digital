import os
import time
import uuid
import glob
import logging
from typing import Dict, Any, List, Optional
import yt_dlp

from utils import detect_platform, format_duration, format_size, sanitize_filename

logger = logging.getLogger("vidgrab.downloader")

DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
MAX_FILE_AGE_SECONDS = int(os.getenv("MAX_FILE_AGE_SECONDS", "1800"))
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "false").lower() == "true"

# Ensure target storage directory exists
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# In-Memory Cache for fast response times (TTL: 10 minutes)
INFO_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600

def cleanup_old_files() -> int:
    """Purges cached downloads older than MAX_FILE_AGE_SECONDS."""
    now = time.time()
    deleted_count = 0
    try:
        for entry in os.scandir(DOWNLOADS_DIR):
            if entry.is_file():
                try:
                    file_age = now - entry.stat().st_mtime
                    if file_age > MAX_FILE_AGE_SECONDS:
                        os.remove(entry.path)
                        deleted_count += 1
                except Exception as file_err:
                    logger.warning(f"Failed to delete {entry.path}: {file_err}")
    except Exception as e:
        logger.error(f"Error during download directory cleanup: {e}")

    # Also purge expired memory cache items
    expired_keys = [k for k, v in INFO_CACHE.items() if (now - v.get("timestamp", 0)) > CACHE_TTL_SECONDS]
    for k in expired_keys:
        INFO_CACHE.pop(k, None)

    return deleted_count

def extract_video_info(url: str) -> Dict[str, Any]:
    """
    Extracts high-fidelity metadata, thumbnail, duration, and structured
    video & audio format options with optimized speed (< 1-2s).
    """
    clean_url = url.strip()
    platform_info = detect_platform(clean_url)

    if platform_info["id"] == "youtube" and not ENABLE_YOUTUBE:
        raise ValueError("YouTube downloads are temporarily disabled on this instance")

    # Check cache for instantaneous return
    now = time.time()
    cached = INFO_CACHE.get(clean_url)
    if cached and (now - cached.get("timestamp", 0)) < CACHE_TTL_SECONDS:
        return cached["data"]

    # Highly optimized options for lightning fast extraction
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": 8,
        "retries": 1,
        "extract_flat": "in_playlist",
        "check_formats": False,  # CRITICAL SPEEDUP: Do not send HEAD requests to format URLs
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
        "no_color": True,
        "ignoreerrors": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(clean_url, download=False)
        except Exception as e:
            raise e

    if not info:
        raise ValueError("No video data found. Please verify the URL.")

    # If playlist was returned, pick primary entry
    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    title = info.get("title") or "Untitled Media"
    thumbnail = info.get("thumbnail") or "/static/img/placeholder.jpg"
    duration = info.get("duration")
    uploader = info.get("uploader") or info.get("channel") or platform_info["name"]
    webpage_url = info.get("webpage_url") or clean_url

    raw_formats = info.get("formats") or []
    video_formats: List[Dict[str, Any]] = []

    # Best combined option (Recommended Default)
    best_direct_url = info.get("url") if info.get("ext") == "mp4" else None
    video_formats.append({
        "format_id": "best",
        "label": "Best Quality (Auto MP4)",
        "resolution": "HD / Best",
        "ext": "mp4",
        "has_audio": True,
        "size_str": format_size(info.get("filesize") or info.get("filesize_approx")),
        "is_recommended": True,
        "badge": "Recommended",
        "direct_url": best_direct_url,
    })

    # Group video formats by standard resolution heights
    seen_heights = set()
    standard_heights = [2160, 1440, 1080, 720, 480, 360, 240, 144]
    resolution_names = {
        2160: "4K Ultra HD",
        1440: "2K Quad HD",
        1080: "1080p Full HD",
        720: "720p HD",
        480: "480p SD",
        360: "360p Medium",
        240: "240p Low",
        144: "144p Compact",
    }

    video_candidates = []
    for f in raw_formats:
        vcodec = f.get("vcodec")
        height = f.get("height")
        if vcodec and vcodec != "none" and height:
            video_candidates.append(f)

    # Sort descending by height and filesize
    video_candidates.sort(key=lambda x: (x.get("height") or 0, x.get("filesize") or 0), reverse=True)

    for cand in video_candidates:
        h = cand.get("height")
        if not h:
            continue

        matched_h = min(standard_heights, key=lambda x: abs(x - h))
        if matched_h not in seen_heights:
            seen_heights.add(matched_h)
            ext = cand.get("ext", "mp4")
            filesize = cand.get("filesize") or cand.get("filesize_approx")
            has_audio = cand.get("acodec") != "none" and cand.get("acodec") is not None
            label = resolution_names.get(matched_h, f"{matched_h}p")

            # Direct URL available from CDN
            direct_link = cand.get("url") if (has_audio and ext == "mp4") else None

            video_formats.append({
                "format_id": str(cand.get("format_id")),
                "label": label,
                "resolution": f"{matched_h}p",
                "ext": "mp4",
                "has_audio": has_audio,
                "size_str": format_size(filesize),
                "is_recommended": False,
                "badge": "HD" if matched_h >= 720 else "SD",
                "direct_url": direct_link,
            })

    # High-Fidelity Audio MP3 options
    audio_formats = [
        {
            "format_id": "mp3-320",
            "quality": "320",
            "label": "MP3 320 kbps",
            "badge": "Ultra Audio",
            "ext": "mp3",
            "description": "Studio Master Quality • FFmpeg Enhanced",
            "is_recommended": True,
        },
        {
            "format_id": "mp3-192",
            "quality": "192",
            "label": "MP3 192 kbps",
            "badge": "High Quality",
            "ext": "mp3",
            "description": "Crisp Sound • Recommended for Music",
            "is_recommended": False,
        },
        {
            "format_id": "mp3-128",
            "quality": "128",
            "label": "MP3 128 kbps",
            "badge": "Standard",
            "ext": "mp3",
            "description": "Fast Download • Small File Size",
            "is_recommended": False,
        },
    ]

    result_data = {
        "title": title,
        "thumbnail": thumbnail,
        "duration_seconds": duration,
        "duration_formatted": format_duration(duration),
        "uploader": uploader,
        "webpage_url": webpage_url,
        "platform": platform_info,
        "video_formats": video_formats,
        "audio_formats": audio_formats,
    }

    # Store in fast memory cache
    INFO_CACHE[clean_url] = {
        "timestamp": now,
        "raw_info": info,
        "data": result_data,
    }

    return result_data

def get_direct_stream_url(url: str, format_id: str = "best") -> Optional[Dict[str, str]]:
    """Checks if a direct CDN URL is available to stream immediately without disk write."""
    clean_url = url.strip()
    cached = INFO_CACHE.get(clean_url)
    if not cached or "raw_info" not in cached:
        return None

    raw_info = cached["raw_info"]
    raw_formats = raw_info.get("formats") or []
    title = sanitize_filename(raw_info.get("title") or "video")

    if format_id == "best" and raw_info.get("ext") == "mp4" and raw_info.get("url"):
        return {
            "stream_url": raw_info["url"],
            "filename": f"{title}.mp4",
            "content_type": "video/mp4",
        }

    for f in raw_formats:
        if str(f.get("format_id")) == str(format_id):
            if f.get("url") and f.get("acodec") != "none" and f.get("ext") == "mp4":
                return {
                    "stream_url": f["url"],
                    "filename": f"{title}.mp4",
                    "content_type": "video/mp4",
                }
    return None

def download_media_file(
    url: str,
    format_id: str = "best",
    media_type: str = "video",
    audio_quality: str = "192"
) -> Dict[str, Any]:
    """
    Downloads and converts requested media (Video MP4 or Audio MP3) into
    the persistent download directory using accelerated parallel pipelines.
    """
    clean_url = url.strip()
    platform_info = detect_platform(clean_url)

    if platform_info["id"] == "youtube" and not ENABLE_YOUTUBE:
        raise ValueError("YouTube downloads are temporarily disabled on this instance")

    unique_token = uuid.uuid4().hex[:10]
    out_tmpl = os.path.join(DOWNLOADS_DIR, f"vidgrab_{unique_token}_%(title).50s.%(ext)s")

    if media_type == "audio":
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }
            ],
            "postprocessor_args": {
                "FFmpegExtractAudio": ["-threads", "4", "-preset", "ultrafast"]
            },
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
            "concurrent_fragment_downloads": 8,
            "buffersize": 65536,
        }
        target_ext = "mp3"
        content_type = "audio/mpeg"
    else:
        if format_id == "best":
            selected_fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
        else:
            selected_fmt = f"{format_id}+bestaudio/best/{format_id}/best"

        ydl_opts = {
            "format": selected_fmt,
            "outtmpl": out_tmpl,
            "merge_output_format": "mp4",
            "postprocessor_args": {
                "Merger": ["-threads", "4", "-c", "copy"]  # Stream copy without re-encoding!
            },
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "socket_timeout": 15,
            "check_formats": False,
            "concurrent_fragment_downloads": 8,
            "buffersize": 65536,
        }
        target_ext = "mp4"
        content_type = "video/mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(clean_url, download=True)
        raw_title = info_dict.get("title") if info_dict else "video"

    # Locate generated output file
    pattern = os.path.join(DOWNLOADS_DIR, f"vidgrab_{unique_token}_*")
    matching_files = glob.glob(pattern)

    if not matching_files:
        raise FileNotFoundError("Processed download file could not be found.")

    final_filepath = matching_files[0]
    safe_title = sanitize_filename(raw_title)
    download_filename = f"{safe_title}.{target_ext}"

    return {
        "file_path": final_filepath,
        "filename": download_filename,
        "content_type": content_type,
        "filesize": os.path.getsize(final_filepath),
    }
