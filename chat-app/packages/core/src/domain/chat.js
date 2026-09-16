export function createChat({ title = '新对话' } = {}) {
  return {
    id: 'c_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    title, messages: [], pinned: false,
    createdAt: Date.now(), updatedAt: Date.now(),
  };
}

export function appendMessage(chat, message) {
  chat.messages.push(message);
  chat.updatedAt = Date.now();
  if (chat.messages.filter(m => m.role === 'user').length === 1) {
    chat.title = (message.content || '附件').slice(0, 22);
  }
  return chat;
}
