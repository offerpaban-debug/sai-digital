document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const form = document.getElementById('download-form');
  const urlInput = document.getElementById('video-url-input');
  const btnPaste = document.getElementById('btn-paste');
  const btnSubmit = document.getElementById('btn-submit');
  const platformChip = document.getElementById('platform-chip');
  const platformChipIcon = document.getElementById('platform-chip-icon');
  const platformChipName = document.getElementById('platform-chip-name');

  const loadingState = document.getElementById('loading-state');
  const loadingStatusText = document.getElementById('loading-status-text');
  const skeletonLoader = document.getElementById('skeleton-loader');
  const resultsSection = document.getElementById('results-section');

  const resultThumbnail = document.getElementById('result-thumbnail');
  const resultDuration = document.getElementById('result-duration');
  const resultPlatform = document.getElementById('result-platform');
  const resultTitle = document.getElementById('result-title');
  const resultAuthor = document.getElementById('result-author');

  const tabVideo = document.getElementById('tab-video');
  const tabAudio = document.getElementById('tab-audio');
  const videoGrid = document.getElementById('video-formats-grid');
  const audioGrid = document.getElementById('audio-formats-grid');
  const toastContainer = document.getElementById('toast-container');

  // State
  let currentVideoData = null;
  let activeTab = 'video'; // 'video' | 'audio'

  // Platform Matchers for Client-Side Instant Detection
  const CLIENT_PLATFORMS = [
    { name: 'Facebook', color: '#1877F2', regex: /(?:facebook\.com|fb\.watch|fb\.com)/i },
    { name: 'Instagram', color: '#E1306C', regex: /(?:instagram\.com|instagr\.am)/i },
    { name: 'TikTok', color: '#FE2C55', regex: /tiktok\.com/i },
    { name: 'Twitter / X', color: '#1DA1F2', regex: /(?:twitter\.com|x\.com)/i },
    { name: 'Pinterest', color: '#E60023', regex: /(?:pinterest\.com|pin\.it)/i },
    { name: 'Reddit', color: '#FF4500', regex: /(?:reddit\.com|redd\.it)/i },
    { name: 'Vimeo', color: '#1AB7EA', regex: /vimeo\.com/i },
    { name: 'Threads', color: '#8b5cf6', regex: /threads\.net/i },
  ];

  // Toast Notification System
  function showToast(title, message, type = 'info', duration = 4500) {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    if (type === 'error') {
      toast.classList.add('shake');
    }

    let iconSvg = '';
    if (type === 'error') {
      iconSvg = `
        <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
      `;
    } else if (type === 'success') {
      iconSvg = `
        <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
          <polyline points="22 4 12 14.01 9 11.01"></polyline>
        </svg>
      `;
    } else {
      iconSvg = `
        <svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="16" x2="12" y2="12"></line>
          <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
      `;
    }

    toast.innerHTML = `
      ${iconSvg}
      <div class="toast-body">
        <div class="toast-title">${escapeHtml(title)}</div>
        <div class="toast-desc">${escapeHtml(message)}</div>
      </div>
      <button class="toast-close" aria-label="Close notification">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="18" y1="6" x2="6" y2="18"></line>
          <line x1="6" y1="6" x2="18" y2="18"></line>
        </svg>
      </button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    const dismiss = () => {
      toast.classList.add('hiding');
      setTimeout(() => toast.remove(), 300);
    };

    closeBtn.addEventListener('click', dismiss);
    setTimeout(dismiss, duration);

    toastContainer.appendChild(toast);
  }

  function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Detect Platform on typing or paste
  function checkUrlPlatform(value) {
    const trimmed = value.trim();
    if (!trimmed) {
      platformChip.classList.remove('active');
      return;
    }

    let detected = null;
    for (const p of CLIENT_PLATFORMS) {
      if (p.regex.test(trimmed)) {
        detected = p;
        break;
      }
    }

    if (detected) {
      platformChipName.textContent = detected.name;
      platformChip.style.background = detected.color;
      platformChip.classList.add('active');
    } else if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      platformChipName.textContent = 'Web Video';
      platformChip.style.background = '#8b5cf6';
      platformChip.classList.add('active');
    } else {
      platformChip.classList.remove('active');
    }
  }

  urlInput.addEventListener('input', (e) => {
    checkUrlPlatform(e.target.value);
  });

  // Paste Button Handler
  btnPaste.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          checkUrlPlatform(text);
          showToast('URL Pasted', 'Clipboard contents inserted', 'info', 2000);
          // Auto trigger fetch for seamless experience
          triggerFetch();
        } else {
          showToast('Clipboard Empty', 'No text found in clipboard', 'info');
        }
      } else {
        urlInput.focus();
        showToast('Clipboard Access', 'Press Ctrl+V / Cmd+V to paste', 'info');
      }
    } catch (err) {
      urlInput.focus();
      showToast('Clipboard Notice', 'Please paste the URL directly into the box', 'info');
    }
  });

  // Add ripple micro-interaction to buttons
  function createRipple(e) {
    const button = e.currentTarget;
    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;
    const rect = button.getBoundingClientRect();

    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${e.clientX - rect.left - radius}px`;
    circle.style.top = `${e.clientY - rect.top - radius}px`;
    circle.classList.add('ripple');

    const ripple = button.getElementsByClassName('ripple')[0];
    if (ripple) {
      ripple.remove();
    }
    button.appendChild(circle);
  }

  btnSubmit.addEventListener('click', (e) => {
    createRipple(e);
    triggerFetch();
  });

  // Fetch Video Information
  async function triggerFetch() {
    const url = urlInput.value.trim();
    if (!url) {
      showToast('Input Required', 'Please paste a valid video URL.', 'error');
      urlInput.focus();
      return;
    }

    // UI Loading state
    resultsSection.style.display = 'none';
    loadingState.style.display = 'flex';
    skeletonLoader.style.display = 'block';
    loadingStatusText.textContent = 'Analyzing video stream...';
    btnSubmit.disabled = true;
    btnSubmit.style.opacity = '0.7';

    try {
      const response = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        const errorTitle = result.error || 'Extraction Failed';
        const errorDesc = result.en ? `${result.en}\n(${result.bn})` : (result.detail || 'Could not fetch video');
        showToast(errorTitle, errorDesc, 'error', 6000);
        return;
      }

      currentVideoData = result.data;
      renderResults(result.data);
      showToast('Media Ready', 'Video formats retrieved successfully!', 'success', 3000);

      // Smooth scroll to results
      setTimeout(() => {
        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 100);

    } catch (err) {
      showToast('Connection Error', 'Network failed or server unreachable. Please try again.', 'error');
    } finally {
      loadingState.style.display = 'none';
      skeletonLoader.style.display = 'none';
      btnSubmit.disabled = false;
      btnSubmit.style.opacity = '1';
    }
  }

  // Render Extracted Video Info and Formats
  function renderResults(data) {
    resultTitle.textContent = data.title || 'Untitled Video';
    resultThumbnail.src = data.thumbnail || '/static/img/placeholder.jpg';
    resultDuration.textContent = data.duration_formatted || '00:00';
    resultAuthor.textContent = data.uploader || 'Creator';

    if (data.platform) {
      resultPlatform.textContent = data.platform.name;
      resultPlatform.style.background = `${data.platform.color}25`;
      resultPlatform.style.color = data.platform.color;
      resultPlatform.style.borderColor = `${data.platform.color}50`;
    }

    renderVideoFormats(data.video_formats, data.webpage_url);
    renderAudioFormats(data.audio_formats, data.webpage_url);

    resultsSection.style.display = 'block';
  }

  // Render Video Format Cards
  function renderVideoFormats(formats, originalUrl) {
    videoGrid.innerHTML = '';

    if (!formats || formats.length === 0) {
      videoGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">
          No individual video formats discovered. Try the standard direct download.
        </div>
      `;
      return;
    }

    formats.forEach((fmt) => {
      const card = document.createElement('div');
      card.className = `format-card ${fmt.is_recommended ? 'recommended' : ''}`;
      
      const badgeHtml = fmt.badge ? `<span class="format-badge">${fmt.badge}</span>` : '';
      const audioIndicator = fmt.has_audio ? 'Audio Included' : 'Auto Muxed Audio';

      card.innerHTML = `
        ${badgeHtml}
        <div class="format-title-group">
          <div class="format-quality">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            <span>${fmt.label}</span>
          </div>
          <div class="format-sub">${fmt.resolution} • MP4 • ${audioIndicator}</div>
        </div>

        <div class="format-footer">
          <span class="format-size">${fmt.size_str || 'Standard Stream'}</span>
          <button type="button" class="btn-card-download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span class="btn-text">Download</span>
          </button>
        </div>
      `;

      card.addEventListener('click', (e) => {
        createRipple(e);
        initiateDownload({
          url: originalUrl,
          format_id: fmt.format_id,
          type: 'video',
          cardElement: card,
          quality: 'best'
        });
      });

      videoGrid.appendChild(card);
    });
  }

  // Render Audio Format Cards (MP3)
  function renderAudioFormats(formats, originalUrl) {
    audioGrid.innerHTML = '';

    if (!formats || formats.length === 0) {
      audioGrid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">
          Audio extraction unavailable for this media stream.
        </div>
      `;
      return;
    }

    formats.forEach((fmt) => {
      const card = document.createElement('div');
      card.className = `format-card ${fmt.is_recommended ? 'recommended' : ''}`;
      const badgeHtml = fmt.badge ? `<span class="format-badge">${fmt.badge}</span>` : '';

      card.innerHTML = `
        ${badgeHtml}
        <div class="format-title-group">
          <div class="format-quality">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 18V5l12-2v13"></path>
              <circle cx="6" cy="18" r="3"></circle>
              <circle cx="18" cy="16" r="3"></circle>
            </svg>
            <span>${fmt.label}</span>
          </div>
          <div class="format-sub">${fmt.description}</div>
        </div>

        <div class="format-footer">
          <span class="format-size">MP3 Audio</span>
          <button type="button" class="btn-card-download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            <span class="btn-text">Download MP3</span>
          </button>
        </div>
      `;

      card.addEventListener('click', (e) => {
        createRipple(e);
        initiateDownload({
          url: originalUrl,
          format_id: 'bestaudio',
          type: 'audio',
          quality: fmt.quality || '192',
          cardElement: card,
        });
      });

      audioGrid.appendChild(card);
    });
  }

  // Tab Switching (Video vs Audio)
  tabVideo.addEventListener('click', () => {
    if (activeTab === 'video') return;
    activeTab = 'video';
    tabVideo.classList.add('active');
    tabVideo.setAttribute('aria-selected', 'true');
    tabAudio.classList.remove('active');
    tabAudio.setAttribute('aria-selected', 'false');

    videoGrid.style.display = 'grid';
    audioGrid.style.display = 'none';
  });

  tabAudio.addEventListener('click', () => {
    if (activeTab === 'audio') return;
    activeTab = 'audio';
    tabAudio.classList.add('active');
    tabAudio.setAttribute('aria-selected', 'true');
    tabVideo.classList.remove('active');
    tabVideo.setAttribute('aria-selected', 'false');

    videoGrid.style.display = 'none';
    audioGrid.style.display = 'grid';
  });

  // ONE-CLICK INSTANT DOWNLOAD
  async function initiateDownload({ url, format_id, type, quality, cardElement }) {
    const btn = cardElement.querySelector('.btn-card-download');
    const btnText = cardElement.querySelector('.btn-text');
    const originalText = btnText ? btnText.textContent : 'Download';

    if (btnText) btnText.textContent = 'Processing...';
    btn.style.opacity = '0.75';
    btn.style.pointerEvents = 'none';

    showToast('Download Initiated', 'Preparing media stream for your browser...', 'info', 3000);

    try {
      const downloadUrl = `/api/download-direct?url=${encodeURIComponent(url)}&format_id=${encodeURIComponent(format_id)}&type=${encodeURIComponent(type)}&quality=${encodeURIComponent(quality || '192')}`;
      
      // Trigger native browser download instantly with zero client memory buffer delay
      const downloadAnchor = document.createElement('a');
      downloadAnchor.href = downloadUrl;
      downloadAnchor.setAttribute('download', '');
      downloadAnchor.style.display = 'none';
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();

      setTimeout(() => {
        downloadAnchor.remove();
      }, 2000);

      showToast('Download Started', 'Media transfer has started in your browser!', 'success', 4000);

    } catch (err) {
      showToast('Download Error', 'Could not initiate media transfer', 'error');
    } finally {
      setTimeout(() => {
        if (btnText) btnText.textContent = originalText;
        btn.style.opacity = '1';
        btn.style.pointerEvents = 'auto';
      }, 800);
    }
  }
});
