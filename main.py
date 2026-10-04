import os
import re
import json
import time
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import requests

from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import (
    HTMLResponse,
    FileResponse,
    JSONResponse,
    StreamingResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from utils import detect_platform, classify_error, sanitize_filename
from downloader import (
    extract_video_info,
    download_media_file,
    get_direct_stream_url,
    cleanup_old_files,
    validate_url,
    DOWNLOADS_DIR,
)

# ==============================================================================
# LOGGING
# ==============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("saidigital.app")

# ==============================================================================
# CONFIG
# ==============================================================================
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "5"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
MAX_STREAM_BYTES = 500 * 1024 * 1024
STREAM_CONNECT_TIMEOUT = 20
STREAM_READ_TIMEOUT = 120

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{RATE_LIMIT_PER_MINUTE}/minute"],
)

# ==============================================================================
# BLOG POSTS DATA
# ==============================================================================
BLOG_POSTS: List[Dict[str, Any]] = [
    {
        "slug": "how-to-download-facebook-videos-mobile-2025",
        "title": "How to Download Facebook Videos on Mobile (2025 Guide)",
        "category": "Facebook",
        "author": "Sai Digital Editorial",
        "date": "January 15, 2025",
        "read_time": "6 min read",
        "image": "https://images.unsplash.com/photo-1611162617213-7d7a39e9b1d7?auto=format&fit=crop&w=1200&q=80",
        "excerpt": "Learn the fastest and safest methods to save high-definition Facebook public videos, reels, and stories directly to your Android or iPhone camera roll without watermarks.",
        "keywords": "facebook video download mobile, download fb reels, save facebook video android, fb video downloader hd",
        "content_html": """
<h2>Introduction: Why Save Facebook Videos Locally?</h2>
<p>Facebook is home to millions of educational clips, entertaining reels, news reports, and creative masterclasses shared every day. However, Facebook does not provide a native button to save these media files directly into your smartphone gallery or camera roll. If you want to watch a tutorial offline during a commute, backup your favorite creator's recipe, or share a video on messaging apps, having a reliable online video downloader is essential.</p>
<p>In this updated 2025 guide, we break down step-by-step instructions for both <strong>Android</strong> and <strong>iOS (iPhone &amp; iPad)</strong> users to download public Facebook videos in 1080p Full HD without installing suspicious third-party apps or risk-laden APKs.</p>

<h2>Step 1: Copy the Public Video Link from Facebook</h2>
<p>Whether you are using the Facebook Android app, iOS app, or mobile web browser, getting the correct shareable link is straightforward:</p>
<ol>
  <li>Open the Facebook application and locate the video or reel you wish to download.</li>
  <li>Tap the <strong>Share</strong> button located beneath the video post.</li>
  <li>In the share sheet that appears, select <strong>Copy Link</strong>.</li>
  <li>Verify that the post privacy is set to <strong>Public</strong> (indicated by the globe icon). Private group videos or friend-only posts cannot be fetched by public download tools due to platform privacy safeguards.</li>
</ol>
<blockquote><strong>Pro Tip:</strong> If you don't see the "Copy Link" button immediately, tap the three dots (<code>...</code>) in the upper-right corner of the video card and tap <strong>Copy link</strong>.</blockquote>

<h2>Step 2: Use Sai Digital Universal Downloader</h2>
<p>Once you have copied the URL:</p>
<ol>
  <li>Open your preferred mobile browser (Google Chrome, Safari, Samsung Internet, or Brave).</li>
  <li>Visit <strong>Sai Digital</strong> at the homepage.</li>
  <li>Paste your copied link into the input field at the top. The platform will automatically recognize it as a Facebook video link.</li>
  <li>Tap the <strong>Fetch Video Formats</strong> button.</li>
  <li>In just 1 to 2 seconds, the tool will analyze the media stream and display a preview thumbnail, video duration, and available resolutions ranging from <strong>720p HD</strong> to <strong>1080p Full HD</strong>.</li>
  <li>Select your preferred resolution and tap <strong>Download</strong>. The video will begin downloading immediately to your device.</li>
</ol>

<h2>Step 3: Finding Your Downloaded Video on Mobile</h2>
<h3>On Android Devices:</h3>
<ul>
  <li>Open your default <strong>Files</strong> or <strong>My Files</strong> application.</li>
  <li>Navigate to the <strong>Downloads</strong> directory.</li>
  <li>You can also view it directly inside <strong>Google Photos</strong> or your smartphone default <strong>Gallery</strong> app under the "Downloads" album.</li>
</ul>

<h3>On iPhone / iPad (iOS):</h3>
<ul>
  <li>Open <strong>Safari</strong> or your browser download manager by tapping the download icon in the address bar.</li>
  <li>Tap on the downloaded <code>.mp4</code> file.</li>
  <li>Tap the <strong>Share</strong> icon at the bottom-left and choose <strong>Save Video</strong> to move it permanently into your <strong>Apple Photos</strong> camera roll.</li>
</ul>

<h2>Safety &amp; Copyright Guidelines</h2>
<ol>
  <li><strong>Never install unknown APKs or browser extensions:</strong> Third-party apps frequently bundle adware or track account credentials. Browser-based online tools are 100% safer.</li>
  <li><strong>Respect Copyright &amp; Intellectual Property:</strong> Only download videos for personal offline reference. Do not re-upload or commercially monetize other creators' content without permission.</li>
  <li><strong>Respect Private Profiles:</strong> Sai Digital strictly adheres to user privacy boundaries and does not download private or DRM-encrypted streams.</li>
</ol>

<h2>Summary</h2>
<p>Downloading Facebook videos on mobile in 2025 is seamless when using a browser-based, zero-installation platform like Sai Digital. With support for high-bitrate MP4 video and pristine audio conversion, you can enjoy your favorite content anytime, anywhere without buffering or watermark clutter.</p>
        """,
    },
    {
        "slug": "instagram-reels-download-complete-tutorial",
        "title": "Instagram Reels Download: Complete Tutorial",
        "category": "Instagram",
        "author": "Sai Digital Editorial",
        "date": "January 20, 2025",
        "read_time": "5 min read",
        "image": "https://images.unsplash.com/photo-1611262588024-d12430b98920?auto=format&fit=crop&w=1200&q=80",
        "excerpt": "Master the easiest way to save Instagram Reels, videos, and IGTV clips with original audio in crisp 1080p without any annoying compression or watermarks.",
        "keywords": "instagram reels download, save insta reels with audio, instagram video downloader 1080p",
        "content_html": """
<h2>The Rise of Instagram Reels in 2025</h2>
<p>Instagram Reels has evolved into one of the world's most vibrant hubs for short-form entertainment, fashion tips, educational masterclasses, and music discovery. While Instagram allows creators to enable or disable in-app saving, built-in downloads often strip out trending audio tracks due to licensing restrictions or superimpose unsightly platform logos.</p>
<p>If you want to save Instagram Reels <strong>with clear original sound</strong> in crystal-clear high definition, this guide provides the exact steps you need.</p>

<h2>Why Does In-App Download Often Mute Audio?</h2>
<p>When you attempt to save an Instagram Reel inside the official app, Instagram's music copyright filters frequently mute licensed commercial songs to comply with regional record label contracts. As a result, users end up with silent video clips. Sai Digital bypasses this limitation by extracting the direct CDN audio-video multiplex stream, ensuring your saved MP4 retains 100% of the original audio track.</p>

<h2>Step-by-Step: How to Download Any Public Instagram Reel</h2>
<ol>
  <li><strong>Obtain the Reel URL:</strong> Open Instagram on your phone or computer, find the Reel you wish to save, tap the <strong>Paper Airplane (Share)</strong> icon on the right, and select <strong>Copy Link</strong>.</li>
  <li><strong>Open Sai Digital Downloader:</strong> Navigate to the Sai Digital homepage in your web browser.</li>
  <li><strong>Paste and Analyze:</strong> Paste the copied link into the URL input bar. Notice how the intelligent engine automatically recognizes the Instagram link.</li>
  <li><strong>Instant Download:</strong> Tap <strong>Fetch Video Formats</strong>, select your target resolution or MP3 audio option, and click <strong>Download</strong>. Your file will start downloading instantly.</li>
</ol>

<h2>Supported Instagram Media Types</h2>
<ul>
  <li><strong>Instagram Reels:</strong> 9:16 vertical video format up to 1080p 60fps.</li>
  <li><strong>Feed Videos:</strong> Traditional landscape or square video posts.</li>
  <li><strong>Carousel Videos:</strong> Individual clips extracted cleanly from multi-slide carousel posts.</li>
  <li><strong>Original Audio MP3:</strong> Want just the trending background song or podcast clip? Switch to the "Audio (MP3)" tab to save pure 320kbps sound.</li>
</ul>

<h2>Troubleshooting &amp; FAQ</h2>
<table>
  <thead>
    <tr><th>Issue</th><th>Possible Cause</th><th>Recommended Solution</th></tr>
  </thead>
  <tbody>
    <tr><td>Video Not Found</td><td>Profile is set to private</td><td>Only public reels can be fetched</td></tr>
    <tr><td>No Audio Playback</td><td>Device media volume muted</td><td>Check phone sound and silent mode switch</td></tr>
    <tr><td>Broken Link Error</td><td>Expired story or temporary link</td><td>Ensure you copied the permanent Reel URL</td></tr>
  </tbody>
</table>

<h2>Conclusion</h2>
<p>Saving Instagram Reels for offline reference, creative moodboards, or study notes is effortless with Sai Digital. Enjoy rapid, watermark-free access to your favorite media library on any device.</p>
        """,
    },
    {
        "slug": "tiktok-video-download-without-watermark",
        "title": "TikTok Video Download Without Watermark — 3 Easy Ways",
        "category": "TikTok",
        "author": "Sai Digital Editorial",
        "date": "February 2, 2025",
        "read_time": "5 min read",
        "image": "https://images.unsplash.com/photo-1596558450255-7c0b7be9d56a?auto=format&fit=crop&w=1200&q=80",
        "excerpt": "Discover how to remove the bouncing TikTok watermark and username overlay to download pristine HD TikTok videos for presentations, backups, and cross-platform editing.",
        "keywords": "tiktok video download without watermark, no watermark tiktok downloader, save tiktok hd",
        "content_html": """
<h2>Why Remove the TikTok Watermark?</h2>
<p>When you download a video directly within the official TikTok application using the built-in "Save video" function, TikTok inserts a bouncing logo and creator username tag across the video corners. While this helps brand the platform, it can significantly obstruct subtitles, block key visual elements, or interfere with professional video compilation projects.</p>
<p>For content creators managing backups of their own published material or researchers studying short-form video choreography, having a clean, watermark-free high-definition file is essential.</p>

<h2>3 Working Methods to Download TikToks Without Watermark</h2>
<h3>Method 1: Online Web Downloader (Fastest &amp; Safest)</h3>
<p>Using a zero-installation web downloader like <strong>Sai Digital</strong> is the superior method. You do not need to install dubious apps or share your account credentials. You simply paste the TikTok link, and the system delivers the original unbranded MP4 stream directly from the content delivery network.</p>

<h3>Method 2: iOS Live Photo Conversion</h3>
<p>On iPhone, you can save a TikTok as a "Live Photo" and then use the Photos app to "Save as Video." However, this method frequently reduces visual fidelity, causes frame drops, and re-compresses the audio track.</p>

<h3>Method 3: Telegram Bot Utilities</h3>
<p>Some automated Telegram bots can strip watermarks, but they are frequently taken offline, pose privacy concerns, and limit file sizes.</p>

<h2>Step-by-Step Guide Using Sai Digital</h2>
<ol>
  <li><strong>Copy Video Link from TikTok:</strong> Open TikTok, find your video, tap the curved <strong>Share</strong> arrow on the lower right, and tap <strong>Copy link</strong>.</li>
  <li><strong>Paste into Sai Digital:</strong> Navigate to the Sai Digital homepage and paste the URL into the search bar.</li>
  <li><strong>One-Click Download:</strong> Tap <strong>Fetch Video Formats</strong> and click <strong>Download</strong> on the best quality option. The video is saved directly to your phone or desktop in under 2 seconds.</li>
</ol>

<h2>Feature Comparison Table</h2>
<table>
  <thead>
    <tr><th>Feature</th><th>Official TikTok App</th><th>Sai Digital Downloader</th></tr>
  </thead>
  <tbody>
    <tr><td>Watermark Status</td><td>Bouncing logo overlay</td><td>100% Watermark-Free</td></tr>
    <tr><td>Resolution Quality</td><td>Compressed 720p</td><td>Full HD 1080p Original</td></tr>
    <tr><td>Audio Extraction</td><td>Not Available</td><td>Dedicated 320kbps MP3 Audio</td></tr>
    <tr><td>Storage Footprint</td><td>App required (300MB+)</td><td>Zero installation required</td></tr>
  </tbody>
</table>

<h2>Ethical Guidelines</h2>
<p>Always respect original creators. When using watermark-free clips for editorial, educational, or review purposes, always provide proper attribution to the original author.</p>
        """,
    },
    {
        "slug": "how-to-convert-any-video-to-mp3-audio",
        "title": "How to Convert Any Video to MP3 Audio (Step-by-Step)",
        "category": "Audio Conversion",
        "author": "Sai Digital Editorial",
        "date": "February 12, 2025",
        "read_time": "5 min read",
        "image": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1200&q=80",
        "excerpt": "Extract studio-master audio tracks from your favorite web videos and concerts directly into high-fidelity 320kbps MP3 format powered by FFmpeg sound pipelines.",
        "keywords": "video to mp3 converter, extract audio from video, mp3 320kbps converter",
        "content_html": """
<h2>Why Convert Video to MP3?</h2>
<p>In many scenarios, you do not need the heavy video stream; you only want the sound. Podcasts, keynote speeches, educational seminars, acoustic sessions, and meditation audio tracks are much lighter in file size when stripped of visual data.</p>
<p>A 100MB 1080p video file can easily be converted into an ultra-high-fidelity <strong>320kbps MP3 file measuring under 8MB</strong>, saving vast amounts of mobile storage and battery life during playback.</p>

<h2>Key Advantages of Audio-Only Conversion</h2>
<ul>
  <li><strong>Massive Storage Savings:</strong> Audio files are up to 90% smaller than high-definition video containers, allowing you to store thousands of lectures or songs on your phone.</li>
  <li><strong>Extended Battery Life:</strong> Playing audio with your phone screen turned off consumes a fraction of the battery power required for video decoding.</li>
  <li><strong>Convenient Offline Listening:</strong> Enjoy seamless audio during commutes, workouts, or flights without buffering interruptions.</li>
</ul>

<h2>How Sai Digital Converts Video to MP3 Using FFmpeg</h2>
<p>Unlike basic web converters that compress sound into muffled, tinny audio, Sai Digital leverages professional <strong>FFmpeg</strong> audio processing engines on the backend:</p>
<ol>
  <li><strong>Audio Stream Extraction:</strong> The original high-bitrate AAC or Opus track is extracted directly from the video container.</li>
  <li><strong>Dynamic Resampling:</strong> The audio is processed through high-precision filters to prevent distortion, popping, or clipped dynamic frequencies.</li>
  <li><strong>Multi-Bitrate Encoding:</strong> Choose between <strong>320 kbps (Ultra Studio Quality)</strong>, <strong>192 kbps (High Quality)</strong>, and <strong>128 kbps (Standard Compact)</strong>.</li>
</ol>

<h2>Bitrate Comparison Guide</h2>
<table>
  <thead>
    <tr><th>Bitrate</th><th>Audio Quality</th><th>Approx. Size (5-min track)</th><th>Best For</th></tr>
  </thead>
  <tbody>
    <tr><td><strong>320 kbps</strong></td><td>Studio Master Quality</td><td>~11.5 MB</td><td>Music, Concerts, Audiophile Headphones</td></tr>
    <tr><td><strong>192 kbps</strong></td><td>Crisp &amp; Clear</td><td>~7.0 MB</td><td>Podcasts, Talks, Everyday Listening</td></tr>
    <tr><td><strong>128 kbps</strong></td><td>Standard Sound</td><td>~4.6 MB</td><td>Voice Memos, Spoken Word Lectures</td></tr>
  </tbody>
</table>

<h2>Summary</h2>
<p>Converting video into MP3 is the ultimate way to build an offline audio library on your phone. Try Sai Digital instant audio engine today for crisp, watermark-free listening on any device.</p>
        """,
    },
    {
        "slug": "top-10-safe-video-downloader-sites-2025",
        "title": "Top 10 Safe Video Downloader Sites in 2025 (Expert Review)",
        "category": "Safety & Reviews",
        "author": "Sai Digital Editorial",
        "date": "February 28, 2025",
        "read_time": "7 min read",
        "image": "https://images.unsplash.com/photo-1563986768609-322da13575f3?auto=format&fit=crop&w=1200&q=80",
        "excerpt": "Stay protected against malicious popups and fake download buttons. Here is our curated assessment of the safest and most efficient online video download utilities in 2025.",
        "keywords": "safe video downloader sites 2025, best video downloader online, download video without malware",
        "content_html": """
<h2>The Landscape of Video Downloaders in 2025</h2>
<p>Finding a trustworthy online video downloader can feel like navigating a digital minefield. Many traditional downloader websites are cluttered with deceptive "Download Now" advertisement banners, unwanted redirects, crypto-mining scripts, or requests to install dangerous browser extensions.</p>
<p>To protect your personal data and smartphone safety, we have evaluated the top qualities that define a genuinely safe video downloading service in 2025.</p>

<h2>Key Hallmarks of a Trustworthy Video Downloader</h2>
<ol>
  <li><strong>No Credit Card or Registration Demanded:</strong> A legitimate utility never asks for payment credentials or personal subscriptions to access basic downloading tools.</li>
  <li><strong>Absence of Deceptive Pop-Under Redirects:</strong> Clicking buttons should trigger the expected action, not open gambling or phishing tabs.</li>
  <li><strong>No Forced Extension or APK Downloads:</strong> Modern HTML5 and cloud backends can process media streams directly in the browser.</li>
  <li><strong>Strict HTTPS SSL Encryption:</strong> Look for the secure padlock icon in the browser address bar.</li>
</ol>

<h2>Why Sai Digital Sets the Benchmark</h2>
<p><strong>Sai Digital</strong> was engineered from the ground up to solve common user frustrations:</p>
<ul>
  <li><strong>Clean SaaS Glassmorphism UI:</strong> Beautiful, intuitive interface modeled on top-tier modern web applications.</li>
  <li><strong>Zero In-Stream Malware:</strong> No aggressive fake download buttons or deceptive click-jackers.</li>
  <li><strong>Open Architecture:</strong> Powered by robust open-source tools like <code>yt-dlp</code> and <code>FFmpeg</code>.</li>
  <li><strong>Platform Auto-Detection:</strong> Paste any public video URL and the engine automatically configures optimal codecs.</li>
</ul>

<h2>Cybersecurity Best Practices for Media Archiving</h2>
<ul>
  <li>Keep your mobile browser (Chrome, Safari, Firefox) updated to the latest version to benefit from built-in phishing protections.</li>
  <li>Never enter your social media passwords on third-party downloader sites.</li>
  <li>Always verify the file extension of downloaded items (it should be <code>.mp4</code> or <code>.mp3</code>, never <code>.exe</code>, <code>.apk</code>, or <code>.scr</code>).</li>
</ul>

<h2>Conclusion</h2>
<p>Safe, ad-free video downloading is achievable with modern web standards. By choosing clean, transparent platforms like Sai Digital, you can enjoy seamless offline entertainment while keeping your devices thoroughly secure.</p>
        """,
    },
]


