import os
import time
import uuid
import glob
import logging
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

import yt_dlp

from utils import detect_platform, format_duration, format_size, sanitize_filename

logger = logging.getLogger("saidigital.downloader")

DOWNLOADS_DIR = os.getenv("DOWNLOADS_DIR", "downloads")
MAX_FILE_AGE_SECONDS = int(os.getenv("MAX_FILE_AGE_SECONDS", "300"))
ENABLE_YOUTUBE = os.getenv("ENABLE_YOUTUBE", "false").lower() == "true"

os.makedirs(DOWNLOADS_DIR, exist_ok=True)

INFO_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600


# ==============================================================================
# URL VALIDATION
# ==============================================================================
ALLOWED_HOSTS = (
    "facebook.com", "fb.watch", "fb.com", "m.facebook.com", "www.facebook.com",
    "instagram.com", "www.instagram.com", "instagr.am",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "twitter.com", "www.twitter.com", "x.com", "www.x.com", "mobile.twitter.com",
    "pinterest.com", "www.pinterest.com", "pin.it",
    "reddit.com", "www.reddit.com", "redd.it", "old.reddit.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    "threads.net", "www.threads.net",
)


def validate_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    host = (parsed.hostname or "").lower()
    if not host:
        return False

    if "youtube" in host or "youtu.be" in host:
        return ENABLE_YOUTUBE

    for allowed in ALLOWED_HOSTS:
        if host == allowed or host.endswith("." + allowed):
            return True
    return False


