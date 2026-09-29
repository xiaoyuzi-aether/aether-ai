// packages/plugins/content-fetcher/index.ts
import type { Kernel } from '@aether/kernel';
import { RssFetcher } from './fetcher.rss';
import { WebFetcher } from './fetcher.web';
export default function install(kernel: Kernel) {
  const rss = new RssFetcher();
  const web = new WebFetcher();
  // 注册到插槽，kernel 按 id 解析
  kernel.defineSlot('content:fetcher');
  kernel.register('content:fetcher', rss.id, rss);
  kernel.register('content:fetcher', web.id, web);
  // 注册命令：供 UI 或 Agent 调用
  kernel.on('command:content:fetch', async (payload: {
    fetcherId?: string; options?: any;
  }) => {
    const ids = payload.fetcherId
      ? [payload.fetcherId]
      : kernel.list('content:fetcher');
    const all: any[] = [];
    for (const id of ids) {
      const fetcher = kernel.resolve('content:fetcher', id) as any;
      if (!fetcher) continue;
      const items = await fetcher.fetch(payload.options || {});
      all.push(...items);
    }
    // 通过事件总线通知 UI 和处理层
    kernel.emit('content:fetched', { items: all, count: all.length });
    return all;
  });
  // 健康检查定时器
  kernel.once('kernel:started', () => {
    setInterval(async () => {
      for (const id of kernel.list('content:fetcher')) {
        const f = kernel.resolve('content:fetcher', id) as any;
        const ok = await f.healthCheck();
        kernel.emit('content:fetcher:health', { id, ok });
      }
    }, 60_000);
  });
}
