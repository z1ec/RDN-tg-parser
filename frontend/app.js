'use strict';

const API = '';  // Относительный путь — FastAPI раздаёт фронт

// ── Состояние приложения ────────────────────────────────────────────────────
const state = {
  token: localStorage.getItem('token') || null,
  login: localStorage.getItem('login') || '',
  chats: [],
  groups: [],
  filterChatId: null,    // id из нашей БД
  filterGroupId: null,
  filterLabel: null,
  pollTimers: {},        // таймеры опроса статуса чатов
};

// ── Утилиты запросов ─────────────────────────────────────────────────────────

async function apiFetch(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...opts.headers };
  if (state.token) headers['Authorization'] = `Bearer ${state.token}`;
  const res = await fetch(API + path, { ...opts, headers });
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

async function apiUpload(path, formData) {
  const res = await fetch(API + path, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${state.token}` },
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

// ── Экраны ───────────────────────────────────────────────────────────────────

function showAuthScreen() {
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('main-screen').classList.add('hidden');
}

function showMainScreen() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('main-screen').classList.remove('hidden');
  document.getElementById('user-label').textContent = `👤 ${state.login}`;
  loadAll();
}

// ── Аутентификация ────────────────────────────────────────────────────────────

let authMode = 'login';

document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    authMode = btn.dataset.tab;
    document.getElementById('auth-submit').textContent =
      authMode === 'login' ? 'Войти' : 'Зарегистрироваться';
    hideAuthError();
  });
});

function showAuthError(msg) {
  const el = document.getElementById('auth-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}
function hideAuthError() {
  document.getElementById('auth-error').classList.add('hidden');
}

document.getElementById('auth-submit').addEventListener('click', async () => {
  const login = document.getElementById('auth-login').value.trim();
  const password = document.getElementById('auth-pass').value;
  if (!login || !password) return showAuthError('Введите логин и пароль');
  hideAuthError();
  try {
    const path = authMode === 'login' ? '/auth/login' : '/auth/register';
    const data = await apiFetch(path, {
      method: 'POST',
      body: JSON.stringify({ login, password }),
    });
    state.token = data.access_token;
    state.login = login;
    localStorage.setItem('token', state.token);
    localStorage.setItem('login', state.login);
    showMainScreen();
  } catch (e) {
    showAuthError(e.message);
  }
});

// Enter в полях входа
['auth-login', 'auth-pass'].forEach(id => {
  document.getElementById(id).addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('auth-submit').click();
  });
});

document.getElementById('logout-btn').addEventListener('click', () => {
  state.token = null;
  state.login = '';
  localStorage.removeItem('token');
  localStorage.removeItem('login');
  Object.values(state.pollTimers).forEach(clearInterval);
  state.pollTimers = {};
  showAuthScreen();
});

// ── Загрузка данных ───────────────────────────────────────────────────────────

async function loadAll() {
  await Promise.all([loadChats(), loadGroups()]);
}

async function loadChats() {
  try {
    state.chats = await apiFetch('/chats') || [];
    renderChats();
    // Запускаем опрос для чатов в обработке
    state.chats.forEach(c => {
      if (c.status === 'processing' || c.status === 'pending') startPolling(c.id);
    });
  } catch (e) { console.error('loadChats:', e); }
}

async function loadGroups() {
  try {
    state.groups = await apiFetch('/groups') || [];
    renderGroups();
  } catch (e) { console.error('loadGroups:', e); }
}

// ── Рендер сайдбара ───────────────────────────────────────────────────────────

function renderChats() {
  const ul = document.getElementById('chat-list');
  ul.innerHTML = '';
  if (!state.chats.length) {
    ul.innerHTML = '<li style="color:var(--text-dim);font-size:.8rem;padding:.3rem .6rem">Нет чатов</li>';
    return;
  }
  state.chats.forEach(chat => {
    const li = document.createElement('li');
    if (state.filterChatId === chat.id) li.classList.add('active');

    const badgeClass = {
      ready: 'badge-ready', processing: 'badge-processing',
      error: 'badge-error', pending: 'badge-pending',
    }[chat.status] || 'badge-pending';

    const badgeLabel = {
      ready: '✓', processing: '⟳', error: '✕', pending: '…',
    }[chat.status] || '?';

    const groupTags = chat.groups.length
      ? chat.groups.map(g => `<span class="chat-group-tag">${escHtml(g)}</span>`).join('')
      : '';

    li.innerHTML = `
      <span class="item-name" title="${escHtml(chat.title)}">${escHtml(chat.title)}</span>
      <span class="item-badge ${badgeClass}">${badgeLabel}</span>
      <button class="btn-icon" data-manage-groups="${chat.id}" title="Группы">⊞</button>
      <button class="btn-danger" data-del-chat="${chat.id}" title="Удалить">✕</button>
    `;
    if (groupTags) {
      const tagsRow = document.createElement('div');
      tagsRow.className = 'chat-group-tags';
      tagsRow.innerHTML = groupTags;
      li.appendChild(tagsRow);
    }

    li.addEventListener('click', (e) => {
      if (e.target.closest('[data-del-chat]') || e.target.closest('[data-manage-groups]')) return;
      setFilter('chat', chat.id, chat.title);
    });
    li.querySelector('[data-del-chat]').addEventListener('click', e => {
      e.stopPropagation();
      confirmDeleteChat(chat.id, chat.title);
    });
    li.querySelector('[data-manage-groups]').addEventListener('click', e => {
      e.stopPropagation();
      openGroupsModal(chat);
    });
    ul.appendChild(li);
  });
}

function renderGroups() {
  const ul = document.getElementById('group-list');
  ul.innerHTML = '';
  if (!state.groups.length) {
    ul.innerHTML = '<li style="color:var(--text-dim);font-size:.8rem;padding:.3rem .6rem">Нет групп</li>';
    return;
  }
  state.groups.forEach(group => {
    const li = document.createElement('li');
    if (state.filterGroupId === group.id) li.classList.add('active');
    li.innerHTML = `
      <span class="item-name" title="${escHtml(group.name)}">${escHtml(group.name)}</span>
      <span class="item-badge badge-pending">${group.chat_ids.length}</span>
      <button class="btn-danger" data-del-group="${group.id}" title="Удалить">✕</button>
    `;
    li.addEventListener('click', e => {
      if (e.target.closest('[data-del-group]')) return;
      setFilter('group', group.id, group.name);
    });
    li.querySelector('[data-del-group]').addEventListener('click', e => {
      e.stopPropagation();
      confirmDeleteGroup(group.id, group.name);
    });
    ul.appendChild(li);
  });
}

// ── Фильтр (срез поиска) ─────────────────────────────────────────────────────

function setFilter(type, id, label) {
  state.filterChatId = type === 'chat' ? id : null;
  state.filterGroupId = type === 'group' ? id : null;
  state.filterLabel = label;
  document.getElementById('scope-label').textContent =
    type === 'chat' ? `Чат: ${label}` : `Группа: ${label}`;
  document.getElementById('clear-scope-btn').classList.remove('hidden');
  renderChats();
  renderGroups();
}

document.getElementById('clear-scope-btn').addEventListener('click', () => {
  state.filterChatId = null;
  state.filterGroupId = null;
  state.filterLabel = null;
  document.getElementById('scope-label').textContent = 'Поиск по всем чатам';
  document.getElementById('clear-scope-btn').classList.add('hidden');
  renderChats();
  renderGroups();
});

// ── Загрузка файла ────────────────────────────────────────────────────────────

document.getElementById('upload-btn').addEventListener('click', () => {
  document.getElementById('file-input').click();
});

document.getElementById('file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  e.target.value = '';

  const statusEl = document.getElementById('upload-status');
  statusEl.classList.remove('hidden');
  statusEl.textContent = `⟳ Загружаем ${file.name}…`;

  try {
    const fd = new FormData();
    fd.append('file', file);
    const data = await apiUpload('/chats/upload', fd);
    statusEl.textContent = `✓ Принят (ID ${data.chat_id}), обрабатывается…`;
    await loadChats();
    startPolling(data.chat_id);
  } catch (e) {
    statusEl.textContent = `✕ Ошибка: ${e.message}`;
  }
});

function startPolling(chatId) {
  if (state.pollTimers[chatId]) return;
  state.pollTimers[chatId] = setInterval(async () => {
    try {
      const s = await apiFetch(`/chats/${chatId}/status`);
      if (s.status === 'ready' || s.status === 'error') {
        clearInterval(state.pollTimers[chatId]);
        delete state.pollTimers[chatId];
        await loadChats();
        const statusEl = document.getElementById('upload-status');
        if (s.status === 'ready') {
          statusEl.textContent = `✓ Чат готов (${s.chunk_count} чанков)`;
        } else {
          statusEl.textContent = `✕ Ошибка: ${s.error_msg}`;
        }
      }
    } catch (e) { /* сеть временно недоступна */ }
  }, 3000);
}

// ── Создание группы ───────────────────────────────────────────────────────────

document.getElementById('new-group-btn').addEventListener('click', () => {
  openModal('Создать группу', `
    <input id="m-group-name" type="text" placeholder="Название группы" />
  `, async () => {
    const name = document.getElementById('m-group-name').value.trim();
    if (!name) return false;
    await apiFetch('/groups', { method: 'POST', body: JSON.stringify({ name }) });
    await loadGroups();
    return true;
  });
});

// ── Удаление ──────────────────────────────────────────────────────────────────

function confirmDeleteChat(chatId, title) {
  openModal(`Удалить чат?`, `
    <p>«${escHtml(title)}» будет удалён вместе со всеми векторами. Отменить нельзя.</p>
  `, async () => {
    await apiFetch(`/chats/${chatId}`, { method: 'DELETE' });
    if (state.filterChatId === chatId) {
      state.filterChatId = null;
      document.getElementById('scope-label').textContent = 'Поиск по всем чатам';
      document.getElementById('clear-scope-btn').classList.add('hidden');
    }
    await loadAll();
    return true;
  });
}

function confirmDeleteGroup(groupId, name) {
  openModal(`Удалить группу?`, `
    <p>Группа «${escHtml(name)}» будет удалена. Чаты и их данные останутся.</p>
  `, async () => {
    await apiFetch(`/groups/${groupId}`, { method: 'DELETE' });
    if (state.filterGroupId === groupId) {
      state.filterGroupId = null;
      document.getElementById('scope-label').textContent = 'Поиск по всем чатам';
      document.getElementById('clear-scope-btn').classList.add('hidden');
    }
    await loadAll();
    return true;
  });
}

// ── Управление группами чата ─────────────────────────────────────────────────

function openGroupsModal(chat) {
  if (!state.groups.length) {
    openModal('Нет групп', '<p>Сначала создай группу кнопкой «+ Создать» в секции Группы.</p>', () => true);
    return;
  }

  const rows = state.groups.map(group => {
    const inGroup = chat.groups.includes(group.name);
    return `
      <div class="group-toggle-row">
        <label class="group-toggle-label">
          <input type="checkbox" data-group-id="${group.id}" ${inGroup ? 'checked' : ''} />
          ${escHtml(group.name)}
        </label>
      </div>`;
  }).join('');

  openModal(
    `Группы для «${chat.title}»`,
    `<div class="group-toggles">${rows}</div>`,
    async () => {
      const boxes = document.querySelectorAll('#modal-body input[type=checkbox]');
      for (const box of boxes) {
        const groupId = Number(box.dataset.groupId);
        const group = state.groups.find(g => g.id === groupId);
        const wasIn = chat.groups.includes(group.name);
        const nowIn = box.checked;
        if (nowIn && !wasIn) {
          await apiFetch(`/groups/${groupId}/chats/${chat.id}`, { method: 'POST' });
        } else if (!nowIn && wasIn) {
          await apiFetch(`/groups/${groupId}/chats/${chat.id}`, { method: 'DELETE' });
        }
      }
      await loadAll();
      return true;
    }
  );
}

// ── Модалка ───────────────────────────────────────────────────────────────────

let _modalCallback = null;

function openModal(title, bodyHtml, onOk) {
  document.getElementById('modal-title').textContent = title;
  document.getElementById('modal-body').innerHTML = bodyHtml;
  document.getElementById('modal-overlay').classList.remove('hidden');
  _modalCallback = onOk;
  // Фокус на первый инпут
  setTimeout(() => {
    const inp = document.querySelector('#modal-body input, #modal-body select');
    if (inp) inp.focus();
  }, 50);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  _modalCallback = null;
}

document.getElementById('modal-cancel').addEventListener('click', closeModal);
document.getElementById('modal-ok').addEventListener('click', async () => {
  if (_modalCallback) {
    try {
      const ok = await _modalCallback();
      if (ok !== false) closeModal();
    } catch (e) {
      alert(`Ошибка: ${e.message}`);
    }
  }
});

document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});

// ── Вопрос-ответ ──────────────────────────────────────────────────────────────

const qaMessages = document.getElementById('qa-messages');

function addMessage(cls, html) {
  const div = document.createElement('div');
  div.className = `msg ${cls}`;
  div.innerHTML = html;
  qaMessages.appendChild(div);
  qaMessages.scrollTop = qaMessages.scrollHeight;
  return div;
}

document.getElementById('qa-send-btn').addEventListener('click', sendQuestion);
document.getElementById('qa-input').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuestion(); }
});

async function sendQuestion() {
  const input = document.getElementById('qa-input');
  const question = input.value.trim();
  if (!question) return;
  input.value = '';

  addMessage('msg-user', escHtml(question));
  const thinking = addMessage('msg-thinking', '⟳ Думаю…');

  const body = { question };
  if (state.filterChatId) body.chat_id = state.filterChatId;
  if (state.filterGroupId) body.group_id = state.filterGroupId;

  try {
    const data = await apiFetch('/qa', { method: 'POST', body: JSON.stringify(body) });
    thinking.remove();

    let sourcesHtml = '';
    if (data.sources && data.sources.length) {
      const items = data.sources.map((s, i) => {
        const d1 = s.date_start ? s.date_start.slice(0, 10) : '';
        const d2 = s.date_end   ? s.date_end.slice(0, 10)   : '';
        const dateRange = d1 === d2 ? d1 : `${d1} — ${d2}`;
        const score = Math.round(s.score * 100);

        // Ищем название чата по tg_chat_id
        const chat = state.chats.find(c => String(c.tg_chat_id) === String(s.chat_id));
        const chatTitle = chat ? escHtml(chat.title) : `Чат ${escHtml(s.chat_id)}`;

        // Участники — разбиваем строку по запятой
        const participants = s.participants
          ? s.participants.split(',').map(p => escHtml(p.trim())).join(', ')
          : '—';

        return `
          <details class="source-card">
            <summary class="source-summary">
              <span class="source-num">${i + 1}</span>
              <span class="source-chat-name">${chatTitle}</span>
              <span class="source-date">${dateRange}</span>
              <span class="source-score-badge">${score}%</span>
            </summary>
            <div class="source-details">
              <div class="source-row"><span class="source-label">Чат</span><span>${chatTitle}</span></div>
              <div class="source-row"><span class="source-label">Период</span><span>${dateRange}</span></div>
              <div class="source-row"><span class="source-label">Участники</span><span>${participants}</span></div>
              <div class="source-row"><span class="source-label">Релевантность</span><span>${score}%</span></div>
            </div>
          </details>`;
      }).join('');

      sourcesHtml = `
        <details class="sources-block">
          <summary class="sources-summary">Источники (${data.sources.length})</summary>
          <div class="sources-list">${items}</div>
        </details>`;
    }

    addMessage('msg-answer', `<div class="answer-text">${md2html(data.answer)}</div>${sourcesHtml}`);
  } catch (e) {
    thinking.remove();
    addMessage('msg-error', `Ошибка: ${escHtml(e.message)}`);
  }
}

// ── Вспомогательные функции ───────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Минимальный markdown → html (только **bold** и переносы строк)
function md2html(str) {
  return escHtml(str)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ── Инициализация ─────────────────────────────────────────────────────────────

if (state.token) {
  showMainScreen();
} else {
  showAuthScreen();
}
