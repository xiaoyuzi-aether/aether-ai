// packages/plugins/geo-analyzer/report.ts
import type { ProbeResult } from './brand-probe';
import type { GeoKeyword } from './keyword-extract';
export interface GeoReport {
  brand: string;
  generatedAt: number;
  totalProbes: number;
  mentionRate: number;              // 品牌被提及的查询比例
  avgMentionPosition: number;       // 平均提及位置
  sentimentBreakdown: Record<string, number>;
  keywordDetails: Array<{
    keyword: string;
    mentioned: boolean;
    position: number;
    sentiment: string;
    competitors: string[];
  }>;
  topCompetitors: Array<{ name: string; mentionCount: number }>;
}
export class GeoReporter {
  generate(brand: string, probes: ProbeResult[], keywords: GeoKeyword[]): GeoReport {
    const mentioned = probes.filter((p) => p.brandMentioned);
    const mentionRate = probes.length ? mentioned.length / probes.length : 0;
    const positions = mentioned.map((p) => p.mentionPosition).filter((p) => p > 0);
    const avgPosition = positions.length
      ? positions.reduce((a, b) => a + b, 0) / positions.length
      : -1;
    const sentimentBreakdown: Record<string, number> = {};
    for (const p of probes) {
      sentimentBreakdown[p.sentiment] = (sentimentBreakdown[p.sentiment] || 0) + 1;
    }
    // 竞品统计
    const compCount = new Map<string, number>();
    for (const p of probes) {
      for (const c of p.competitorsMentioned) {
        compCount.set(c, (compCount.get(c) || 0) + 1);
      }
    }
    const topCompetitors = [...compCount.entries()]
      .map(([name, mentionCount]) => ({ name, mentionCount }))
      .sort((a, b) => b.mentionCount - a.mentionCount)
      .slice(0, 10);
    // 按关键词聚合
    const kwMap = new Map<string, ProbeResult[]>();
    for (const p of probes) {
      if (!kwMap.has(p.keyword)) kwMap.set(p.keyword, []);
      kwMap.get(p.keyword)!.push(p);
    }
    const keywordDetails = keywords.map((kw) => {
      const kProbes = kwMap.get(kw.keyword) || [];
      const kMentioned = kProbes.some((p) => p.brandMentioned);
      const first = kProbes.find((p) => p.brandMentioned);
      return {
        keyword: kw.keyword,
        mentioned: kMentioned,
        position: first?.mentionPosition ?? -1,
        sentiment: first?.sentiment ?? 'absent',
        competitors: [...new Set(kProbes.flatMap((p) => p.competitorsMentioned))],
      };
    });
    return {
      brand,
      generatedAt: Date.now(),
      totalProbes: probes.length,
      mentionRate: Math.round(mentionRate * 1000) / 10,
      avgMentionPosition: Math.round(avgPosition * 10) / 10,
      sentimentBreakdown,
      keywordDetails,
      topCompetitors,
    };
  }
}
