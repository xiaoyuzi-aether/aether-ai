// packages/plugins/geo-analyzer/brand-probe.ts
export interface ProbeResult {
  keyword: string;
  model: string;
  response: string;
  brandMentioned: boolean;
  mentionPosition: number;   // 品牌在回答中首次出现的位置（第几段）
  sentiment: 'positive' | 'neutral' | 'negative' | 'absent';
  competitorsMentioned: string[];
  timestamp: number;
}
export class BrandProbe {
  private backendUrl: string;
  private models: string[];
  constructor(
    backendUrl = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8001',
    models = ['deepseek-chat', 'deepseek-reasoner']
  ) {
    this.backendUrl = backendUrl;
    this.models = models;
  }
  async probe(
    brand: string,
    keywords: string[],
    competitors: string[] = []
  ): Promise<ProbeResult[]> {
    const results: ProbeResult[] = [];
    for (const keyword of keywords) {
      for (const model of this.models) {
        try {
          const response = await this.queryModel(model, keyword);
          results.push(this.analyze(brand, keyword, model, response, competitors));
        } catch (err) {
          console.warn(`[GEO] 探测失败 ${model}/${keyword}:`, err);
        }
        // 控制频率，避免触发限流
        await this.sleep(500);
      }
    }
    return results;
  }
  private async queryModel(model: string, query: string): Promise<string> {
    const resp = await fetch(`${this.backendUrl}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [
          { role: 'system', content: '你是一个知识助手，请用中文回答用户的问题，推荐相关产品和服务。' },
          { role: 'user', content: query },
        ],
        model,
        temperature: 0.7,
      }),
    });
    const data = await resp.json();
    return data.choices?.[0]?.message?.content || '';
  }
  private analyze(
    brand: string,
    keyword: string,
    model: string,
    response: string,
    competitors: string[]
  ): ProbeResult {
    const brandLower = brand.toLowerCase();
    const respLower = response.toLowerCase();
    const brandMentioned = respLower.includes(brandLower);
    // 计算品牌首次出现的段落位置
    const paragraphs = response.split(/\n{2,}/);
    const mentionParagraph = paragraphs.findIndex((p) =>
      p.toLowerCase().includes(brandLower)
    );
    // 情感判定（简化版：检查品牌附近的正面/负面词）
    let sentiment: ProbeResult['sentiment'] = 'absent';
    if (brandMentioned) {
      const positive = ['推荐', '优秀', '领先', '最佳', '值得', '可靠', '专业'];
      const negative = ['不推荐', '较差', '劣势', '不足', '问题', '风险'];
      const nearby = response.slice(
        Math.max(0, respLower.indexOf(brandLower) - 100),
        respLower.indexOf(brandLower) + brand.length + 100
      );
      if (negative.some((w) => nearby.includes(w))) sentiment = 'negative';
      else if (positive.some((w) => nearby.includes(w))) sentiment = 'positive';
      else sentiment = 'neutral';
    }
    const competitorsMentioned = competitors.filter((c) =>
      respLower.includes(c.toLowerCase())
    );
    return {
      keyword,
      model,
      response,
      brandMentioned,
      mentionPosition: mentionParagraph >= 0 ? mentionParagraph + 1 : -1,
      sentiment,
      competitorsMentioned,
      timestamp: Date.now(),
    };
  }
  private sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms));
  }
}
