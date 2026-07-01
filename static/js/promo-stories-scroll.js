(function () {
  function initRail(rail) {
    var scroll = rail.querySelector('[data-promo-scroll]');
    var prev = rail.querySelector('.promo-scroll-prev');
    var next = rail.querySelector('.promo-scroll-next');
    if (!scroll || !prev || !next) return;

    function updateArrows() {
      var max = scroll.scrollWidth - scroll.clientWidth;
      if (max <= 4) {
        prev.hidden = true;
        next.hidden = true;
        return;
      }
      prev.hidden = scroll.scrollLeft <= 4;
      next.hidden = scroll.scrollLeft >= max - 4;
    }

    function scrollPage(direction) {
      var amount = scroll.clientWidth * 0.9;
      scroll.scrollBy({ left: direction * amount, behavior: 'smooth' });
    }

    prev.addEventListener('click', function () { scrollPage(-1); });
    next.addEventListener('click', function () { scrollPage(1); });
    scroll.addEventListener('scroll', updateArrows, { passive: true });
    window.addEventListener('resize', updateArrows);
    updateArrows();
  }

  document.querySelectorAll('.promo-stories-rail.has-nav').forEach(initRail);
})();