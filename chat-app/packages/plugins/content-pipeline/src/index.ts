// packages/plugins/content-pipeline/index.ts
import type { Kernel } from '@aether/kernel';
import { ContentPipeline } from './pipeline';
import { SimHashDedup } from './dedup.simhash';
import { SemanticDedup } from './dedup.semantic';
import { AiSummarizer } from './summarize';
export default function install(kernel: Kernel) {
  const pipeline = new ContentPipeline();
  pipeline.register(new SimHashDedup());
  pipeline.register(new SemanticDedup());
  pipeline.register(new AiSummarizer());
  // 监听采集层事件，自动触发处理流水线
  kernel.on('content:fetched', async ({ items }) => {
    if (!items?.length) return;
    const processed = await pipeline.run(items);
    kernel.emit('content:processed', { items: processed, count: processed.length });
  });
  // 提供手动触发命令
  kernel.on('command:content:process', async (items: any[]) => {
    return pipeline.run(items);
  });
}
