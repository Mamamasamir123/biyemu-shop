function initApprovalList(listId) {
  var root = document.querySelector('[data-approval-list="' + listId + '"]');
  if (!root) return;

  var searchInput = document.querySelector('[data-search-for="' + listId + '"]');
  var selectAll = document.querySelector('[data-select-all-for="' + listId + '"]');
  var countEl = document.querySelector('[data-count-for="' + listId + '"]');
  var cards = Array.prototype.slice.call(root.querySelectorAll('[data-row]'));
  var bulkForms = Array.prototype.slice.call(
    document.querySelectorAll('[data-bulk-form-for="' + listId + '"]')
  );
  var bulkBtns = Array.prototype.slice.call(
    document.querySelectorAll('[data-bulk-btn-for="' + listId + '"]')
  );

  function visibleCards() {
    return cards.filter(function (card) {
      return !card.hidden;
    });
  }

  function updateCount() {
    if (!countEl) return;
    var shown = visibleCards().length;
    countEl.textContent = shown + ' / ' + cards.length;
  }

  function filterCards() {
    var q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    cards.forEach(function (card) {
      var text = (card.getAttribute('data-search') || card.textContent || '').toLowerCase();
      card.hidden = q && text.indexOf(q) === -1;
    });
    updateCount();
    syncSelectAll();
    updateBulkBtns();
  }

  function rowChecks() {
    return visibleCards().map(function (card) {
      return card.querySelector('.approval-row-check');
    }).filter(Boolean);
  }

  function selectedChecks() {
    return rowChecks().filter(function (cb) {
      return cb.checked && !cb.disabled;
    });
  }

  function updateBulkBtns() {
    var n = selectedChecks().length;
    bulkBtns.forEach(function (btn) {
      var label = btn.getAttribute('data-label') || btn.textContent;
      btn.disabled = n === 0;
      btn.textContent = label + (n ? ' (' + n + ')' : '');
    });
  }

  function syncSelectAll() {
    if (!selectAll) return;
    var checks = rowChecks().filter(function (cb) {
      return !cb.disabled;
    });
    if (!checks.length) {
      selectAll.checked = false;
      selectAll.indeterminate = false;
      return;
    }
    var checked = checks.filter(function (cb) {
      return cb.checked;
    }).length;
    selectAll.checked = checked === checks.length;
    selectAll.indeterminate = checked > 0 && checked < checks.length;
  }

  if (searchInput) {
    searchInput.addEventListener('input', filterCards);
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      rowChecks().forEach(function (cb) {
        if (!cb.disabled) cb.checked = selectAll.checked;
      });
      updateBulkBtns();
    });
  }

  root.addEventListener('change', function (e) {
    if (e.target && e.target.classList.contains('approval-row-check')) {
      syncSelectAll();
      updateBulkBtns();
    }
  });

  bulkForms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
      var selected = selectedChecks();
      if (!selected.length) {
        e.preventDefault();
        return;
      }
      var msg = form.getAttribute('data-confirm') || '';
      if (msg && !window.confirm(msg)) {
        e.preventDefault();
        return;
      }
      form.querySelectorAll('input.bulk-req-id').forEach(function (el) {
        el.remove();
      });
      selected.forEach(function (cb) {
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'req_ids';
        input.value = cb.value;
        input.className = 'bulk-req-id';
        form.appendChild(input);
      });
    });
  });

  filterCards();
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-approval-list]').forEach(function (el) {
    initApprovalList(el.getAttribute('data-approval-list'));
  });
});