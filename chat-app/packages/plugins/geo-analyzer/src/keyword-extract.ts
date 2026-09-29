// packages/plugins/geo-analyzer/keyword-extract.ts
export interface GeoKeyword {
  keyword: string;
  intent: 'informational' | 'commercial' | 'navigational';
  volume: number;       // 估算搜索量
  difficulty: number;   // 竞争难度 0-100
  relevance: number;    // 与品牌的相关度 0-100
}
export class KeywordExtractor {
  private backendUrl: string;
  constructor(backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001') {
    this.backendUrl = backendUrl;
  }
  async extract(brand: string, industry: string, locale = 'zh-CN'): Promise<GeoKeyword[]> {
    const prompt = `你是一个GEO关键词分析专家。品牌：${brand}，行业：${industry}，地区：${locale}。
请生成 15-20 个真实用户可能在 AI 搜索引擎（DeepSeek、豆包、ChatGPT）中输入的查询关键词。
要求：
- 关键词不能直接包含品牌名（品牌盲测）
- 覆盖 informational / commercial / navigational 三种意图
- 按预估搜索量从高到低排序
严格按 JSON 数组输出：
[{"keyword": "...", "intent": "informational", "volume": 5000, "difficulty": 30, "relevance": 90}]`;
    const resp = await fetch(`${this.backendUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        temperature: 0.3,
      }),
    });
    const data = await resp.json();
    const text = data.choices?.[0]?.message?.content || '';
    return this.parseJsonArray(text);
  }
  private parseJsonArray(text: string): GeoKeyword[] {
    const match = text.match(/\[[\s\S]*\]/);
    if (!match) return [];
    try { return JSON.parse(match[0]); } catch { return []; }
  }
}
