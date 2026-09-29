// packages/plugins/content-pipeline/pipeline.ts
import type { ContentItem } from '../content-fetcher/src/fetcher.base';

export interface ProcessedItem extends ContentItem {
  simhash: string;          // 64 位 SimHash 指纹
  embedding?: number[];     // 语义向量（384 维）
  importance: number;       // 重要性评分 0-100
  category: string;         // 分类标签
}
export interface ContentProcessor {
  readonly stage: 'filter' | 'dedup' | 'summarize' | 'rank';
  process(items: ProcessedItem[]): Promise<ProcessedItem[]>;
}

const STAGE_ORDER: Record<string, number> = {
  filter: 0, dedup: 1, summarize: 2, rank: 3,
};

export class ContentPipeline {
  private stages: ContentProcessor[] = [];
  register(stage: ContentProcessor) {
    this.stages.push(stage);
    this.stages.sort((a, b) => STAGE_ORDER[a.stage] - STAGE_ORDER[b.stage]);
  }
  async run(items: ProcessedItem[]): Promise<ProcessedItem[]> {
    let current = items;
    for (const stage of this.stages) {
      const before = current.length;
      current = await stage.process(current);
      console.log(`[Pipeline] ${stage.stage}: ${before} → ${current.length}`);
    }
    return current;
  }
}
