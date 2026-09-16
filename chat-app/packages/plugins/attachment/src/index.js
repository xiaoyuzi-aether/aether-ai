export function AttachmentPlugin({ fileStore }) {
  let attached = [];
  return {
    name: 'attachment',
    setup(kernel) {
      const emit = () => kernel.bus.emit('attach:changed', { files: attached.slice() });

      kernel.bus.on('ui:attach:pick', async () => {
        const { files, skipped } = await fileStore.pick();
        attached = attached.concat(files);
        if (skipped?.length) kernel.bus.emit('attach:skipped', { items: skipped });
        emit();
      });

      kernel.bus.on('ui:attach:remove', ({ index }) => {
        attached.splice(index, 1);
        emit();
      });

      kernel.bus.on('ui:attach:clear', () => {
        attached = [];
        emit();
      });

      kernel.bus.on('ui:send:consume', ({ payload }) => {
        payload.attachments = attached.slice();
        attached = [];
        emit();
      });
    },
  };
}
