"""AETHER 瀵硅瘽鍚庣浠ｇ悊 鈥?鍓嶇閫氳繃姝ゆ湇鍔¤皟 DeepSeek銆?
鐜鍙橀噺锛?  DEEPSEEK_API_KEY  鎴? OPENAI_API_KEY   锛堝繀濉級
  DEEPSEEK_BASE_URL   榛樿 https://api.deepseek.com
  DEEPSEEK_MODEL      榛樿 deepseek-chat
  DEEPSEEK_FALLBACK_MODEL  榛樿 deepseek-reasoner
  CORS_ORIGINS        閫楀彿鍒嗛殧鐧藉悕鍗曪紝榛樿 http://localhost:5173
  PORT                Railway 娉ㄥ叆
"""
from __future__ import annotations
import json
import os
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEFAULT_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
FALLBACK_MODEL = os.getenv("DEEPSEEK_FALLBACK_MODEL", "deepseek-reasoner")

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,https://xiaoyuzi-aether.github.io",
    ).split(",")
    if o.strip()
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

if not DEEPSEEK_API_KEY:
    print("[warn] DEEPSEEK_API_KEY not set 鈥?/chat will error")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }


async def _stream_deepseek(messages, model):
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_headers(),
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                text = await resp.aread()
                raise RuntimeError(
                    f"DeepSeek error {resp.status_code}: {text.decode(errors='ignore')[:500]}"
                )
            async for line in resp.aiter_lines():
                if not line:
                    continue
                yield line + "\n\n"


@app.get("/health")
async def health():
    return {
        "ok": True,
        "model": DEFAULT_MODEL,
        "key_set": bool(DEEPSEEK_API_KEY),
        "version": "1.2.1",
    }


@app.post("/chat")
async def chat(req: Request):
    body = await req.json()
    messages = body.get("messages") or []
    model = body.get("model") or DEFAULT_MODEL
    payload = {"model": model, "messages": messages, "stream": False}
    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers=_headers(),
            json=payload,
        )
        if resp.status_code >= 400:
            return JSONResponse(status_code=resp.status_code, content={"error": resp.text})
        data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    return {"content": content}


@app.post("/chat/stream")
async def chat_stream(req: Request):
    body = await req.json()
    messages = body.get("messages") or []
    model = body.get("model") or DEFAULT_MODEL

    async def event_generator():
        sent_any = False
        try:
            async for chunk in _stream_deepseek(messages, model):
                sent_any = True
                yield chunk
        except Exception as e:
            if not sent_any and model != FALLBACK_MODEL:
                try:
                    async for chunk in _stream_deepseek(messages, FALLBACK_MODEL):
                        yield chunk
                    return
                except Exception as fb_err:
                    yield f"data: {json.dumps({'error': str(fb_err)})}\n\n"
            else:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ============================================================
# GEO 插件后端端点（懒加载，未装依赖时返回 503，不影响主聊天）
# ============================================================
import re as _re
import asyncio
import hashlib
import xml.etree.ElementTree as _ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pydantic import BaseModel


class FetchBodyRequest(BaseModel):
    url: str


# ── /fetch/rss：RSS/Atom 订阅源抓取（标准库解析，零额外依赖）──
RSS_SOURCES = [
    {"key": "hackernews", "url": "https://hnrss.org/frontpage"},
    {"key": "36kr", "url": "https://36kr.com/feed"},
    {"key": "sspai", "url": "https://sspai.com/feed"},
    {"key": "infoq_cn", "url": "https://www.infoq.cn/feed"},
    {"key": "github_trending", "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml"},
    {"key": "bbc_top", "url": "https://feeds.bbci.co.uk/news/rss.xml"},
    {"key": "wallstreetcn", "url": "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=30"},
]


def _strip_html(html: str) -> str:
    if not html:
        return ""
    s = _re.sub(r"<script[\s\S]*?</script>", " ", html, flags=_re.I)
    s = _re.sub(r"<style[\s\S]*?</style>", " ", s, flags=_re.I)
    s = _re.sub(r"<[^>]+>", " ", s)
    for a, b in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return _re.sub(r"\s{2,}", " ", s).strip()


def _to_ts(value: str) -> int:
    if not value:
        return 0
    try:
        dt = parsedate_to_datetime(value)  # RSS RFC822
        return int(dt.timestamp() * 1000)
    except Exception:
        pass
    try:
        v = value.replace("Z", "+00:00") if value.endswith("Z") else value
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


