"""AETHER 对话后端代理 — 前端静态页面通过此服务调 DeepSeek。"""
from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

class ChatReq(BaseModel):
    message: str
    history: list[dict] = []

@app.post("/chat")
async def chat(req: ChatReq):
    messages = [{"role": "system", "content": "你是 AETHER，一个好奇心驱动的自主智能体内核。简洁专业地回答。"}]
    for h in req.history[-10:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            DEEPSEEK_URL,
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.7, "max_tokens": 1024},
            headers={"Authorization": f"Bearer {API_KEY}"},
        )
        r.raise_for_status()
        data = r.json()
    return {"reply": data["choices"][0]["message"]["content"]}

@app.get("/health")
async def health():
    return {"status": "ok", "model": "deepseek-chat"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
