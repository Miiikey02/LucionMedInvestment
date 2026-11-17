# 医药赛道研究库

本库把《医药全产业链细分赛道筛选与头部企业研究报告》做成可浏览、可检索的网站，内容包括 16 个细分赛道、64 条技术路线、48 家头部企业及其研发管线、每周自动更新的报告后动态，以及 AI 研究助手。同事只需浏览器即可使用，不需要任何 AI 账号。

## 组成

| 部分 | 位置 | 作用 |
|---|---|---|
| 网站 | `site/` | 纯静态网页，可放在 GitHub Pages 或任何网页空间 |
| AI 网关 | `gateway/` | 保存模型与搜索的 API Key，为网页提供 AI 对话、联网搜索、网页读取 |
| 数据与构建 | `source/`、`data/`、`tools/` | 报告原文、动态与管线数据、构建脚本 |
| 每周更新 | `UPDATE_TASK.md` | 本机定时任务的执行步骤，更新后自动推送到 GitHub |

ClinicalTrials.gov 与 ChEMBL 由浏览器直接查询，不经过网关，所以即使不部署网关，企业页的「查询 ClinicalTrials.gov 登记试验」也能用。

## 发布前请先确认可见范围

GitHub Pages 的网站在公网可以访问。免费账号只能从公开仓库发布 Pages，此时源文件也公开；付费的 Pro 或 Team 账号可以从私有仓库发布，但网站本身仍对所有人公开；只有 GitHub Enterprise Cloud 才能把 Pages 限定为组织成员可见。网站包含报告全文、打分与投资判断。如果这些内容不能公开，请改用以下方式之一：

1. 公司内网或云服务器上的网页服务（把 `site/` 目录交给 IT 发布即可）。
2. 组织已有 GitHub Enterprise Cloud 时，使用私有 Pages。
3. Cloudflare Pages 加 Cloudflare Access，按邮箱限定访问人员。

AI 网关的访问码只保护 AI 额度，不能保护网页内容。

## 第一步 发布网站到 GitHub Pages

1. 在 GitHub 新建仓库（账号支持时建议设为私有），然后在本目录执行
   ```bash
   git add -A && git commit -m "医药赛道研究库"
   ```
   ```bash
   git remote add origin https://github.com/<账号>/<仓库>.git && git push -u origin main
   ```
2. 进入仓库的 Settings，打开 Pages，把 Source 设为 GitHub Actions。`.github/workflows/pages.yml` 会在每次推送后把 `site/` 发布出去。
3. 几分钟后网站地址为 `https://<账号>.github.io/<仓库>/`。

`.gitignore` 已排除报告原文 docx、密钥文件与构建中间文件。

## 第二步 部署 AI 网关（需要 AI 助手和联网搜索时）

### 选择模型

网关支持所有 OpenAI 兼容接口，也支持 Claude（Anthropic API）。在 `gateway/.env.example` 中有 DeepSeek、通义千问、Kimi、智谱与 Claude 的填写示例，换模型只需改环境变量，不用改代码。

联网搜索可选博查（bocha，国内可直接访问）或 Tavily，不配置则 AI 助手不显示联网搜索。

### 方式 A 用 Cloudflare Workers 部署（免费，适合 GitHub Pages）

```bash
cd gateway && npx wrangler login
```
```bash
npx wrangler secret put LLM_API_KEY
```
```bash
npx wrangler secret put ACCESS_CODE
```
```bash
npx wrangler deploy
```

需要联网搜索时再执行 `npx wrangler secret put SEARCH_API_KEY`，并在 `wrangler.toml` 中填写 `SEARCH_PROVIDER`。部署后把 `wrangler.toml` 里的 `ALLOWED_ORIGINS` 改成网站地址（例如 `https://<账号>.github.io`），然后重新部署。

`workers.dev` 域名在中国大陆访问不稳定。同事在国内使用时，请给 Worker 绑定公司自有域名，或使用方式 B。

### 方式 B 在任意服务器上运行（公司服务器、阿里云 ECS 等，需 Node 18 以上）

```bash
cd gateway && cp .env.example .env
```
编辑 `.env` 填入 Key 与访问码后运行
```bash
node server.mjs
```
默认监听 8787 端口，生产环境请放在 HTTPS 反向代理之后。

### 把网站连到网关

在 `config.json` 中填写 `ai_gateway_url`（例如 `https://ai.example.com`），然后执行
```bash
./tools/deploy.sh
```
同事第一次使用 AI 助手时输入管理员提供的访问码，访问码只保存在各自浏览器中。

## 每周自动更新

本机 Claude 应用中的定时任务「医药赛道研究库 每周动态更新」每周一上午运行。它检索 48 家企业与路线标的的融资、BD 与授权、临床、监管事件，核实来源后写入 `data/updates.json`，同步推进 `data/pipelines.json` 中的管线阶段，然后运行 `tools/deploy.sh` 推送到 GitHub，网站随之更新。任务只在这台电脑开着 Claude 应用时运行，同事无需安装任何东西。

## 常用命令

| 命令 | 作用 |
|---|---|
| `./tools/rebuild.sh` | 由报告与数据重新生成网站 |
| `./tools/deploy.sh` | 重新生成并推送到 GitHub |
| `python3 tools/query.py 高瓴` | 在命令行检索数据（供 Agent 使用，字段说明见 `AGENTS.md`） |

更新报告时用新版替换 `source/report.docx`（章节结构保持一致），再运行 `./tools/deploy.sh`。

本工具不构成任何投资建议。
