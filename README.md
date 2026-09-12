# AETHER 官网 · GitHub Pages 免费部署包

本目录是一套可直接上传到 GitHub 的静态网站，托管在 **GitHub Pages**（免费、公网可访问），部署后手机和电脑都能直接打开。

## 目录结构

```
gh-pages/
├── index.html          ← 手机版官网（首页，推荐手机打开）
├── desktop/
│   └── index.html      ← 桌面完整版（含在线演示）
└── README.md           ← 本说明
```

部署后访问地址：
- 手机版（首页）：`https://xiaoyuzi-aether.github.io/aether-ai/`
- 桌面完整版：`https://xiaoyuzi-aether.github.io/aether-ai/desktop/`

---

## 部署步骤（约 3 分钟，全程免费）

### 方式一：网页直接上传（最简单，无需命令行）

1. 打开 **github.com** 并登录（没有账号先免费注册一个）。
2. 点右上角 **+** → **New repository**（新建仓库）：
   - Repository name 填：`aether-ai`
   - 选择 **Public**（公开，免费托管必须公开）
   - 不要勾选 "Add a README file"，直接点 **Create repository**
3. 进入仓库后点 **uploading an existing file**（上传已有文件）：
   - 把本目录里的 `index.html` 和 `desktop` 文件夹拖进去
   - 点 **Commit changes**（提交）
4. 点仓库页面的 **Settings** → 左侧 **Pages**：
   - Source 选 **Deploy from a branch**
   - Branch 选 **main**、目录选 **/ (root)**
   - 点 **Save**
5. 等待 1~2 分钟，页面顶部出现提示后，访问：
   `https://xiaoyuzi-aether.github.io/aether-ai/`

### 方式二：命令行推送（有 Git 的话）

```bash
cd gh-pages
git init
git add .
git commit -m "AETHER official site"
git branch -M main
git remote add origin https://github.com/xiaoyuzi-aether/aether-ai.git
git push -u origin main
```

推送后同样到 **Settings → Pages** 里选择 main 分支的 / (root) 开启即可。

---

## 常见问题

- **打开是 404？** 等 1~2 分钟让 Pages 首次构建完成，或确认仓库名与 `aether-ai` 完全一致、分支选的是 main。
- **想换域名？** GitHub Pages 支持绑定自定义域名（免费，需自己购买域名）。
- **想更新内容？** 重新上传覆盖 `index.html` 即可，1 分钟后自动生效。

## 说明

- 网站为纯静态单文件，无后端依赖；字体与背景图走公共 CDN，公网可正常加载。
- 代码 Apache-2.0。网站内"源码仓库"链接指向 `github.com/xiaoyuzi-aether/ether-ai`，仓库创建后即可直达。
