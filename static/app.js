document.addEventListener('DOMContentLoaded', () => {
  // ==========================================================================
  // DOM
  // ==========================================================================
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

  let currentVideoData = null;
  let activeTab = 'video';

  // ==========================================================================
  // PLATFORM DETECTION
  // ==========================================================================
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

  // ==========================================================================
  // TOAST
  // ==========================================================================
  function showToast(title, message, type = 'info', duration = 3000) {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    if (type === 'error') toast.classList.add('shake');

    let iconSvg = '';
    if (type === 'error') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else if (type === 'success') {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>`;
    } else {
      iconSvg = `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `
      ${iconSvg}
      <div class="toast-body">
        <div class="toast-title">${escapeHtml(title)}</div>
        <div class="toast-desc">${escapeHtml(message)}</div>
      </div>
      <button class="toast-close" aria-label="Close notification">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
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

  // ==========================================================================
  // PLATFORM CHIP
  // ==========================================================================
  function checkUrlPlatform(value) {
    const trimmed = (value || '').trim();
    if (!trimmed) {
      platformChip && platformChip.classList.remove('active');
      return;
    }
    let detected = null;
    for (const p of CLIENT_PLATFORMS) {
      if (p.regex.test(trimmed)) { detected = p; break; }
    }
    if (detected && platformChip) {
      platformChipName.textContent = detected.name;
      platformChip.style.background = detected.color;
      platformChip.classList.add('active');
    } else if ((trimmed.startsWith('http://') || trimmed.startsWith('https://')) && platformChip) {
      platformChipName.textContent = 'Web Video';
      platformChip.style.background = '#8b5cf6';
      platformChip.classList.add('active');
    } else if (platformChip) {
      platformChip.classList.remove('active');
    }
  }

  urlInput && urlInput.addEventListener('input', (e) => checkUrlPlatform(e.target.value));

  // ==========================================================================
  // PASTE
  // ==========================================================================
  btnPaste && btnPaste.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          checkUrlPlatform(text);
          showToast('URL Pasted', 'Clipboard contents inserted', 'info', 1500);
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

  // ==========================================================================
  // RIPPLE
  // ==========================================================================
  function createRipple(e) {
    const button = e.currentTarget;
    if (!button) return;
    const circle = document.createElement('span');
    const diameter = Math.max(button.clientWidth, button.clientHeight);
    const radius = diameter / 2;
    const rect = button.getBoundingClientRect();
    circle.style.width = circle.style.height = `${diameter}px`;
    circle.style.left = `${e.clientX - rect.left - radius}px`;
    circle.style.top = `${e.clientY - rect.top - radius}px`;
    circle.classList.add('ripple');
    const existing = button.getElementsByClassName('ripple')[0];
    if (existing) existing.remove();
    button.appendChild(circle);
  }

  // ==========================================================================
  // SUBMIT / FETCH
  // ==========================================================================
  if (form) {
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      triggerFetch();
    });
  }

  btnSubmit && btnSubmit.addEventListener('click', (e) => {
    createRipple(e);
    if (!form) triggerFetch();
  });

  async function triggerFetch() {
    const url = urlInput.value.trim();
    if (!url) {
      showToast('Input Required', 'Please paste a valid video URL.', 'error');
      urlInput.focus();
      return;
    }

    resultsSection && (resultsSection.style.display = 'none');
    loadingState && (loadingState.style.display = 'flex');
    skeletonLoader && (skeletonLoader.style.display = 'block');
    if (loadingStatusText) loadingStatusText.textContent = 'Analyzing video stream...';
    if (btnSubmit) {
      btnSubmit.disabled = true;
      btnSubmit.style.opacity = '0.7';
    }

    try {
      const response = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        const errorTitle = result.error || 'Extraction Failed';
        const errorDesc = result.en || result.detail || 'Could not fetch video';
        showToast(errorTitle, errorDesc, 'error', 5000);
        return;
      }

      currentVideoData = result.data;
      renderResults(result.data);
      showToast('Media Ready', 'Video formats retrieved successfully!', 'success', 2000);

      setTimeout(() => {
        resultsSection && resultsSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }, 80);
    } catch (err) {
      showToast('Connection Error', 'Network failed or server unreachable.', 'error');
    } finally {
      loadingState && (loadingState.style.display = 'none');
      skeletonLoader && (skeletonLoader.style.display = 'none');
      if (btnSubmit) {
        btnSubmit.disabled = false;
        btnSubmit.style.opacity = '1';
      }
    }
  }

  // ==========================================================================
  // RENDER
  // ==========================================================================
  function renderResults(data) {
    if (resultTitle) resultTitle.textContent = data.title || 'Untitled Video';
    if (resultThumbnail) resultThumbnail.src = data.thumbnail || '/static/img/placeholder.jpg';
    if (resultDuration) resultDuration.textContent = data.duration_formatted || '00:00';
    if (resultAuthor) resultAuthor.textContent = data.uploader || 'Creator';

    if (data.platform && resultPlatform) {
      resultPlatform.textContent = data.platform.name;
      resultPlatform.style.background = `${data.platform.color}25`;
      resultPlatform.style.color = data.platform.color;
      resultPlatform.style.borderColor = `${data.platform.color}50`;
    }

    renderVideoFormats(data.video_formats, data.webpage_url, data.best_direct_url);
    renderAudioFormats(data.audio_formats, data.webpage_url);

    resultsSection && (resultsSection.style.display = 'block');
  }

  function renderVideoFormats(formats, originalUrl, bestDirectUrl) {
    if (!videoGrid) return;
    videoGrid.innerHTML = '';

    if (!formats || formats.length === 0) {
      videoGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">No individual video formats discovered.</div>`;
      return;
    }

    formats.forEach((fmt) => {
      const card = document.createElement('div');
      card.className = `format-card ${fmt.is_recommended ? 'recommended' : ''}`;
      const badgeHtml = fmt.badge ? `<span class="format-badge">${escapeHtml(fmt.badge)}</span>` : '';
      const audioIndicator = fmt.has_audio ? 'Audio Included' : 'Auto Muxed Audio';

      card.innerHTML = `
        ${badgeHtml}
        <div class="format-title-group">
          <div class="format-quality">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            <span>${escapeHtml(fmt.label)}</span>
          </div>
          <div class="format-sub">${escapeHtml(fmt.resolution)} • MP4 • ${audioIndicator}</div>
        </div>
        <div class="format-footer">
          <span class="format-size">${escapeHtml(fmt.size_str || 'Standard Stream')}</span>
          <button type="button" class="btn-card-download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
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
          quality: 'best',
          // ⚡ Pass pre-computed direct URL only when it matches this format
          directUrl: (fmt.format_id === 'best' && fmt.direct_url) ? fmt.direct_url : (bestDirectUrl && fmt.format_id === 'best' ? bestDirectUrl : null),
        });
      });

      videoGrid.appendChild(card);
    });
  }

  function renderAudioFormats(formats, originalUrl) {
    if (!audioGrid) return;
    audioGrid.innerHTML = '';

    if (!formats || formats.length === 0) {
      audioGrid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 2rem; color: var(--text-muted);">Audio extraction unavailable.</div>`;
      return;
    }

    formats.forEach((fmt) => {
      const card = document.createElement('div');
      card.className = `format-card ${fmt.is_recommended ? 'recommended' : ''}`;
      const badgeHtml = fmt.badge ? `<span class="format-badge">${escapeHtml(fmt.badge)}</span>` : '';

      card.innerHTML = `
        ${badgeHtml}
        <div class="format-title-group">
          <div class="format-quality">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>
            <span>${escapeHtml(fmt.label)}</span>
          </div>
          <div class="format-sub">${escapeHtml(fmt.description)}</div>
        </div>
        <div class="format-footer">
          <span class="format-size">MP3 Audio</span>
          <button type="button" class="btn-card-download">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
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
          directUrl: null,
        });
      });

      audioGrid.appendChild(card);
    });
  }

  // ==========================================================================
  // TABS
  // ==========================================================================
  tabVideo && tabVideo.addEventListener('click', () => {
    if (activeTab === 'video') return;
    activeTab = 'video';
    tabVideo.classList.add('active');
    tabVideo.setAttribute('aria-selected', 'true');
    tabAudio && tabAudio.classList.remove('active');
    tabAudio && tabAudio.setAttribute('aria-selected', 'false');
    videoGrid && (videoGrid.style.display = 'grid');
    audioGrid && (audioGrid.style.display = 'none');
  });

  tabAudio && tabAudio.addEventListener('click', () => {
    if (activeTab === 'audio') return;
    activeTab = 'audio';
    tabAudio.classList.add('active');
    tabAudio.setAttribute('aria-selected', 'true');
    tabVideo && tabVideo.classList.remove('active');
    tabVideo && tabVideo.setAttribute('aria-selected', 'false');
    videoGrid && (videoGrid.style.display = 'none');
    audioGrid && (audioGrid.style.display = 'grid');
  });

  // ==========================================================================
  // DOWNLOAD — instant, with direct-url hint
  // ==========================================================================
  function initiateDownload({ url, format_id, type, quality, cardElement, directUrl }) {
    const btn = cardElement.querySelector('.btn-card-download');
    const btnText = cardElement.querySelector('.btn-text');
    const originalText = btnText ? btnText.textContent : 'Download';

    if (btnText) btnText.textContent = 'Starting...';
    if (btn) {
      btn.style.opacity = '0.75';
      btn.style.pointerEvents = 'none';
    }

    showToast('Download Started', 'Your browser will handle the download.', 'info', 1500);

    const params = new URLSearchParams({
      url: url,
      format_id: format_id,
      type: type,
      quality: quality || '192',
    });

    // ⚡ If we already have the CDN URL, pass it so backend skips yt-dlp
    if (directUrl && type === 'video' && format_id === 'best') {
      params.set('direct_url', directUrl);
    }

    const downloadUrl = `/api/download-direct?${params.toString()}`;

    // Native browser download — instant, honors Content-Disposition
    const a = document.createElement('a');
    a.href = downloadUrl;
    a.rel = 'noopener';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => a.remove(), 1500);

    // Reset button FAST (200ms instead of 1500ms)
    setTimeout(() => {
      if (btnText) btnText.textContent = originalText;
      if (btn) {
        btn.style.opacity = '1';
        btn.style.pointerEvents = 'auto';
      }
    }, 200);
  }
});