def _parse_rss_xml(text: str, source_key: str):
    root = _ET.fromstring(text)
    ATOM = "{http://www.w3.org/2005/Atom}"
    atom_entries = root.findall(f".//{ATOM}entry")
    is_atom = len(atom_entries) > 0
    entries = atom_entries if is_atom else (root.findall("./channel/item") or root.findall("./item"))
    items = []
    for node in entries:
        if is_atom:
            title = (node.findtext(f"{ATOM}title") or "").strip()
            link_el = node.find(f"{ATOM}link")
            url = (link_el.get("href") if link_el is not None else "") or ""
            content = _strip_html(
                node.findtext(f"{ATOM}summary") or node.findtext(f"{ATOM}content") or ""
            )
            pub = node.findtext(f"{ATOM}published") or node.findtext(f"{ATOM}updated") or ""
            guid = node.findtext(f"{ATOM}id") or url
            author = (node.findtext(f"{ATOM}author/{ATOM}name") or "").strip()
            cats = [c.text or "" for c in node.findall(f"{ATOM}category") if c.text]
        else:
            title = (node.findtext("title") or "").strip()
            url = (node.findtext("link") or node.findtext("guid") or "").strip()
            content = _strip_html(
                node.findtext("description") or node.findtext("content:encoded")
                or node.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            )
            pub = node.findtext("pubDate") or node.findtext("dc:date") or ""
            guid = node.findtext("guid") or url
            author = (node.findtext("dc:creator") or node.findtext("author") or "").strip()
            cats = [c.text or "" for c in node.findall("category") if c.text]
        published_at = _to_ts(pub)
        item_id = hashlib.md5(f"{source_key}:{guid or title}".encode("utf-8")).hexdigest()
        items.append({
            "id": item_id,
            "title": title,
            "content": content,
            "source": source_key,
            "sourceUrl": url,
            "author": author or None,
            "publishedAt": published_at or int(__import__("time").time() * 1000),
            "tags": [c.lower() for c in cats],
            "heat": 0,
        })
    return items


def _parse_wallstreetcn(data: dict, source_key: str):
    items = []
    for live in (data.get("lives") or [])[:50]:
        content = _strip_html(live.get("content") or "")
        if not content:
            continue
        title = (live.get("title") or content[:40]).strip()
        published_at = live.get("created_at") or 0
        if isinstance(published_at, str):
            published_at = int(published_at) if published_at.isdigit() else 0
        items.append({
            "id": hashlib.md5(f"{source_key}:{live.get('id') or content[:40]}".encode("utf-8")).hexdigest(),
            "title": title,
            "content": content,
            "source": source_key,
            "sourceUrl": "",
            "author": None,
            "publishedAt": published_at or int(__import__("time").time() * 1000),
            "tags": [],
            "heat": 0,
        })
    return items


class FetchRssRequest(BaseModel):
    sources: list | None = None
    limit: int = 20


@app.post("/fetch/rss")
async def fetch_rss(req: FetchRssRequest):
    """并发抓取多个 RSS/Atom 源，返回 ContentItem[]（与前端插件契约一致）。"""
    sources = [s for s in RSS_SOURCES if not req.sources or s["key"] in req.sources]
    if not sources:
        return {"items": [], "count": 0}

    async def grab(src: dict):
        try:
            timeout = httpx.Timeout(15.0, connect=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(
                    src["url"],
                    headers={"User-Agent": "AETHER/1.0 (+https://github.com/aether)"},
                )
                resp.raise_for_status()
                if src["key"] == "wallstreetcn":
                    return _parse_wallstreetcn(resp.json(), src["key"])
                return _parse_rss_xml(resp.text, src["key"])
        except Exception as e:
            print(f"[rss] {src['key']} failed: {e}")
            return []

    results: list = []
    for batch in await asyncio.gather(*(grab(s) for s in sources)):
        results.extend(batch)
    results.sort(key=lambda x: x["publishedAt"], reverse=True)
    limit = max(1, min(req.limit, 100))
    return {"items": results[:limit], "count": min(len(results), limit)}


_playwright_cm = None


@app.post("/fetch/body")
async def fetch_body(req: FetchBodyRequest):
    """用 Playwright 渲染页面并提取正文，绕过 Cloudflare 等反爬机制。"""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return JSONResponse(status_code=503, content={"error": "playwright 未安装"})
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            await page.goto(req.url, wait_until="networkidle", timeout=20000)
            title = await page.title()
            content = await page.evaluate("""() => {
                const article = document.querySelector('article')
                    || document.querySelector('[class*="content"]')
                    || document.querySelector('[class*="article"]')
                    || document.body;
                return article.innerText;
            }""")
            await browser.close()
            content = _re.sub(r'\n{3,}', '\n\n', content).strip()
            return {"title": title, "content": content, "publishedAt": None, "tags": []}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"抓取失败: {e}"})


_embed_model = None


def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embed_model


class EmbedBatchRequest(BaseModel):
    texts: list


@app.post("/embed/batch")
async def embed_batch(req: EmbedBatchRequest):
    """批量生成文本向量，用于语义去重。"""
    if not req.texts:
        return {"embeddings": []}
    try:
        model = _get_embed_model()
    except ImportError:
        return JSONResponse(status_code=503, content={"error": "sentence-transformers 未安装"})
    vectors = model.encode(req.texts, normalize_embeddings=True)
    return {"embeddings": [v.tolist() for v in vectors]}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)

