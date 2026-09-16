export function createMessage({ role, content, attachments = [], meta = {} }) {
  if (!['user', 'assistant', 'system'].includes(role)) throw new Error('bad role');
  return Object.freeze({
    id: 'm_' + Math.random().toString(36).slice(2, 10),
    role, content, attachments, meta,
    createdAt: Date.now(),
  });
}
