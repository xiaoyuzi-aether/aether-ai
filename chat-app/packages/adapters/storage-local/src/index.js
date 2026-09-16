const KEY = 'aether_chats_v1';

export function createLocalChatRepository() {
  return {
    async list() {
      try { return JSON.parse(localStorage.getItem(KEY)) || []; }
      catch { return []; }
    },
    async save(chat) {
      const all = await this.list();
      const i = all.findIndex(c => c.id === chat.id);
      if (i >= 0) all[i] = chat; else all.unshift(chat);
      localStorage.setItem(KEY, JSON.stringify(all));
    },
    async remove(id) {
      const all = await this.list();
      localStorage.setItem(KEY, JSON.stringify(all.filter(c => c.id !== id)));
    },
  };
}
