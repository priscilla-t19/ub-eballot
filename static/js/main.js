// UB eBallot — Main JS

// ── Service Worker Registration ───────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js')
      .then(registration => {
        console.log('SW registered:', registration.scope);

        // Handle updates
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // New version available
              showUpdateNotification();
            }
          });
        });
      })
      .catch(error => console.log('SW registration failed:', error));
  });
}

// ── PWA Update Notification ──────────────
function showUpdateNotification() {
  const notification = document.createElement('div');
  notification.className = 'flash flash-info';
  notification.innerHTML = `
    <span>A new version is available! Refresh to update.</span>
    <button class="flash-close" onclick="this.parentElement.remove()">×</button>
    <button onclick="updateApp()" style="margin-left: 1rem; background: #003087; color: white; border: none; padding: 0.25rem 0.5rem; border-radius: 4px; cursor: pointer;">Update</button>
  `;
  document.querySelector('.flash-container')?.appendChild(notification) ||
  document.body.insertBefore(notification, document.body.firstChild);
}

function updateApp() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.ready.then(registration => {
      registration.waiting?.postMessage({ type: 'SKIP_WAITING' });
    });
    window.location.reload();
  }
}

// ── Mobile Detection & Optimizations ──────
const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                 (window.innerWidth <= 768 && window.innerHeight <= 1024);

if (isMobile) {
  document.documentElement.classList.add('mobile-device');
}

// ── Touch Device Optimizations ────────────
if ('ontouchstart' in window) {
  // Prevent double-tap zoom on buttons
  document.querySelectorAll('button, .btn, .candidate-option').forEach(el => {
    el.addEventListener('touchstart', e => {
      // Prevent ghost clicks
      e.target.style.transform = 'scale(0.98)';
      setTimeout(() => e.target.style.transform = '', 150);
    }, { passive: true });
  });

  // Improve scrolling on iOS
  document.addEventListener('touchmove', e => {
    if (e.target.closest('.scrollable')) {
      e.stopPropagation();
    }
  }, { passive: true });
}

// ── Mobile Nav ────────────────────────────
const navToggle = document.getElementById('navToggle');
const navMobile = document.getElementById('navMobile');
if (navToggle && navMobile) {
  navToggle.addEventListener('click', () => navMobile.classList.toggle('open'));

  // Close mobile nav when clicking outside
  document.addEventListener('click', e => {
    if (!navToggle.contains(e.target) && !navMobile.contains(e.target)) {
      navMobile.classList.remove('open');
    }
  });
}

// ── Auto-dismiss flash messages ───────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.5s';
    setTimeout(() => el.remove(), 500);
  }, 6000);
});

// ── Form loading spinner ──────────────────
// Any form with data-loading="true" will show a spinner on the submit button
document.querySelectorAll('form[data-loading]').forEach(form => {
  form.addEventListener('submit', () => {
    const btn = form.querySelector('[type="submit"]');
    if (btn) {
      btn.classList.add('btn-loading');
      btn.disabled = true;
      btn.innerHTML = '<span class="spinner"></span> Processing...';
    }
  });
});

// ── Network Status Monitoring ─────────────
let isOnline = navigator.onLine;
function updateNetworkStatus() {
  const wasOnline = isOnline;
  isOnline = navigator.onLine;

  if (wasOnline && !isOnline) {
    showNetworkNotification('You are now offline. Some features may not work.', 'warning');
  } else if (!wasOnline && isOnline) {
    showNetworkNotification('You are back online!', 'success');
  }
}

function showNetworkNotification(message, type) {
  const notification = document.createElement('div');
  notification.className = `flash flash-${type}`;
  notification.innerHTML = `
    <span>${message}</span>
    <button class="flash-close" onclick="this.parentElement.remove()">×</button>
  `;
  document.querySelector('.flash-container')?.appendChild(notification) ||
  document.body.insertBefore(notification, document.body.firstChild);

  setTimeout(() => notification.remove(), 5000);
}

window.addEventListener('online', updateNetworkStatus);
window.addEventListener('offline', updateNetworkStatus);

// ── Mobile Viewport Height Fix ────────────
function setVH() {
  const vh = window.innerHeight * 0.01;
  document.documentElement.style.setProperty('--vh', `${vh}px`);
}