def get_all_blog_posts(category: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
    posts = BLOG_POSTS
    if category and category.lower() != "all":
        posts = [p for p in posts if p.get("category", "").lower() == category.lower()]
    if search:
        s = search.lower().strip()
        posts = [
            p for p in posts
            if s in p.get("title", "").lower()
            or s in p.get("excerpt", "").lower()
            or s in p.get("category", "").lower()
        ]
    return posts


def get_blog_post_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    for p in BLOG_POSTS:
        if p["slug"] == slug:
            return p
    return None


def get_all_categories() -> List[str]:
    return sorted(list(set(p["category"] for p in BLOG_POSTS if p.get("category"))))


def get_related_blog_posts(slug: str, category: str, limit: int = 3) -> List[Dict[str, Any]]:
    related = [p for p in BLOG_POSTS if p["slug"] != slug and p.get("category") == category]
    if len(related) < limit:
        others = [p for p in BLOG_POSTS if p["slug"] != slug and p not in related]
        related.extend(others)
    return related[:limit]


# ==============================================================================
# LIFESPAN
# ==============================================================================
async def periodic_cleanup_task():
    while True:
        try:
            purged = cleanup_old_files()
            if purged > 0:
                logger.info(f"Periodic cleaner removed {purged} expired download files.")
        except Exception as e:
            logger.error(f"Error in cleanup background task: {e}")
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    cleanup_task = asyncio.create_task(periodic_cleanup_task())
    logger.info("Sai Digital Universal Downloader & Blog Hub online.")
    yield
    cleanup_task.cancel()
    logger.info("Sai Digital background tasks stopped.")


# ==============================================================================
# APP
# ==============================================================================
app = FastAPI(
    title="Sai Digital - Universal Video Downloader & Blog Hub",
    description="High-performance universal video and audio extraction service.",
    version="3.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": "Rate limited",
            "en": "Too many requests, please wait a minute.",
            "detail": "Rate limit exceeded. Maximum requests reached.",
        },
    )


