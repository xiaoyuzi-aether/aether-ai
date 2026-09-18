"""AETHER 对话后端代理 — 前端通过此服务调 DeepSeek。

环境变量：
  DEEPSEEK_API_KEY  或  OPENAI_API_KEY   （必填）
  DEEPSEEK_BASE_URL   默认 https://api.deepseek.com
  DEEPSEEK_MODEL      默认 deepseek-chat
  DEEPSEEK_FALLBACK_MODEL  默认 deepseek-reasoner
  CORS_ORIGINS        逗号分隔白名单，默认 http://localhost:5173
  PORT                Railway 注入
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
    print("[warn] DEEPSEEK_API_KEY not set — /chat will error")


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
        "version": "1.2.0",
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


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
