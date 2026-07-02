(function () {
  var shell = document.getElementById('staffChatShell');
  if (!shell) return;

  var searchInput = document.getElementById('chatContactSearch');
  var shopFilter = document.getElementById('chatShopFilter');
  var contacts = Array.prototype.slice.call(document.querySelectorAll('.chat-directory-item'));
  var messagesEl = document.getElementById('chatMessages');
  var partnerId = shell.getAttribute('data-partner-id') || '';
  var pollTemplate = shell.getAttribute('data-poll-url') || '';
  var labelSent = shell.getAttribute('data-label-sent') || 'Sent';
  var labelRead = shell.getAttribute('data-label-read') || 'Read';

  function filterContacts() {
    var q = searchInput ? searchInput.value.toLowerCase().trim() : '';
    var shop = shopFilter ? shopFilter.value : '';
    contacts.forEach(function (item) {
      var text = (item.getAttribute('data-search') || '').toLowerCase();
      var itemShop = item.getAttribute('data-shop-id') || '';
      var matchSearch = !q || text.indexOf(q) !== -1;
      var matchShop = !shop || itemShop === shop;
      item.style.display = matchSearch && matchShop ? '' : 'none';
    });
  }

  if (searchInput) searchInput.addEventListener('input', filterContacts);
  if (shopFilter) shopFilter.addEventListener('change', filterContacts);

  function scrollMessages() {
    if (!messagesEl) return;
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  scrollMessages();

  function updateReadStatus(bubble, msg) {
    if (!msg.mine) return;
    var status = bubble.querySelector('.chat-read-status');
    if (!status) {
      var meta = bubble.querySelector('.chat-bubble-meta');
      if (!meta) return;
      status = document.createElement('span');
      status.className = 'chat-read-status';
      meta.appendChild(status);
    }
    if (msg.read_at) {
      status.classList.add('is-read');
      status.textContent = '✓✓';
      status.title = labelRead;
      status.setAttribute('aria-label', labelRead);
    } else {
      status.classList.remove('is-read');
      status.textContent = '✓';
      status.title = labelSent;
      status.setAttribute('aria-label', labelSent);
    }
  }

  function createBubble(msg) {
    var bubble = document.createElement('div');
    bubble.className = 'chat-bubble ' + (msg.mine ? 'mine' : 'theirs');
    bubble.setAttribute('data-msg-id', msg.id);
    bubble.innerHTML = '<p></p><div class="chat-bubble-meta"><time></time></div>';
    bubble.querySelector('p').textContent = msg.body;
    bubble.querySelector('time').textContent = msg.created_at;
    if (msg.mine) {
      updateReadStatus(bubble, msg);
    }
    return bubble;
  }

  var knownIds = {};
  if (messagesEl) {
    messagesEl.querySelectorAll('[data-msg-id]').forEach(function (node) {
      knownIds[node.getAttribute('data-msg-id')] = true;
    });
  }

  function syncMessages(messages) {
    if (!messagesEl) return;
    var empty = document.getElementById('chatEmptyThread');
    if (empty && messages.length) empty.remove();

    messages.forEach(function (msg) {
      var bubble = messagesEl.querySelector('[data-msg-id="' + msg.id + '"]');
      if (!bubble) {
        messagesEl.appendChild(createBubble(msg));
        if (!msg.mine && !knownIds[msg.id]) {
          if (window.BiyeMuAlerts && window.BiyeMuAlerts.playMessage) {
            window.BiyeMuAlerts.playMessage();
          }
        }
        knownIds[msg.id] = true;
      } else if (msg.mine) {
        updateReadStatus(bubble, msg);
        knownIds[msg.id] = true;
      }
    });
    scrollMessages();
  }

  if (partnerId && pollTemplate) {
    var pollUrl = pollTemplate.replace('__ID__', partnerId);
    setInterval(function () {
      fetch(pollUrl, { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (data && data.messages) syncMessages(data.messages);
        })
        .catch(function () {});
    }, 5000);
  }

  var compose = document.getElementById('chatComposeForm');
  var input = document.getElementById('chatMessageInput');
  if (compose && input) {
    compose.addEventListener('submit', function () {
      if (!input.value.trim()) return;
    });
    input.focus();
  }
})();