ALLOWED_ORIGINS = [
    "https://sai-digital.onrender.com",
    "http://localhost:7860",
    "http://127.0.0.1:7860",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://.*\.onrender\.com",
    allow_credentials=False,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length"],
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ==============================================================================
# MODELS
# ==============================================================================
class InfoRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    format_id: Optional[str] = "best"
    type: Optional[str] = "video"
    quality: Optional[str] = "192"


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: Optional[str] = ""
    message: str


# ==============================================================================
# PAGES
# ==============================================================================
@app.get("/", response_class=HTMLResponse)
@app.head("/")
async def serve_index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/health")
@app.head("/health")
async def health_check():
    import yt_dlp
    return {
        "status": "healthy",
        "service": "Sai Digital",
        "engine": "yt-dlp",
        "yt_dlp_version": yt_dlp.version.__version__,
        "youtube_enabled": os.getenv("ENABLE_YOUTUBE", "false").lower() == "true",
        "environment": ENVIRONMENT,
    }


# ==============================================================================
# API: INFO
# ==============================================================================
@app.post("/api/info")
@limiter.limit(f"{max(RATE_LIMIT_PER_MINUTE * 2, 10)}/minute")
async def get_media_info(payload: InfoRequest, request: Request):
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail={"en": "URL cannot be empty"})

    if not validate_url(url):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "Unsupported URL",
                "en": "This link is not from a supported platform.",
                "detail": "Only Facebook, Instagram, TikTok, Twitter/X, Pinterest, Reddit, Vimeo, Threads are supported.",
            },
        )

    try:
        data = await asyncio.to_thread(extract_video_info, url)
        return {"success": True, "data": data}
    except Exception as exc:
        err_info = classify_error(exc)
        logger.warning(f"Info extraction error for {url}: {exc}")
        return JSONResponse(
            status_code=err_info["status_code"],
            content={
                "success": False,
                "error": err_info["title"],
                "en": err_info["en"],
                "detail": err_info["detail"],
            },
        )


