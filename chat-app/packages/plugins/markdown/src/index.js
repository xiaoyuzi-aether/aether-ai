export function MarkdownPlugin({ renderer }) {
  return {
    name: 'markdown',
    setup(kernel) {
      kernel.registry.defineSlot('markdown:renderer', { version: '1.0.0' });
      kernel.registry.register('markdown:renderer', 'default', () => (text) =>
        typeof renderer === 'function' ? renderer(text || '') : String(text || '')
      );
    },
  };
}
