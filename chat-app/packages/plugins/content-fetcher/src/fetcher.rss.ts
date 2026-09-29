// packages/plugins/content-fetcher/fetcher.rss.ts
import type { ContentFetcher, ContentItem, FetchOptions } from './fetcher.base';
/**
 * RSS/Atom 抓取代理：解析逻辑放后端 /fetch/rss（标准库解析，零依赖）。
 * 前端不直接跑 rss-parser，避免 Node 模块进浏览器 bundle、以及跨域 CORS 问题。
 */
export class RssFetcher implements ContentFetcher {
  readonly id = 'rss';
  readonly name = 'RSS/Atom 订阅源';
  private readonly backendUrl: string;
  constructor(backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001') {
    this.backendUrl = backendUrl;
  }
  async fetch(options: FetchOptions = {}): Promise<ContentItem[]> {
    const limit = options.limit ?? 20;
    try {
      const resp = await fetch(`${this.backendUrl}/fetch/rss`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          sources: (options as any).sources || undefined,
          limit,
        }),
      });
      if (!resp.ok) return [];
      const data = await resp.json();
      return (data.items || []) as ContentItem[];
    } catch (err) {
      console.warn('[RSS] 后端抓取失败:', err);
      return [];
    }
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