# ==============================================================================
# CLEANUP
# ==============================================================================
def cleanup_old_files() -> int:
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

    expired_keys = [
        k for k, v in INFO_CACHE.items()
        if (now - v.get("timestamp", 0)) > CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        INFO_CACHE.pop(k, None)

    return deleted_count


# ==============================================================================
# YT-DLP BASE OPTS
# ==============================================================================
def _base_ydl_opts() -> Dict[str, Any]:
    return {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
        "no_color": True,
        "ignoreerrors": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
    }


# ==============================================================================
# INFO EXTRACTION
# ==============================================================================
def extract_video_info(url: str) -> Dict[str, Any]:
    clean_url = url.strip()
    platform_info = detect_platform(clean_url)

    if platform_info["id"] == "youtube" and not ENABLE_YOUTUBE:
        raise ValueError("YouTube downloads are temporarily disabled on this instance")

    if not validate_url(clean_url):
        raise ValueError("Unsupported or invalid URL")

    now = time.time()
    cached = INFO_CACHE.get(clean_url)
    if cached and (now - cached.get("timestamp", 0)) < CACHE_TTL_SECONDS:
        return cached["data"]

    ydl_opts = _base_ydl_opts()
    ydl_opts.update({
        "skip_download": True,
        "extract_flat": False,
        "check_formats": False,
        "youtube_include_dash_manifest": False,
        "youtube_include_hls_manifest": False,
    })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(clean_url, download=False)

    if not info:
        raise ValueError("No video data found. Please verify the URL.")

    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    title = info.get("title") or "Untitled Media"
    thumbnail = info.get("thumbnail") or "/static/img/placeholder.jpg"
    duration = info.get("duration")
    uploader = info.get("uploader") or info.get("channel") or platform_info["name"]
    webpage_url = info.get("webpage_url") or clean_url

    raw_formats = info.get("formats") or []
    video_formats: List[Dict[str, Any]] = []

    best_direct_url = None
    if info.get("ext") == "mp4" and info.get("url"):
        best_direct_url = info["url"]

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

    video_candidates.sort(
        key=lambda x: (x.get("height") or 0, x.get("filesize") or x.get("filesize_approx") or 0),
        reverse=True,
    )

    for cand in video_candidates:
        h = cand.get("height")
        if not h:
            continue
        matched_h = min(standard_heights, key=lambda x: abs(x - h))
        if matched_h in seen_heights:
            continue
        seen_heights.add(matched_h)

        ext = cand.get("ext", "mp4")
        filesize = cand.get("filesize") or cand.get("filesize_approx")
        acodec = cand.get("acodec")
        has_audio = bool(acodec) and acodec != "none"
        label = resolution_names.get(matched_h, f"{matched_h}p")

        direct_link = None
        if has_audio and ext == "mp4" and cand.get("url"):
            direct_link = cand["url"]

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

    INFO_CACHE[clean_url] = {
        "timestamp": now,
        "raw_info": info,
        "data": result_data,
    }
    return result_data


# ==============================================================================
# DIRECT STREAM URL — Storage = 0 path
# ==============================================================================
def get_direct_stream_url(url: str, format_id: str = "best") -> Optional[Dict[str, str]]:
    """
    Return a direct CDN URL for video (muxed MP4) — Storage = 0.
    Only returns URLs that contain BOTH video + audio in a single stream.
    """
    clean_url = url.strip()
    if not validate_url(clean_url):
        return None

    cached = INFO_CACHE.get(clean_url)
    if not cached or "raw_info" not in cached:
        try:
            extract_video_info(clean_url)
            cached = INFO_CACHE.get(clean_url)
        except Exception as e:
            logger.warning(f"Cache rebuild failed for {clean_url}: {e}")
            return None

    if not cached or "raw_info" not in cached:
        return None

    raw_info = cached["raw_info"]
    raw_formats = raw_info.get("formats") or []
    title = sanitize_filename(raw_info.get("title") or "video")
    referer = raw_info.get("webpage_url") or clean_url

    def _is_muxed_mp4(f: Dict[str, Any]) -> bool:
        return (
            bool(f.get("url"))
            and f.get("ext") == "mp4"
            and f.get("vcodec") not in (None, "none")
            and f.get("acodec") not in (None, "none")
        )

    if format_id == "best":
        # top-level direct mp4
        if raw_info.get("ext") == "mp4" and raw_info.get("url"):
            return {
                "stream_url": raw_info["url"],
                "filename": f"{title}.mp4",
                "content_type": "video/mp4",
                "referer": referer,
            }
        muxed = [f for f in raw_formats if _is_muxed_mp4(f)]
        if muxed:
            muxed.sort(
                key=lambda x: (x.get("height") or 0, x.get("tbr") or 0),
                reverse=True,
            )
            best = muxed[0]
            return {
                "stream_url": best["url"],
                "filename": f"{title}.mp4",
                "content_type": "video/mp4",
                "referer": referer,
            }
        return None

    # Specific format_id
    for f in raw_formats:
        if str(f.get("format_id")) == str(format_id) and _is_muxed_mp4(f):
            return {
                "stream_url": f["url"],
                "filename": f"{title}.mp4",
                "content_type": "video/mp4",
                "referer": referer,
            }
    return None


# ==============================================================================
# FALLBACK: SERVER-SIDE DOWNLOAD
# ==============================================================================
def download_media_file(
    url: str,
    format_id: str = "best",
    media_type: str = "video",
    audio_quality: str = "192",
) -> Dict[str, Any]:
    clean_url = url.strip()
    platform_info = detect_platform(clean_url)

    if platform_info["id"] == "youtube" and not ENABLE_YOUTUBE:
        raise ValueError("YouTube downloads are temporarily disabled on this instance")

    if not validate_url(clean_url):
        raise ValueError("Unsupported or invalid URL")

    unique_token = uuid.uuid4().hex[:10]
    out_tmpl = os.path.join(
        DOWNLOADS_DIR, f"saidigital_{unique_token}_%(title).50s.%(ext)s"
    )

    if media_type == "audio":
        ydl_opts = _base_ydl_opts()
        ydl_opts.update({
            "format": "bestaudio/best",
            "outtmpl": out_tmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": audio_quality,
                }
            ],
            "concurrent_fragment_downloads": 4,
            "buffersize": 65536,
        })
        target_ext = "mp3"
        content_type = "audio/mpeg"
    else:
        if format_id == "best":
            selected_fmt = (
                "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo+bestaudio/"
                "best[ext=mp4]/best"
            )
        else:
            selected_fmt = f"{format_id}+bestaudio/best/{format_id}/best"

        ydl_opts = _base_ydl_opts()
        ydl_opts.update({
            "format": selected_fmt,
            "outtmpl": out_tmpl,
            "merge_output_format": "mp4",
            "concurrent_fragment_downloads": 4,
            "buffersize": 65536,
        })
        target_ext = "mp4"
        content_type = "video/mp4"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(clean_url, download=True)
        raw_title = (info_dict.get("title") if info_dict else None) or "video"

    pattern = os.path.join(DOWNLOADS_DIR, f"saidigital_{unique_token}_*")
    matching_files = glob.glob(pattern)

    if not matching_files:
        raise FileNotFoundError("Processed download file could not be found.")

    final_filepath = matching_files[0]
    for mf in matching_files:
        if mf.lower().endswith("." + target_ext):
            final_filepath = mf
            break

    safe_title = sanitize_filename(raw_title)
    download_filename = f"{safe_title}.{target_ext}"

    abs_path = os.path.abspath(final_filepath)
    abs_root = os.path.abspath(DOWNLOADS_DIR)
    if not abs_path.startswith(abs_root + os.sep):
        raise ValueError("Resolved file path escaped the downloads directory.")

    return {
        "file_path": abs_path,
        "filename": download_filename,
        "content_type": content_type,
        "filesize": os.path.getsize(abs_path),
    }
