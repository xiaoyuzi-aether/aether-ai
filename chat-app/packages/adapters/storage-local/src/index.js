const DEFAULT_KEY = 'aether_chats_v1';

export function makeStorageLocal({ key = DEFAULT_KEY } = {}) {
  return {
    async list() {
      try { return JSON.parse(localStorage.getItem(key)) || []; }
      catch { return []; }
    },
    async save(chat) {
      const all = await this.list();
      const i = all.findIndex(c => c.id === chat.id);
      if (i >= 0) all[i] = chat; else all.unshift(chat);
      localStorage.setItem(key, JSON.stringify(all));
    },
    async remove(id) {
      const all = await this.list();
      localStorage.setItem(key, JSON.stringify(all.filter(c => c.id !== id)));
    },
  };
}

export function createLocalChatRepository() {
  return makeStorageLocal();
}