# ==============================================================================
# SAFE STREAMING HELPERS
# ==============================================================================
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _iter_remote_chunks(stream_url: str, referer: Optional[str] = None):
    headers = {"User-Agent": BROWSER_UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    total = 0
    with requests.get(
        stream_url,
        headers=headers,
        stream=True,
        timeout=(STREAM_CONNECT_TIMEOUT, STREAM_READ_TIMEOUT),
        allow_redirects=True,
    ) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=128 * 1024):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_STREAM_BYTES:
                logger.warning("Stream exceeded max size cap; aborting.")
                break
            yield chunk


def _content_disposition(filename: str) -> str:
    safe = sanitize_filename(filename or "media")
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(safe)}"


# ==============================================================================
# API: DOWNLOAD (POST)
# ==============================================================================
@app.post("/api/download")
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def download_media_post(payload: DownloadRequest, request: Request):
    return await _do_download(
        url=payload.url,
        format_id=payload.format_id or "best",
        media_type=payload.type or "video",
        quality=payload.quality or "192",
    )


# ==============================================================================
# API: DOWNLOAD-DIRECT (GET)
# ==============================================================================
@app.get("/api/download-direct")
@limiter.limit(f"{RATE_LIMIT_PER_MINUTE}/minute")
async def download_media_get(
    request: Request,
    url: str,
    format_id: str = "best",
    type: str = "video",
    quality: str = "192",
):
    return await _do_download(
        url=url,
        format_id=format_id or "best",
        media_type=type or "video",
        quality=quality or "192",
    )


