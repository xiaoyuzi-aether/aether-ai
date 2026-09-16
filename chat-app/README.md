# AETHER Chat App

微内核 + 六边形架构的聊天应用 monorepo。

## 架构

```
ui ──▶ public-api ──▶ core ──▶ kernel
                       ▲
                  adapters（实现 core/ports）
                       ▲
                  plugins（通过 kernel 扩展点注册）
```

## 包结构

- `packages/kernel` — 微内核：生命周期、事件总线、插件注册
- `packages/core` — 领域模型 + 用例 + 端口（零外部依赖）
- `packages/adapters/*` — 端口实现：storage-local / ai-http / file-browser
- `packages/plugins/*` — 官方插件：markdown / attachment / multi-select
- `packages/ui` — Vite + 原生 JS 的聊天 UI
- `packages/public-api` — 稳定对外 API

## 快速开始

```bash
pnpm install
pnpm dev          # 前端 http://localhost:5173
python server.py  # 后端（可选，回显模式）
```

## 依赖边界约束

```bash
pnpm depcruise
```

强制：
- core 不依赖 ui/adapters/plugins
- kernel 不依赖 core
- ui 不直接依赖 adapters
- plugins 只通过 core/ports 依赖

## 接真实 LLM

替换 `packages/adapters/ai-http/src/index.js` 中的 `createHttpAiGateway`，或直接改 `server.py` 转发到 DeepSeek/OpenAI 兼容接口。
