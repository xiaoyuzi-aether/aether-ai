export function createBrowserFileStore({ maxFiles = 50, maxSize = 100 * 1024 * 1024 } = {}) {
  return {
    async pick() {
      return new Promise(resolve => {
        const input = document.createElement('input');
        input.type = 'file';
        input.multiple = true;
        input.onchange = () => {
          const files = Array.from(input.files || []);
          const ok = [];
          const skipped = [];
          for (const f of files) {
            if (ok.length >= maxFiles) { skipped.push(`${f.name}(超出数量)`); continue; }
            if (f.size > maxSize) { skipped.push(`${f.name}(超出大小)`); continue; }
            ok.push({ name: f.name, size: f.size });
          }
          resolve({ files: ok, skipped });
        };
        input.click();
      });
    },
  };
}
