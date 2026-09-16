export function MultiSelectPlugin() {
  let mode = false;
  const selected = new Set();
  const emit = (bus) => bus.emit('multi:changed', { mode, selected: [...selected] });

  return {
    name: 'multi-select',
    setup(kernel) {
      kernel.bus.on('ui:multi:enter', () => { mode = true; selected.clear(); emit(kernel.bus); });
      kernel.bus.on('ui:multi:exit', () => { mode = false; selected.clear(); emit(kernel.bus); });
      kernel.bus.on('ui:multi:toggle', ({ id }) => {
        selected.has(id) ? selected.delete(id) : selected.add(id);
        emit(kernel.bus);
      });
      kernel.bus.on('ui:multi:delete', async ({ chatRepo }) => {
        const ids = [...selected];
        for (const id of ids) await chatRepo.remove(id);
        kernel.bus.emit('multi:deleted', { ids });
        selected.clear();
        emit(kernel.bus);
      });
    },
  };
}
