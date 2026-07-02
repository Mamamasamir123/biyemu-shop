(function () {
  var root = document.querySelector('[data-alerts-api]');
  if (!root) return;

  var apiUrl = root.getAttribute('data-alerts-api');
  if (!apiUrl) return;

  var STORAGE_KEY = 'biyemu_sound_enabled';
  var POLL_MS = 8000;
  var audioCtx = null;
  var unlocked = false;
  var ready = false;
  var last = {
    notifications: 0,
    chat: 0,
    connections: 0,
  };

  window.BiyeMuAlerts = {
    isSoundEnabled: function () {
      return localStorage.getItem(STORAGE_KEY) !== '0';
    },
    setSoundEnabled: function (on) {
      localStorage.setItem(STORAGE_KEY, on ? '1' : '0');
      var toggle = document.getElementById('alertSoundToggle');
      if (toggle) toggle.checked = !!on;
    },
    playMessage: function () {
      if (!this.isSoundEnabled()) return;
      playChime([660, 880], 0.12);
      vibrate([80, 40, 80]);
    },
    playNotification: function () {
      if (!this.isSoundEnabled()) return;
      playChime([523, 659, 784], 0.1);
      vibrate([120, 60, 120, 60, 160]);
    },
  };

  function ensureAudio() {
    if (audioCtx) return audioCtx;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return null;
    audioCtx = new Ctx();
    return audioCtx;
  }

  function unlockAudio() {
    if (unlocked) return;
    var ctx = ensureAudio();
    if (!ctx) return;
    if (ctx.state === 'suspended') {
      ctx.resume().then(function () {
        unlocked = true;
      }).catch(function () {});
    } else {
      unlocked = true;
    }
  }

  function playChime(freqs, gap) {
    var ctx = ensureAudio();
    if (!ctx || !window.BiyeMuAlerts.isSoundEnabled()) return;
    if (ctx.state === 'suspended') {
      ctx.resume().catch(function () {});
    }
    var start = ctx.currentTime;
    freqs.forEach(function (freq, i) {
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, start + i * gap);
      gain.gain.exponentialRampToValueAtTime(0.22, start + i * gap + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + i * gap + 0.18);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start + i * gap);
      osc.stop(start + i * gap + 0.2);
    });
  }

  function vibrate(pattern) {
    if (navigator.vibrate) {
      try { navigator.vibrate(pattern); } catch (e) {}
    }
  }

  function setBadge(kind, count) {
    document.querySelectorAll('[data-alert-badge="' + kind + '"]').forEach(function (el) {
      if (count > 0) {
        el.textContent = String(count);
        el.hidden = false;
        el.style.display = '';
      } else {
        el.textContent = '';
        el.hidden = true;
      }
    });
  }

  function updateBadges(data) {
    setBadge('notifications', data.unread_notifications || 0);
    setBadge('chat', (data.unread_chat || 0) + (data.pending_connections || 0));
  }

  function handleData(data) {
    if (!data) return;
    updateBadges(data);

    if (!ready) {
      last.notifications = data.unread_notifications || 0;
      last.chat = data.unread_chat || 0;
      last.connections = data.pending_connections || 0;
      ready = true;
      return;
    }

    var notifIncreased = (data.unread_notifications || 0) > last.notifications;
    var chatIncreased = (data.unread_chat || 0) > last.chat;
    var connIncreased = (data.pending_connections || 0) > last.connections;

    if (notifIncreased) {
      window.BiyeMuAlerts.playNotification();
    } else if (chatIncreased || connIncreased) {
      window.BiyeMuAlerts.playMessage();
    }

    last.notifications = data.unread_notifications || 0;
    last.chat = data.unread_chat || 0;
    last.connections = data.pending_connections || 0;
  }

  function poll() {
    fetch(apiUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(handleData)
      .catch(function () {});
  }

  document.addEventListener('click', unlockAudio, { once: true, passive: true });
  document.addEventListener('touchstart', unlockAudio, { once: true, passive: true });
  document.addEventListener('keydown', unlockAudio, { once: true });

  var toggle = document.getElementById('alertSoundToggle');
  if (toggle) {
    toggle.checked = window.BiyeMuAlerts.isSoundEnabled();
    toggle.addEventListener('change', function () {
      window.BiyeMuAlerts.setSoundEnabled(toggle.checked);
      if (toggle.checked) unlockAudio();
    });
  }

  poll();
  setInterval(poll, POLL_MS);
})();