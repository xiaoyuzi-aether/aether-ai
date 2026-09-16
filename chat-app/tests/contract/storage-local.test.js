import { describe, it, expect } from 'vitest';
import { makeStorageLocal } from '@aether/adapter-storage-local';

function runChatRepositoryContract(name, createRepo) {
  describe(`${name} chat-repository contract`, () => {
    it('list returns array', async () => {
      const repo = createRepo();
      const list = await repo.list();
      expect(Array.isArray(list)).toBe(true);
    });
    it('save upserts by id', async () => {
      const repo = createRepo();
      await repo.save({ id: 'a', title: 'A', messages: [] });
      await repo.save({ id: 'a', title: 'A2', messages: [] });
      const list = await repo.list();
      const found = list.filter(c => c.id === 'a');
      expect(found).toHaveLength(1);
      expect(found[0].title).toBe('A2');
    });
    it('remove deletes by id', async () => {
      const repo = createRepo();
      await repo.save({ id: 'a', title: 'A', messages: [] });
      await repo.remove('a');
      const list = await repo.list();
      expect(list.find(c => c.id === 'a')).toBeUndefined();
    });
  });
}

runChatRepositoryContract('storage-local', () =>
  makeStorageLocal({ key: `aether_test_${Date.now()}_${Math.random()}` }),
);
