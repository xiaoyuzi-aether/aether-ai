// packages/plugins/content-pipeline/dedup.semantic.ts
import type { ContentProcessor, ProcessedItem } from './pipeline';
const SEMANTIC_THRESHOLD = 0.85;
const RECENT_WINDOW_MS = 24 * 3600 * 1000; // 24 小时内阈值放宽
export class SemanticDedup implements ContentProcessor {
  readonly stage = 'dedup' as const;
  private backendUrl: string;
  constructor(backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001') {
    this.backendUrl = backendUrl;
  }
  async process(items: ProcessedItem[]): Promise<ProcessedItem[]> {
    if (items.length === 0) return [];
    // 批量生成 embedding
    const texts = items.map((it) => `${it.title}\n${it.content.slice(0, 512)}`);
    const embeddings = await this.batchEmbed(texts);
    const kept: ProcessedItem[] = [];
    const keptEmbeddings: number[][] = [];
    const keptTimes: number[] = [];
    for (let i = 0; i < items.length; i++) {
      const emb = embeddings[i];
      if (!emb) { kept.push(items[i]); continue; }
      items[i].embedding = emb;
      const now = items[i].publishedAt;
      let isDup = false;
      for (let j = 0; j < keptEmbeddings.length; j++) {
        // 24 小时内的新文章降低阈值
        const threshold = (now - keptTimes[j] < RECENT_WINDOW_MS)
          ? SEMANTIC_THRESHOLD - 0.05
          : SEMANTIC_THRESHOLD;
        if (this.cosineSimilarity(emb, keptEmbeddings[j]) > threshold) {
          isDup = true;
          break;
        }
      }
      if (!isDup) {
        kept.push(items[i]);
        keptEmbeddings.push(emb);
        keptTimes.push(now);
      }
    }
    return kept;
  }
  /** 调用后端批量 embedding 接口 */
  private async batchEmbed(texts: string[]): Promise<(number[] | null)[]> {
    try {
      const resp = await fetch(`${this.backendUrl}/embed/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texts }),
      });
      if (!resp.ok) return texts.map(() => null);
      const data = await resp.json();
      return data.embeddings;
    } catch {
      return texts.map(() => null);
    }
  }
  private cosineSimilarity(a: number[], b: number[]): number {
    let dot = 0, na = 0, nb = 0;
    for (let i = 0; i < a.length; i++) {
      dot += a[i] * b[i];
      na += a[i] * a[i];
      nb += b[i] * b[i];
    }
    return dot / (Math.sqrt(na) * Math.sqrt(nb) + 1e-8);
  }
}