async def _do_download(url: str, format_id: str, media_type: str, quality: str):
    clean_url = (url or "").strip()
    if not clean_url:
        raise HTTPException(status_code=400, detail={"en": "URL cannot be empty"})

    if not validate_url(clean_url):
        raise HTTPException(
            status_code=400,
            detail={"en": "Unsupported URL. Only allowed platforms are permitted."},
        )

    if media_type == "video":
        try:
            direct = await asyncio.to_thread(get_direct_stream_url, clean_url, format_id)
        except Exception as e:
            logger.warning(f"Direct URL lookup failed: {e}")
            direct = None

        if direct and direct.get("stream_url"):
            filename = direct["filename"]
            ctype = direct.get("content_type") or "video/mp4"
            referer = direct.get("referer") or clean_url
            logger.info(f"Streaming directly from CDN: {filename}")
            return StreamingResponse(
                _iter_remote_chunks(direct["stream_url"], referer=referer),
                media_type=ctype,
                headers={
                    "Content-Disposition": _content_disposition(filename),
                    "Cache-Control": "no-store",
                    "X-Accel-Buffering": "no",
                },
            )

    try:
        result = await asyncio.to_thread(
            download_media_file,
            clean_url,
            format_id,
            media_type,
            quality,
        )
    except Exception as exc:
        err_info = classify_error(exc)
        logger.error(f"Media download failed: {exc}")
        return JSONResponse(
            status_code=err_info["status_code"],
            content={
                "success": False,
                "error": err_info["title"],
                "en": err_info["en"],
                "detail": err_info["detail"],
            },
        )

    file_path = result["file_path"]
    download_name = result["filename"]
    content_type = result["content_type"]

    abs_path = os.path.abspath(file_path)
    abs_root = os.path.abspath(DOWNLOADS_DIR)
    if not abs_path.startswith(abs_root + os.sep):
        raise HTTPException(status_code=400, detail={"en": "Invalid file path."})

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail={"en": "File not found after processing."})

    filesize = os.path.getsize(abs_path)
    if filesize > MAX_STREAM_BYTES:
        try:
            os.remove(abs_path)
        except Exception:
            pass
        raise HTTPException(status_code=413, detail={"en": "File exceeds the 500 MB limit."})

    return FileResponse(
        path=abs_path,
        media_type=content_type,
        headers={
            "Content-Disposition": _content_disposition(download_name),
            "Cache-Control": "no-store",
            "Access-Control-Expose-Headers": "Content-Disposition, Content-Length",
        },
    )


