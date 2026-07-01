function initShopDataTable(tableId) {
  var table = document.getElementById(tableId);
  if (!table) return;

  var searchInput = document.querySelector('[data-search-for="' + tableId + '"]');
  var selectAll = document.querySelector('[data-select-all-for="' + tableId + '"]');
  var bulkBtn = document.querySelector('[data-bulk-btn-for="' + tableId + '"]');
  var bulkForm = document.querySelector('[data-bulk-form-for="' + tableId + '"]');
  var countEl = document.querySelector('[data-count-for="' + tableId + '"]');
  var rows = Array.prototype.slice.call(table.querySelectorAll('tbody tr[data-row]'));

  function visibleRows() {
    return rows.filter(function (row) {
      return !row.hidden && row.style.display !== 'none';
    });
  }

  function updateCount() {
    if (!countEl) return;
    var shown = visibleRows().length;
    countEl.textContent = shown + ' / ' + rows.length;
  }

  function filterRows() {
    var q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    rows.forEach(function (row) {
      var text = (row.getAttribute('data-search') || row.textContent || '').toLowerCase();
      row.hidden = q && text.indexOf(q) === -1;
    });
    updateCount();
    syncSelectAll();
    updateBulkBtn();
  }

  function rowChecks() {
    return visibleRows().map(function (row) {
      return row.querySelector('.shop-row-check');
    }).filter(Boolean);
  }

  function selectedChecks() {
    return rowChecks().filter(function (cb) {
      return cb.checked && !cb.disabled;
    });
  }

  function updateBulkBtn() {
    if (!bulkBtn) return;
    var n = selectedChecks().length;
    bulkBtn.disabled = n === 0;
    bulkBtn.textContent = bulkBtn.getAttribute('data-label') + (n ? ' (' + n + ')' : '');
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
    searchInput.addEventListener('input', filterRows);
  }

  if (selectAll) {
    selectAll.addEventListener('change', function () {
      rowChecks().forEach(function (cb) {
        if (!cb.disabled) cb.checked = selectAll.checked;
      });
      updateBulkBtn();
    });
  }

  table.addEventListener('change', function (e) {
    if (e.target && e.target.classList.contains('shop-row-check')) {
      syncSelectAll();
      updateBulkBtn();
    }
  });

  if (bulkForm) {
    bulkForm.addEventListener('submit', function (e) {
      var selected = selectedChecks();
      if (!selected.length) {
        e.preventDefault();
        return;
      }
      var msg = bulkForm.getAttribute('data-confirm') || '';
      if (msg && !window.confirm(msg)) {
        e.preventDefault();
        return;
      }
      bulkForm.querySelectorAll('input.bulk-item-id').forEach(function (el) {
        el.remove();
      });
      selected.forEach(function (cb) {
        var input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'item_ids';
        input.value = cb.value;
        input.className = 'bulk-item-id';
        bulkForm.appendChild(input);
      });
    });
  }

  filterRows();
}

document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-shop-table]').forEach(function (el) {
    initShopDataTable(el.getAttribute('data-shop-table'));
  });
});