import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@aether/kernel': resolve(root, 'packages/kernel/src/index.js'),
      '@aether/core': resolve(root, 'packages/core/src/index.js'),
      '@aether/adapter-storage-local': resolve(root, 'packages/adapters/storage-local/src/index.js'),
      '@aether/adapter-ai-http': resolve(root, 'packages/adapters/ai-http/src/index.js'),
      '@aether/adapter-file-browser': resolve(root, 'packages/adapters/file-browser/src/index.js'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/**/*.test.js', 'packages/**/*.test.js'],
  },
});
