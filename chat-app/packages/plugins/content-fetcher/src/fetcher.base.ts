// packages/plugins/content-fetcher/fetcher.base.ts
export interface ContentItem {
  id: string;
  title: string;
  content: string;          // 纯文本正文
  summary?: string;         // AI 摘要（后续填充）
  source: string;           // 来源标识，如 'hackernews'
  sourceUrl: string;
  author?: string;
  publishedAt: number;      // Unix 时间戳（毫秒）
  tags: string[];
  heat: number;             // 热度值
  rawHtml?: string;         // 原始 HTML（可选，用于回查）
}
export interface FetchOptions {
  limit?: number;           // 最大条数
  since?: number;           // 起始时间戳
  keyword?: string;         // 关键词过滤
  deep?: boolean;           // 是否深度抓取正文
}
export interface ContentFetcher {
  readonly id: string;      // 唯一标识，如 'rss', 'web', 'newsapi'
  readonly name: string;    // 显示名称
  fetch(options: FetchOptions): Promise<ContentItem[]>;
  healthCheck(): Promise<boolean>;
}
