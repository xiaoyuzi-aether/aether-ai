// packages/plugins/content-pipeline/summarize.ts
import type { ContentProcessor, ProcessedItem } from './pipeline';
const SUMMARIZE_PROMPT = `你是一个信息处理助手。对以下文章执行三个任务：
1. 判断文章是否与「科技、AI、互联网、金融」领域相关。不相关则 importance 设为 0。
2. 生成 2-3 句中文摘要，以及 1 句英文摘要。
3. 提取 3-5 个标签，并给出重要性评分（0-100）。
严格按以下 JSON 格式输出，不要输出其他内容：
{
  "relevant": true/false,
  "summary_zh": "中文摘要",
  "summary_en": "English summary",
  "tags": ["tag1", "tag2"],
  "importance": 85,
  "category": "AI/科技/金融/其他"
}`;
export class AiSummarizer implements ContentProcessor {
  readonly stage = 'summarize' as const;
  private backendUrl: string;
  constructor(backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001') {
    this.backendUrl = backendUrl;
  }
  async process(items: ProcessedItem[]): Promise<ProcessedItem[]> {
    const results: ProcessedItem[] = [];
    for (const item of items) {
      try {
        const parsed = await this.summarizeOne(item);
        if (!parsed || parsed.importance === 0) continue;
        item.summary = parsed.summary_zh;
        (item as any).summaryEn = parsed.summary_en;
        item.tags = [...new Set([...item.tags, ...parsed.tags])];
        item.heat = parsed.importance;
        (item as any).category = parsed.category;
        results.push(item);
      } catch (err) {
        console.warn(`[Summarize] 处理失败: ${item.title}`, err);
        // 摘要失败不丢弃，保留原始内容，heat 设为 50
        item.heat = 50;
        results.push(item);
      }
    }
    return results;
  }
  private async summarizeOne(item: ProcessedItem): Promise<any | null> {
    const userContent = `标题：${item.title}\n\n正文：${item.content.slice(0, 3000)}`;
    const resp = await fetch(`${this.backendUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [
          { role: 'system', content: SUMMARIZE_PROMPT },
          { role: 'user', content: userContent },
        ],
        temperature: 0.1,
        response_format: { type: 'json_object' },
      }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    const text = data.choices?.[0]?.message?.content || data.content || '';
    return this.extractJson(text);
  }
  private extractJson(text: string): any | null {
    // 尝试直接解析，失败则用正则提取 JSON 块
    try { return JSON.parse(text); } catch { /* ignore */ }
    const match = text.match(/\{[\s\S]*\}/);
    if (match) {
      try { return JSON.parse(match[0]); } catch { /* ignore */ }
    }
    return null;
  }
}
