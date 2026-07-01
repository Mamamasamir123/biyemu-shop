(function () {
  var STORY_DURATION = 5000;
  var items = window.PROMO_STORY_ITEMS || [];
  if (!items.length) return;

  var viewer = document.getElementById('promoStoryViewer');
  var progressEl = document.getElementById('promoStoryProgress');
  var titleEl = document.getElementById('promoStoryViewerTitle');
  var slideA = document.getElementById('promoStorySlideA');
  var slideB = document.getElementById('promoStorySlideB');
  if (!viewer || !progressEl || !slideA || !slideB) return;

  var currentIndex = 0;
  var timerId = null;
  var rafId = null;
  var startedAt = 0;
  var activeSlide = slideA;
  var idleSlide = slideB;
  var isOpen = false;

  function buildProgressBars() {
    progressEl.innerHTML = '';
    items.forEach(function (_, i) {
      var bar = document.createElement('div');
      bar.className = 'promo-story-progress-item';
      bar.innerHTML = '<span class="promo-story-progress-fill"></span>';
      progressEl.appendChild(bar);
    });
  }

  function getFillEl(index) {
    var bars = progressEl.querySelectorAll('.promo-story-progress-fill');
    return bars[index] || null;
  }

  function resetProgress() {
    progressEl.querySelectorAll('.promo-story-progress-fill').forEach(function (el, i) {
      el.style.transition = 'none';
      el.style.width = i < currentIndex ? '100%' : '0%';
    });
  }

  function stopTimer() {
    if (timerId) { clearTimeout(timerId); timerId = null; }
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  }

  function startTimer() {
    stopTimer();
    startedAt = performance.now();
    var fill = getFillEl(currentIndex);
    if (!fill) return;
    fill.style.transition = 'none';
    fill.style.width = '0%';
    fill.offsetHeight;
    function tick(now) {
      if (!isOpen) return;
      var elapsed = now - startedAt;
      var pct = Math.min(100, (elapsed / STORY_DURATION) * 100);
      fill.style.width = pct + '%';
      if (elapsed >= STORY_DURATION) {
        window.promoStoryNext(false);
        return;
      }
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);
    timerId = setTimeout(function () {
      window.promoStoryNext(false);
    }, STORY_DURATION);
  }

  function renderSlide(el, item, animClass) {
    el.className = 'promo-story-slide' + (animClass ? ' ' + animClass : '');
    el.innerHTML =
      '<img src="' + item.image + '" alt="">' +
      '<div class="promo-story-slide-caption">' + escapeHtml(item.name) + '</div>';
  }

  function escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  function showStory(index, direction) {
    if (!items.length) return;
    if (index < 0) index = 0;
    if (index >= items.length) {
      closePromoStoryViewer();
      return;
    }
    var prevIndex = currentIndex;
    currentIndex = index;
    var item = items[currentIndex];
    titleEl.textContent = item.name;

    resetProgress();
    for (var i = 0; i < currentIndex; i++) {
      var done = getFillEl(i);
      if (done) done.style.width = '100%';
    }

    if (!activeSlide.querySelector('img')) {
      renderSlide(activeSlide, item, 'active');
      idleSlide.className = 'promo-story-slide';
      startTimer();
      return;
    }

    if (prevIndex === currentIndex) {
      renderSlide(activeSlide, item, 'active');
      startTimer();
      return;
    }

    var enterClass = direction === 'prev' ? 'enter-from-left' : 'enter-from-right';
    var leaveClass = direction === 'prev' ? 'leave-to-right' : 'leave-to-left';

    renderSlide(idleSlide, item, 'active ' + enterClass);
    if (activeSlide.querySelector('img')) {
      activeSlide.classList.add(leaveClass);
      activeSlide.classList.remove('active');
    }

    requestAnimationFrame(function () {
      idleSlide.classList.remove('enter-from-left', 'enter-from-right');
      if (activeSlide.classList.contains('leave-to-left') || activeSlide.classList.contains('leave-to-right')) {
        setTimeout(function () {
          activeSlide.className = 'promo-story-slide';
        }, 280);
      }
    });

    var tmp = activeSlide;
    activeSlide = idleSlide;
    idleSlide = tmp;

    startTimer();
  }

  window.openPromoStoryViewer = function (storyIndex) {
    if (!items.length) return;
    buildProgressBars();
    isOpen = true;
    viewer.hidden = false;
    viewer.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    slideA.className = 'promo-story-slide';
    slideB.className = 'promo-story-slide';
    activeSlide = slideA;
    idleSlide = slideB;
    currentIndex = -1;
    showStory(storyIndex || 0, 'next');
  };

  window.closePromoStoryViewer = function () {
    isOpen = false;
    stopTimer();
    viewer.hidden = true;
    viewer.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
  };

  window.promoStoryNext = function (manual) {
    if (!isOpen) return;
    stopTimer();
    var fill = getFillEl(currentIndex);
    if (fill) {
      fill.style.transition = 'width 0.15s linear';
      fill.style.width = '100%';
    }
    if (currentIndex >= items.length - 1) {
      setTimeout(closePromoStoryViewer, manual ? 120 : 80);
      return;
    }
    showStory(currentIndex + 1, 'next');
  };

  window.promoStoryPrev = function () {
    if (!isOpen) return;
    stopTimer();
    if (currentIndex <= 0) {
      resetProgress();
      startTimer();
      return;
    }
    showStory(currentIndex - 1, 'prev');
  };

  document.addEventListener('keydown', function (e) {
    if (!isOpen) return;
    if (e.key === 'Escape') closePromoStoryViewer();
    if (e.key === 'ArrowRight') promoStoryNext(true);
    if (e.key === 'ArrowLeft') promoStoryPrev();
  });
})();