# ==============================================================================
# BLOG
# ==============================================================================
@app.get("/blog", response_class=HTMLResponse)
async def blog_list(request: Request, category: Optional[str] = None, q: Optional[str] = None):
    posts = get_all_blog_posts(category=category, search=q)
    categories = get_all_categories()
    return templates.TemplateResponse(
        request=request,
        name="blog.html",
        context={
            "posts": posts,
            "categories": categories,
            "current_category": category,
            "search_query": q,
        },
    )


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def blog_post_detail(slug: str, request: Request):
    post = get_blog_post_by_slug(slug)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found")
    related = get_related_blog_posts(slug, post.get("category", "General"), limit=3)
    return templates.TemplateResponse(
        request=request,
        name="post.html",
        context={"post": post, "related_posts": related},
    )


# ==============================================================================
# STATIC PAGES
# ==============================================================================
@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse(request=request, name="about.html")


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse(request=request, name="privacy.html")


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse(request=request, name="terms.html")


@app.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse(request=request, name="contact.html")


@app.get("/disclaimer", response_class=HTMLResponse)
async def disclaimer_page(request: Request):
    return templates.TemplateResponse(request=request, name="disclaimer.html")


@app.post("/api/contact")
@limiter.limit("3/minute")
async def contact_submit(payload: ContactRequest, request: Request):
    try:
        contacts_file = os.path.join(DOWNLOADS_DIR, "contact_inquiries.json")
        entries = []
        if os.path.exists(contacts_file):
            try:
                with open(contacts_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = []

        new_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "name": payload.name.strip()[:200],
            "email": payload.email.strip()[:200],
            "subject": (payload.subject or "General Inquiry").strip()[:300],
            "message": payload.message.strip()[:5000],
        }
        entries.append(new_entry)

        with open(contacts_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

        logger.info(f"New contact inquiry recorded from {payload.email}")
        return {"success": True, "message": "Inquiry successfully recorded."}
    except Exception as e:
        logger.error(f"Contact form logging error: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": "Unable to save inquiry."},
        )


