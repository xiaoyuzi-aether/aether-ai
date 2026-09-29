// packages/plugins/content-fetcher/fetcher.web.ts
import type { ContentFetcher, ContentItem, FetchOptions } from './fetcher.base';

/** 纯 JS 稳定哈希（djb2），替代 Node crypto，浏览器可用 */
function hashId(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h << 5) + h + s.charCodeAt(i)) | 0;
  return 'w_' + (h >>> 0).toString(36);
}
/**
 * 依赖后端 Playwright 服务（server.py 中新增 /fetch/body 端点）。
 * 前端不直接跑 Playwright，避免 bundle 体积膨胀和反爬暴露。
 */
export class WebFetcher implements ContentFetcher {
  readonly id = 'web';
  readonly name = '网页正文抓取';
  private readonly backendUrl: string;
  constructor(backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001') {
    this.backendUrl = backendUrl;
  }
  async fetch(options: FetchOptions = {}): Promise<ContentItem[]> {
    const urls: string[] = (options as any).urls || [];
    if (urls.length === 0) return [];
    const results: ContentItem[] = [];
    for (const url of urls.slice(0, options.limit ?? 10)) {
      try {
        const resp = await fetch(`${this.backendUrl}/fetch/body`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ url }),
        });
        if (!resp.ok) continue;
        const data = await resp.json();
        if (data.title && data.content) {
          results.push({
            id: hashId(url),
            title: data.title,
            content: data.content,
            source: new URL(url).hostname,
            sourceUrl: url,
            publishedAt: data.publishedAt || Date.now(),
            tags: data.tags || [],
            heat: 0,
          });
        }
      } catch (err) {
        console.warn(`[Web] 抓取失败 ${url}:`, err);
      }
    }
    return results;
  }
  async healthCheck(): Promise<boolean> {
    try {
      const resp = await fetch(`${this.backendUrl}/health`);
      return resp.ok;
    } catch {
      return false;
    }
  }
}
