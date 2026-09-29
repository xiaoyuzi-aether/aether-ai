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

## 本地完整运行（接真实 DeepSeek）

```bash
# 1. 拉代码（已有仓库则跳过）
git clone <你的仓库地址>
cd <项目根目录>

# 2. 安装依赖
pnpm install
pip install -r requirements.txt
# 或者至少：
pip install fastapi uvicorn httpx

# 3. 配置后端 Key（Windows PowerShell）
$env:DEEPSEEK_API_KEY = "sk-你的真实key"
# macOS / Linux
# export DEEPSEEK_API_KEY=sk-你的真实key

# 4. 启动后端（两种方式任选）
python server.py
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 5. 验证后端
curl http://localhost:8001/health
# {"version":"...","key_set":true,"model":"deepseek-chat"}

# 6. 配置前端后端地址（.env 或环境变量）
VITE_API_BASE_URL=http://localhost:8001

# 7. 启动前端
pnpm dev
# 打开 http://localhost:5173
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

## 部署上线

```
push 到 main
  ├─ GitHub Actions 构建前端 → GitHub Pages
  └─ Railway 构建后端 → Railway 后端
```

### 前端 → GitHub Pages

`deploy-pages.yml` 已配置好，push 到 main 自动构建 `packages/ui/dist` 并发布。仓库需在 GitHub 开启 Pages（Source: GitHub Actions）。

构建时注入的后端地址在仓库 Secrets 里配置：

```bash
# GitHub → Settings → Secrets and variables → Actions → New repository secret
# 名称 VITE_API_BASE_URL，值：
https://你的railway后端.up.railway.app
```

若仓库名不是根路径部署（如 `https://<用户名>.github.io/<仓库名>/`），`deploy-pages.yml` 已通过 `VITE_BASE_PATH=/${{ github.event.repository.name }}/` 自动处理，无需手动改 `base`。

### 后端 → Railway

1. 新建 Railway 项目，连接仓库，Railway 会自动识别 `railway.json`（Nixpacks + `uvicorn server:app --host 0.0.0.0 --port $PORT`）。
2. 在 Railway 的 Variables 里配置：

```bash
DEEPSEEK_API_KEY=sk-你的真实key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_FALLBACK_MODEL=deepseek-reasoner
CORS_ORIGINS=http://localhost:5173,https://你的用户名.github.io
```

> API Key 只存在 Railway 环境变量里，仓库和前端代码中都只有占位符，浏览器拿不到。

3. 验证：

```bash
curl https://你的railway应用.up.railway.app/health
# {"version":"...","key_set":true,"model":"deepseek-chat"}
```

### CORS 允许来源

`server.py` 通过环境变量 `CORS_ORIGINS` 控制允许来源，默认：

```python
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "https://你的用户名.github.io"
]
```

部署后如需新增来源，在 Railway Variables 里追加，逗号分隔。

### 一键部署

```bash
git add .
git commit -m "deploy"
git push origin main
```

push 后前端 GitHub Pages、后端 Railway 各自自动重建上线。