# ==============================================================================
# SEO
# ==============================================================================
@app.get("/sitemap.xml")
async def sitemap_xml(request: Request):
    base_url = str(request.base_url).rstrip("/")
    current_date = time.strftime("%Y-%m-%d")
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f'  <url><loc>{base_url}/</loc><lastmod>{current_date}</lastmod><changefreq>daily</changefreq><priority>1.0</priority></url>',
        f'  <url><loc>{base_url}/blog</loc><lastmod>{current_date}</lastmod><changefreq>daily</changefreq><priority>0.9</priority></url>',
        f'  <url><loc>{base_url}/about</loc><lastmod>{current_date}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>',
        f'  <url><loc>{base_url}/contact</loc><lastmod>{current_date}</lastmod><changefreq>monthly</changefreq><priority>0.8</priority></url>',
        f'  <url><loc>{base_url}/privacy</loc><lastmod>{current_date}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>',
        f'  <url><loc>{base_url}/terms</loc><lastmod>{current_date}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>',
        f'  <url><loc>{base_url}/disclaimer</loc><lastmod>{current_date}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>',
    ]
    for p in BLOG_POSTS:
        xml_lines.append(
            f'  <url><loc>{base_url}/blog/{p["slug"]}</loc><lastmod>{current_date}</lastmod><changefreq>weekly</changefreq><priority>0.85</priority></url>'
        )
    xml_lines.append("</urlset>")
    return Response(content="\n".join(xml_lines), media_type="application/xml")


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return f"User-agent: *\nAllow: /\n\nSitemap: {base_url}/sitemap.xml\n"


# ==============================================================================
# RUNNER
# ==============================================================================
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "7860"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info(f"Starting Sai Digital on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
