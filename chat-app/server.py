"""AETHER 对话后端代理 — 前端静态页面通过此服务调 DeepSeek。

API Key 从环境变量 OPENAI_API_KEY 读取，绝不写进代码，也不暴露给前端。
前端只调 http://localhost:8001/chat 或 /chat/stream。
"""
from __future__ import annotations
import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import httpx

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_PROMPT = "你是 AETHER，一个好奇心驱动的自主智能体内核。简洁专业地回答。"

class ChatReq(BaseModel):
    message: str
    history: list[dict] = []

def build_messages(req: ChatReq) -> list[dict]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in req.history[-10:]:
        msgs.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    msgs.append({"role": "user", "content": req.message})
    return msgs

@app.post("/chat")
async def chat(req: ChatReq):
    if not API_KEY:
        return {"reply": "⚠️ 后端未配置 OPENAI_API_KEY 环境变量。"}
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            DEEPSEEK_URL,
            json={"model": "deepseek-chat", "messages": build_messages(req), "temperature": 0.7, "max_tokens": 1024},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        r.raise_for_status()
        data = r.json()
    return {"reply": data["choices"][0]["message"]["content"]}

@app.post("/chat/stream")
async def chat_stream(req: ChatReq):
    if not API_KEY:
        async def empty():
            yield 'data: {"choices":[{"delta":{"content":"未配置 API key"}}]}\n\n'
            yield 'data: [DONE]\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream")

    async def gen():
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                DEEPSEEK_URL,
                json={"model": "deepseek-chat", "messages": build_messages(req),
                      "temperature": 0.7, "max_tokens": 1024, "stream": True},
                headers={"Authorization": f"Bearer {API_KEY}"},
            ) as r:
                async for line in r.aiter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        yield line + "\n\n"
                    elif line == "data: [DONE]":
                        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/health")
async def health():
    return {"status": "ok", "model": "deepseek-chat" if API_KEY else "no-key"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
