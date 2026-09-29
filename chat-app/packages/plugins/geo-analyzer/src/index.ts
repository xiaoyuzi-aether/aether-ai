// packages/plugins/geo-analyzer/index.ts
import type { Kernel } from '@aether/kernel';
import { KeywordExtractor } from './keyword-extract';
import { BrandProbe } from './brand-probe';
import { GeoReporter } from './report';
export default function install(kernel: Kernel) {
  const extractor = new KeywordExtractor();
  const probe = new BrandProbe();
  const reporter = new GeoReporter();
  kernel.defineSlot('geo:analyzer');
  kernel.on('command:geo:run', async (payload: {
    brand: string;
    industry: string;
    competitors?: string[];
    locale?: string;
  }) => {
    const { brand, industry, competitors = [], locale } = payload;
    kernel.emit('geo:progress', { stage: 'keywords', message: '正在提取关键词...' });
    const keywords = await extractor.extract(brand, industry, locale);
    kernel.emit('geo:progress', {
      stage: 'probing',
      message: `正在探测 ${keywords.length} 个关键词...`,
      total: keywords.length,
    });
    const probes = await probe.probe(
      brand,
      keywords.map((k) => k.keyword),
      competitors
    );
    kernel.emit('geo:progress', { stage: 'report', message: '正在生成报告...' });
    const report = reporter.generate(brand, probes, keywords);
    kernel.emit('geo:report:ready', report);
    return report;
  });
  // 提供导出命令
  kernel.on('command:geo:export', (report: any, format: 'json' | 'markdown') => {
    if (format === 'json') {
      return JSON.stringify(report, null, 2);
    }
    return toMarkdown(report);
  });
}

function toMarkdown(report: any): string {
  const lines: string[] = [
    `# GEO 可见度报告 — ${report.brand}`,
    '',
    `生成时间：${new Date(report.generatedAt).toLocaleString()}`,
    `总探测次数：${report.totalProbes}`,
    `品牌提及率：**${report.mentionRate}%**`,
    `平均提及位置：第 ${report.avgMentionPosition} 段`,
    '',
    '## 竞品排名',
    '',
    '| 竞品 | 被提及次数 |',
    '|------|-----------|',
    ...report.topCompetitors.map((c: any) => `| ${c.name} | ${c.mentionCount} |`),
    '',
    '## 关键词详情',
    '',
    '| 关键词 | 是否提及 | 位置 | 情感 | 竞品 |',
    '|--------|---------|------|------|------|',
    ...report.keywordDetails.map((k: any) =>
      `| ${k.keyword} | ${k.mentioned ? '✅' : '❌'} | ${k.position} | ${k.sentiment} | ${k.competitors.join(', ')} |`
    ),
  ];
  return lines.join('\n');
}
