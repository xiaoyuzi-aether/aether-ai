import { makeSendMessageStream } from '@aether/core';

const $ = (id) => document.getElementById(id);

export function mountApp({ kernel, chatRepo, createChat, sendMessage, aiGateway }) {
  const { bus } = kernel;
  const renderMarkdown = kernel.registry.resolve('markdown:renderer', 'default');
  const sendStream = makeSendMessageStream({ chatRepo, aiGateway, bus });

  const els = {
    sidebar: $('sidebar'), backdrop: $('backdrop'),
    welcome: $('welcome'), chatWrap: $('chatWrap'),
    chat: $('chat'), chatInner: $('chatInner'), chatList: $('chatList'),
    input1: $('input1'), input2: $('input2'),
    send1: $('send1'), send2: $('send2'),
    warn: $('warn'), chips1: $('chips1'), chips2: $('chips2'),
    batchBar: $('batchBar'), batchCount: $('batchCount'),
  };

  const state = { chats: [], currentId: null, attached: [], multi: { mode: false, selected: [] } };

  (async () => {
    state.chats = await chatRepo.list();
    renderList();
    if (state.chats.length) await selectChat(state.chats[0].id);
    else await newChat();
  })();

  const toggleSidebar = () => {
    if (window.innerWidth <= 768) {
      els.sidebar.classList.toggle('mobile-open');
      els.backdrop.classList.toggle('show', els.sidebar.classList.contains('mobile-open'));
    } else {
      els.sidebar.classList.toggle('collapsed');
    }
  };
  $('topbarToggle').addEventListener('click', toggleSidebar);
  $('mobileMenu').addEventListener('click', toggleSidebar);
  $('sidebarToggleIcon').addEventListener('click', toggleSidebar);
  els.backdrop.addEventListener('click', toggleSidebar);

  async function newChat() {
    const c = createChat();
    state.chats.unshift(c);
    await chatRepo.save(c);
    state.currentId = c.id;
    els.chatInner.innerHTML = '';
    els.welcome.style.display = 'flex';
    els.chatWrap.style.display = 'none';
    renderList();
    els.input1.focus();
    return c;
  }
  $('newChatBtn').addEventListener('click', newChat);
  $('mobileNew').addEventListener('click', newChat);

  async function selectChat(id) {
    state.currentId = id;
    const c = state.chats.find(x => x.id === id);
    if (!c) return;
    renderList();
    if (!c.messages.length) {
      els.welcome.style.display = 'flex'; els.chatWrap.style.display = 'none';
      els.chatInner.innerHTML = ''; return;
    }
    els.welcome.style.display = 'none'; els.chatWrap.style.display = 'flex';
    els.chatInner.innerHTML = '';
    for (const m of c.messages) renderMessage(m);
    els.chat.scrollTop = els.chat.scrollHeight;
  }

  function renderMessage(m) {
    const div = document.createElement('div');
    div.className = 'msg ' + m.role;
    const av = m.role === 'user' ? '你' : 'A';
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    if (m.role === 'user') bubble.textContent = m.content;
    else bubble.innerHTML = renderMarkdown(m.content);
    div.innerHTML = `<div class="avatar">${av}</div>`;
    div.appendChild(bubble);
    els.chatInner.appendChild(div);
    return div;
  }
  function renderTyping() {
    const div = document.createElement('div');
    div.className = 'msg assistant';
    div.innerHTML = `<div class="avatar">A</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
    els.chatInner.appendChild(div);
    els.chat.scrollTop = els.chat.scrollHeight;
    return div;
  }

  function bindInput(inp, btn) {
    inp.addEventListener('input', () => {
      btn.classList.toggle('ready', !!inp.value.trim() || state.attached.length > 0);
      inp.style.height = 'auto';
      inp.style.height = Math.min(inp.scrollHeight, 160) + 'px';
    });
    inp.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onSubmit(inp.value, inp); }
    });
    btn.addEventListener('click', () => onSubmit(inp.value, inp));
  }
  bindInput(els.input1, els.send1);
  bindInput(els.input2, els.send2);

  async function onSubmit(text, source) {
    text = (text || '').trim();
    if (!text && !state.attached.length) return;
    let current = state.chats.find(c => c.id === state.currentId);
    if (!current) current = await newChat();
    const payload = { text, attachments: [] };
    bus.emit('ui:send:consume', { payload });
    els.welcome.style.display = 'none'; els.chatWrap.style.display = 'flex';
    const displayText = text || `（上传了 ${payload.attachments.length} 个文件）`;
    source.value = ''; source.dispatchEvent(new Event('input'));

    // 流式：先放一个空 AI 气泡，逐字填充
    const aiDiv = document.createElement('div');
    aiDiv.className = 'msg assistant';
    const aiBubble = document.createElement('div');
    aiBubble.className = 'bubble';
    aiBubble.innerHTML = '<span class="typing"><span></span><span></span><span></span></span>';
    aiDiv.innerHTML = '<div class="avatar">A</div>';
    aiDiv.appendChild(aiBubble);
    els.chatInner.appendChild(aiDiv);

    let full = '';
    try {
      await sendStream(current, displayText, payload.attachments, (delta, fullText) => {
        full = fullText;
        aiBubble.innerHTML = renderMarkdown(full);
        els.chat.scrollTop = els.chat.scrollHeight;
      });
    } catch (e) {
      els.warn.style.display = 'block';
      aiBubble.innerHTML = '⚠️ 无法连接后端。';
    }
    els.chat.scrollTop = els.chat.scrollHeight;
    els.input2.focus();
    renderList();
  }

  $('attachBtn1').addEventListener('click', () => bus.emit('ui:attach:pick'));
  $('attachBtn2').addEventListener('click', () => bus.emit('ui:attach:pick'));
  document.querySelectorAll('.feature-btn').forEach(b => b.addEventListener('click', () => b.classList.toggle('active')));

  function renderList() {
    els.chatList.innerHTML = '';
    els.batchBar.classList.toggle('show', state.multi.mode);
    els.batchCount.textContent = '已选 ' + state.multi.selected.length;
    const now = new Date();
    const pinned = state.chats.filter(c => c.pinned);
    const rest = state.chats.filter(c => !c.pinned);
    const isSameDay = (a, b) => a.getFullYear()===b.getFullYear() && a.getMonth()===b.getMonth() && a.getDate()===b.getDate();
    const draw = (label, items) => {
      if (!items.length) return;
      const lab = document.createElement('div');
      lab.className = 'group-title'; lab.textContent = label;
      els.chatList.appendChild(lab);
      items.forEach(c => els.chatList.appendChild(buildItem(c)));
    };
    if (pinned.length) draw('置顶', pinned);
    draw('今天', rest.filter(c => isSameDay(new Date(c.updatedAt), now)));
    draw('昨天', rest.filter(c => isSameDay(new Date(c.updatedAt), new Date(now - 86400000))));
    draw('7 天内', rest.filter(c => now - new Date(c.updatedAt) < 7 * 86400000));
    draw('更早', rest.filter(c => now - new Date(c.updatedAt) >= 7 * 86400000));
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }
  function buildItem(c) {
    const item = document.createElement('div');
    item.className = 'history-item' + (c.id === state.currentId ? ' active' : '');
    const isSel = state.multi.selected.includes(c.id);
    const chk = state.multi.mode ? `<input type="checkbox" class="chk" ${isSel ? 'checked' : ''}>` : '';
    const pin = c.pinned ? '<span class="pin">📌</span>' : '';
    item.innerHTML = `${chk}<span class="t">${pin}${escapeHtml(c.title)}</span><button class="menu">⋯</button>`;
    item.onclick = (e) => {
      if (state.multi.mode) { bus.emit('ui:multi:toggle', { id: c.id }); return; }
      selectChat(c.id);
    };
    item.querySelector('.menu').onclick = (e) => {
      e.stopPropagation();
      if (state.multi.mode) { bus.emit('ui:multi:toggle', { id: c.id }); return; }
      const r = e.currentTarget.getBoundingClientRect();
      openCtxMenu(c.id, Math.min(r.right - 170, window.innerWidth - 180), r.bottom + 4);
    };
    return item;
  }

  let ctxEl = null;
  const closeCtxMenu = () => { if (ctxEl) { ctxEl.remove(); ctxEl = null; } document.removeEventListener('click', closeCtxMenu); };
  function openCtxMenu(id, x, y) {
    closeCtxMenu();
    const c = state.chats.find(t => t.id === id);
    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.innerHTML = `
      <button data-a="rename">✏️ 重命名</button>
      <button data-a="pin">📌 ${c?.pinned ? '取消置顶' : '置顶'}</button>
      <button data-a="share">🔗 分享</button>
      <button data-a="multi">☑️ 多选</button>
      <button data-a="del" class="danger">🗑 删除</button>`;
    menu.style.left = x + 'px'; menu.style.top = y + 'px';
    menu.addEventListener('click', async e => {
      const b = e.target.closest('button'); if (!b) return;
      const a = b.dataset.a; closeCtxMenu();
      if (a === 'rename') {
        const name = prompt('重命名对话：', c.title);
        if (name && name.trim()) { c.title = name.trim(); await chatRepo.save(c); renderList(); }
      } else if (a === 'pin') {
        c.pinned = !c.pinned; c.updatedAt = Date.now();
        await chatRepo.save(c); renderList();
      } else if (a === 'share') {
        const text = c.messages.map(m => (m.role === 'user' ? '你：' : 'AETHER：') + m.content).join('\n\n');
        try { await navigator.clipboard.writeText(text); alert('对话已复制到剪贴板'); }
        catch { prompt('复制：', text); }
      } else if (a === 'multi') {
        bus.emit('ui:multi:enter');
      } else if (a === 'del') {
        if (!confirm('删除这条对话？')) return;
        await chatRepo.remove(c.id);
        state.chats = state.chats.filter(x => x.id !== c.id);
        if (state.currentId === c.id) {
          state.currentId = null;
          els.welcome.style.display = 'flex'; els.chatWrap.style.display = 'none';
          els.chatInner.innerHTML = '';
          if (state.chats.length) await selectChat(state.chats[0].id);
        }
        renderList();
      }
    });
    document.body.appendChild(menu); ctxEl = menu;
    setTimeout(() => document.addEventListener('click', closeCtxMenu), 0);
  }

  $('batchCancel').addEventListener('click', () => bus.emit('ui:multi:exit'));
  $('batchDelete').addEventListener('click', async () => {
    if (!state.multi.selected.length) return;
    if (!confirm(`删除选中的 ${state.multi.selected.length} 条对话？`)) return;
    bus.emit('ui:multi:delete', { chatRepo });
  });

  $('userProfile').addEventListener('click', e => {
    e.stopPropagation(); closeCtxMenu();
    const r = e.currentTarget.getBoundingClientRect();
    const menu = document.createElement('div');
    menu.className = 'ctx-menu';
    menu.innerHTML = `
      <button data-a="app">📱 手机下载 APP</button>
      <button data-a="settings">⚙️ 系统设置</button>
      <button data-a="help">💬 帮助与反馈</button>
      <button data-a="logout" class="danger">🚪 退出登录</button>`;
    menu.style.left = '16px'; menu.style.top = (r.top - 220) + 'px';
    menu.addEventListener('click', async ev => {
      const b = ev.target.closest('button'); if (!b) return;
      const a = b.dataset.a; closeCtxMenu();
      if (a === 'app') alert('APP 即将上线，敬请期待。');
      else if (a === 'settings') alert('设置：后端地址 = http://localhost:8001');
      else if (a === 'help') alert('反馈邮箱：2100393959@qq.com');
      else if (a === 'logout') {
        if (confirm('退出登录？将清空本地对话记录。')) {
          localStorage.removeItem('aether_chats_v1'); location.reload();
        }
      }
    });
    document.body.appendChild(menu); ctxEl = menu;
    setTimeout(() => document.addEventListener('click', closeCtxMenu), 0);
  });

  bus.on('chat:message:added', ({ message }) => { if (message.role === 'user') renderMessage(message); });
  bus.on('chat:ai:error', () => { els.warn.style.display = 'block'; });
  bus.on('attach:changed', ({ files }) => {
    state.attached = files; renderChips(files);
    els.send1.classList.toggle('ready', !!els.input1.value.trim() || files.length > 0);
    els.send2.classList.toggle('ready', !!els.input2.value.trim() || files.length > 0);
  });
  bus.on('attach:skipped', ({ items }) => { alert('部分文件被跳过：\n' + items.join('\n')); });
  bus.on('multi:changed', ({ mode, selected }) => {
    state.multi.mode = mode; state.multi.selected = selected; renderList();
  });
  bus.on('multi:deleted', async ({ ids }) => {
    state.chats = state.chats.filter(c => !ids.includes(c.id));
    if (ids.includes(state.currentId)) {
      state.currentId = null;
      els.welcome.style.display = 'flex'; els.chatWrap.style.display = 'none';
      els.chatInner.innerHTML = '';
      if (state.chats.length) await selectChat(state.chats[0].id);
    }
    renderList();
  });

  function fmtSize(b) {
    if (b < 1024) return b + 'B';
    if (b < 1024 * 1024) return (b / 1024).toFixed(1) + 'KB';
    return (b / 1024 / 1024).toFixed(1) + 'MB';
  }
  function renderChips(files) {
    [els.chips1, els.chips2].forEach(box => {
      box.classList.toggle('show', files.length > 0);
      box.innerHTML = files.map((f, i) =>
        `<span class="attach-chip"><span>📎</span><span class="fn">${escapeHtml(f.name)}</span><span style="opacity:.6">${fmtSize(f.size)}</span><span class="rm" data-i="${i}">×</span></span>`
      ).join('');
      box.querySelectorAll('.rm').forEach(x => x.onclick = () => bus.emit('ui:attach:remove', { index: +x.dataset.i }));
    });
  }

  return { state, newChat, selectChat };
}