setVH();
window.addEventListener('resize', setVH);
window.addEventListener('orientationchange', () => {
  setTimeout(setVH, 100);
});

// ── OTP digit boxes ───────────────────────
const otpInputs = document.querySelectorAll('.otp-digit');
const otpHidden = document.getElementById('otp_hidden');

if (otpInputs.length) {
  otpInputs.forEach((input, idx) => {
    // Accept only digits
    input.addEventListener('keydown', (e) => {
      if (!/^\d$/.test(e.key) && !['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
      }
    });

    input.addEventListener('input', () => {
      const val = input.value.replace(/\D/g, '');
      input.value = val.slice(-1); // keep only last digit entered
      input.classList.toggle('filled', input.value !== '');

      if (input.value && idx < otpInputs.length - 1) {
        otpInputs[idx + 1].focus();
      }
      syncHidden();
    });
  otpInputs.forEach((input, idx) => {
    // Accept only digits
    input.addEventListener('keydown', (e) => {
      if (!/^\d$/.test(e.key) && !['Backspace', 'Delete', 'Tab', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
      }
    });

    input.addEventListener('input', () => {
      const val = input.value.replace(/\D/g, '');
      input.value = val.slice(-1); // keep only last digit entered
      input.classList.toggle('filled', input.value !== '');

      if (input.value && idx < otpInputs.length - 1) {
        otpInputs[idx + 1].focus();
      }
      syncHidden();
    });

    input.addEventListener('keyup', (e) => {
      if (e.key === 'Backspace' && !input.value && idx > 0) {
        otpInputs[idx - 1].focus();
        otpInputs[idx - 1].value = '';
        otpInputs[idx - 1].classList.remove('filled');
        syncHidden();
      }
    });

    // Arrow key navigation
    input.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft' && idx > 0) otpInputs[idx - 1].focus();
      if (e.key === 'ArrowRight' && idx < otpInputs.length - 1) otpInputs[idx + 1].focus();
    });
  });

  // Paste support — distribute digits across boxes
  otpInputs[0].addEventListener('paste', (e) => {
    e.preventDefault();
    const pasted = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
    pasted.slice(0, 6).split('').forEach((ch, i) => {
      if (otpInputs[i]) {
        otpInputs[i].value = ch;
        otpInputs[i].classList.add('filled');
      }
    });
    const next = Math.min(pasted.length, otpInputs.length - 1);
    otpInputs[next].focus();
    syncHidden();
  });

  function syncHidden() {
    if (otpHidden) {
      otpHidden.value = Array.from(otpInputs).map(i => i.value).join('');
    }
  }

  // Focus first box on load
  otpInputs[0].focus();

  // Shake all boxes on error (if server returned error, inputs start empty)
  const hasError = document.querySelector('.flash-danger');
  if (hasError) {
    otpInputs.forEach(i => {
      i.classList.add('error');
      setTimeout(() => i.classList.remove('error'), 500);
    });
  }
}

// ── OTP countdown timer ───────────────────
const countdownEl = document.getElementById('otp-countdown-time');
if (countdownEl) {
  const expirySeconds = parseInt(countdownEl.dataset.seconds || '600', 10);
  let remaining = expirySeconds;

  const wrapper = countdownEl.closest('.otp-countdown');

  function tick() {
    if (remaining <= 0) {
      countdownEl.textContent = '00:00';
      if (wrapper) wrapper.classList.add('urgent');
      // Redirect back to identify page after expiry
      const redirectUrl = countdownEl.dataset.redirect;
      if (redirectUrl) {
        setTimeout(() => { window.location.href = redirectUrl; }, 1500);
      }
      return;
    }
    const m = String(Math.floor(remaining / 60)).padStart(2, '0');
    const s = String(remaining % 60).padStart(2, '0');
    countdownEl.textContent = `${m}:${s}`;

    if (remaining <= 120 && wrapper) wrapper.classList.add('urgent');
    remaining--;
    setTimeout(tick, 1000);
  }
  tick();
}

// ── Live election countdown ───────────────
document.querySelectorAll('.election-countdown').forEach(el => {
  const endTime = new Date(el.dataset.end).getTime();

  function updateTimer() {
    const diff = endTime - Date.now();
    const timer = el.closest('.election-timer');
    if (diff <= 0) {
      el.textContent = 'Closed';
      if (timer) timer.classList.add('urgent');
      return;
    }
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    const s = Math.floor((diff % 60000) / 1000);

    if (h > 0) {
      el.textContent = `${h}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s remaining`;
    } else if (m > 0) {
      el.textContent = `${m}m ${String(s).padStart(2,'0')}s remaining`;
      if (m < 10 && timer) timer.classList.add('urgent');
    } else {
      el.textContent = `${s}s remaining`;
      if (timer) timer.classList.add('urgent');
    }
    setTimeout(updateTimer, 1000);
  }
  updateTimer();
});

// ── Candidate selection highlight ─────────
document.querySelectorAll('.candidate-option').forEach(option => {
  const radio = option.querySelector('input[type="radio"]');
  if (radio) {
    radio.addEventListener('change', () => {
      document.querySelectorAll(`input[name="${radio.name}"]`).forEach(r => {
        r.closest('.candidate-option').classList.remove('selected');
      });
      option.classList.add('selected');
    });
  }
});

// ── Ballot submission guard ────────────────
const ballotForm = document.getElementById('ballotForm');
if (ballotForm) {
  ballotForm.addEventListener('submit', (e) => {
    const positions = ballotForm.querySelectorAll('[data-position]');
    let allSelected = true;
    positions.forEach(pos => {
      const selected = ballotForm.querySelector(`input[name="position_${pos.dataset.position}"]:checked`);
      if (!selected) {
        allSelected = false;
        pos.style.borderLeftColor = '#c0392b';
      } else {
        pos.style.borderLeftColor = '#FFD700';
      }
    });

    if (!allSelected) {
      e.preventDefault();
      window.scrollTo({ top: 0, behavior: 'smooth' });
      const warn = document.getElementById('ballot-warning');
      if (warn) warn.style.display = 'flex';
    } else {
      const btn = ballotForm.querySelector('[type="submit"]');
      if (btn) btn.classList.add('btn-loading');
    }
  });
}

// ── Copy receipt code ──────────────────────
const copyBtn = document.getElementById('copyReceiptBtn');
if (copyBtn) {
  copyBtn.addEventListener('click', () => {
    const code = document.getElementById('receiptCode')?.textContent?.trim();
    if (!code) return;

    function onCopied() {
      copyBtn.textContent = '✓ Copied!';
      copyBtn.style.background = 'var(--success)';
      copyBtn.style.color = '#fff';
      copyBtn.style.borderColor = 'var(--success)';
      setTimeout(() => {
        copyBtn.textContent = 'Copy Code';
        copyBtn.style.background = '';
        copyBtn.style.color = '';
        copyBtn.style.borderColor = '';
      }, 2500);
    }

    // Modern clipboard API (HTTPS / localhost)
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(code).then(onCopied).catch(() => fallbackCopy(code));
    } else {
      fallbackCopy(code);
    }

    function fallbackCopy(text) {
      // Works on http:// (local network) where clipboard API is blocked
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;';
      document.body.appendChild(ta);
      ta.focus(); ta.select();
      try { document.execCommand('copy'); onCopied(); } catch (e) { /* silent */ }
      document.body.removeChild(ta);
    }
  });
}

// ── PWA Install Banner ─────────────────────
let deferredPrompt;
const pwaBanner    = document.getElementById('pwa-banner');
const pwaInstallBtn = document.getElementById('pwaInstallBtn');
const pwaDismissBtn = document.getElementById('pwaDismissBtn');

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  if (pwaBanner && !localStorage.getItem('pwa-dismissed')) pwaBanner.classList.add('show');
});

if (pwaInstallBtn) {
  pwaInstallBtn.addEventListener('click', async () => {
    if (deferredPrompt) { deferredPrompt.prompt(); deferredPrompt = null; }
    if (pwaBanner) pwaBanner.classList.remove('show');
  });
}

if (pwaDismissBtn) {
  pwaDismissBtn.addEventListener('click', () => {
    if (pwaBanner) pwaBanner.classList.remove('show');
    localStorage.setItem('pwa-dismissed', '1');
  });
}

// ── Register Service Worker ────────────────
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/js/sw.js')
      .catch(() => {});
  });
}
