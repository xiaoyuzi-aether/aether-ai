// packages/plugins/content-pipeline/dedup.simhash.ts
import type { ContentProcessor, ProcessedItem } from './pipeline';
const HAMMING_THRESHOLD = 3; // 64 位中最多 3 位不同
const HASH_BITS = 64;

/** FNV-1a 64 位（纯 JS BigInt 实现，替代 Node crypto/MD5，浏览器可用） */
function fnv1a64(str: string): bigint {
  const prime = 0x100000001b3n;
  let hash = 0xcbf29ce484222325n;
  for (let i = 0; i < str.length; i++) {
    hash ^= BigInt(str.charCodeAt(i));
    hash = (hash * prime) & 0xffffffffffffffffn;
  }
  return hash;
}
export class SimHashDedup implements ContentProcessor {
  readonly stage = 'dedup' as const;
  // 内存中维护已入库指纹（生产环境应改为 Redis 或数据库）
  private seenHashes: bigint[] = [];
  async process(items: ProcessedItem[]): Promise<ProcessedItem[]> {
    const kept: ProcessedItem[] = [];
    for (const item of items) {
      const fingerprint = this.computeSimHash(item.content);
      item.simhash = fingerprint.toString(16).padStart(16, '0');
      const isDuplicate = this.seenHashes.some(
        (h) => this.hammingDistance(h, fingerprint) <= HAMMING_THRESHOLD
      );
      if (!isDuplicate) {
        this.seenHashes.push(fingerprint);
        kept.push(item);
      }
    }
    // 限制内存指纹数量（生产环境用 Redis SET + 定期清理）
    if (this.seenHashes.length > 100_000) {
      this.seenHashes = this.seenHashes.slice(-50_000);
    }
    return kept;
  }
  /** 计算 64 位 SimHash 指纹 */
  private computeSimHash(text: string): bigint {
    const tokens = this.tokenize(text);
    const weights = new Map<string, number>();
    for (const token of tokens) {
      weights.set(token, (weights.get(token) || 0) + 1);
    }
    const vector = new Array<number>(HASH_BITS).fill(0);
    for (const [token, weight] of weights) {
      const hash = fnv1a64(token);
      for (let i = 0; i < HASH_BITS; i++) {
        const bit = (hash >> BigInt(HASH_BITS - 1 - i)) & 1n;
        vector[i] += bit ? weight : -weight;
      }
    }
    let fingerprint = 0n;
    for (let i = 0; i < HASH_BITS; i++) {
      if (vector[i] >= 0) fingerprint |= 1n << BigInt(HASH_BITS - 1 - i);
    }
    return fingerprint;
  }
  /** 计算两个指纹的汉明距离 */
  private hammingDistance(a: bigint, b: bigint): number {
    let xor = a ^ b;
    let count = 0;
    while (xor > 0n) {
      count += Number(xor & 1n);
      xor >>= 1n;
    }
    return count;
  }
  /** 简单分词：中文按字，英文按词 */
  private tokenize(text: string): string[] {
    return text
      .toLowerCase()
      .replace(/[^\u4e00-\u9fa5a-z0-9]/g, ' ')
      .split(/\s+/)
      .flatMap((seg) => {
        if (/[\u4e00-\u9fa5]/.test(seg)) {
          // 中文按 2-gram 切片
          const chars = [...seg];
          const grams: string[] = [];
          for (let i = 0; i < chars.length - 1; i++) {
            grams.push(chars[i] + chars[i + 1]);
          }
          return grams.length ? grams : chars;
        }
        return [seg];
      })
      .filter((t) => t.length > 0);
  }
}
