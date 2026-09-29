-- AETHER GEO 插件：内容表（PostgreSQL + pgvector）
-- 用法：在已安装 pgvector 扩展的库上执行
--   CREATE EXTENSION IF NOT EXISTS vector;

-- 内容表
CREATE TABLE IF NOT EXISTS content_items (
  id          TEXT PRIMARY KEY,
  title       TEXT NOT NULL,
  content     TEXT,
  summary     TEXT,
  source      TEXT,
  source_url  TEXT,
  published_at BIGINT,
  tags        TEXT[],
  heat        INTEGER DEFAULT 0,
  simhash     TEXT,
  embedding   vector(384),
  created_at  TIMESTAMP DEFAULT NOW()
);

-- 向量索引（HNSW，余弦距离）
CREATE INDEX IF NOT EXISTS idx_content_embedding ON content_items
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 200);

-- 按时间倒序列出
CREATE INDEX IF NOT EXISTS idx_content_published ON content_items (published_at DESC);

-- 去重查询示例：找与给定向量相似的内容
-- SELECT id, title, 1 - (embedding <=> $1) AS similarity
-- FROM content_items
-- WHERE 1 - (embedding <=> $1) > 0.85
-- ORDER BY similarity DESC LIMIT 10;
