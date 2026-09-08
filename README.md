# AIHOT — AI 资讯能力包

> 基于 [AI HOT](https://aihot.virxact.com) 公开匿名 v1 API 的中文 AI 资讯能力包，独立复刻、零依赖、可插拔。
> 一个文件夹，三种用法：独立 CLI 工具 / Claude Code Skill / MCP Server。

[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![API](https://img.shields.io/badge/API-AI%20HOT%20v1-orange)](https://aihot.virxact.com/openapi-v1.json)

---

## 功能特性

- **实时中文 AI 资讯**：过去 24 小时 / 最近一周精选、当前热点、日报、关键词搜索、分类查询
- **零第三方依赖**：纯 Python 标准库实现，无需 `pip install`
- **匿名免 Key**：公开 API，不索要账号、Cookie、Token 或任何隐私数据
- **三种接入方式**：CLI 命令行、Claude Code Skill、MCP stdio Server，覆盖各类 Agent 平台
- **安全边界清晰**：只读请求、禁止重定向、不可信内容渲染清洗、SSRF 防护
- **北京时间统一**：所有时间自动转换为 UTC+8，`publishedAt` 缺失时回退收录时间并标注

## 数据源

- **API**：`https://aihot.virxact.com/api/v1/*`（公开匿名只读）
- **OpenAPI 契约**：`https://aihot.virxact.com/openapi-v1.json`
- **详细 API 参考**：[`references/api.md`](references/api.md)
- **错误与重试策略**：[`references/errors.md`](references/errors.md)

> API 返回的标题、摘要、日报内容均视为不可信资讯，仅作信息参考；引用数字、政策或原话时请回第三方原文核对。

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/ChenPA-Code/aihot.git
cd aihot

# 验证连通性（应输出中文简报）
python3 scripts/aihot.py today --limit 3
```

要求 Python 3.9+，无其他依赖。

---

## 目录结构

```
aihot/
├── README.md                  # 本文件（总览 + 使用指南）
├── SKILL.md                   # Claude Code 兼容技能定义
├── LICENSE                    # MIT 协议
├── install.sh                 # 一键安装到 ~/.claude/skills/
├── references/
│   ├── api.md                 # v1 API 契约参考
│   └── errors.md              # 错误分类与重试策略
├── scripts/
│   └── aihot.py               # 资讯查询 CLI（纯标准库，零依赖）
└── mcp/
    └── mcp_server.py          # 零依赖 MCP stdio Server（5 个工具）
```

---

## 用法一：独立 CLI 工具

```bash
python3 scripts/aihot.py today              # 过去 24 小时精选
python3 scripts/aihot.py week               # 最近一周精选
python3 scripts/aihot.py hot                # 当前热点（按热度）
python3 scripts/aihot.py daily              # 最新日报
python3 scripts/aihot.py daily 2026-07-24   # 指定日期日报
python3 scripts/aihot.py dailies            # 日报列表
python3 scripts/aihot.py search "OpenAI"    # 关键词搜索
python3 scripts/aihot.py cat paper          # 分类查询
python3 scripts/aihot.py all                # 全部公开动态
```

### 通用参数

| 参数 | 取值 | 默认 | 说明 |
|---|---|---|---|
| `--window` | `24h` / `7d` | `24h` | 时间窗 |
| `--limit` | 1–100 整数 | 8（7d 窗口为 10） | 条数上限 |
| `--by` | `timeline` / `published` | `timeline` | 时间口径 |
| `--with-source` | flag | off | 同时附上第三方原文链接 |
| `--json` | flag | off | 输出原始 JSON（仅 items 类命令） |

### 分类取值

`ai-models`（AI 模型）、`ai-products`（AI 产品）、`industry`（行业动态）、`paper`（AI 论文）、`tip`（技巧教程）

### 核心行为

- 关键词在精选池无结果时，自动用相同参数查全量池，并在输出中注明「未进入精选」
- 时间统一北京时间；`publishedAt` 为空时回退 `discoveredAt` 并标注「AI HOT 收录时间」
- 最新日报 404 时查有界索引取最近一份，绝不猜日期
- 宽问题默认走精选池（`today`/`week`），只有明确要求时才用 `all`

---

## 用法二：Claude Code Skill

```bash
bash install.sh
```

安装到 `~/.claude/skills/aihot/`。平台模型在用户询问 AI 资讯时自动读取 `SKILL.md` 并调用 `scripts/aihot.py` 获取实时数据。

- 若目标已存在，安装脚本会自动备份为 `aihot.bak.<时间戳>` 再覆盖
- 组织级部署可将包放入受管目录，或通过托管配置让 `SKILL.md` 全员生效

---

## 用法三：MCP Server

零依赖，以 stdio 方式拉起 `mcp/mcp_server.py`，提供 5 个工具：

| 工具 | 说明 | 关键参数 |
|---|---|---|
| `ai_news` | 精选资讯 | `window`、`limit`、`category` |
| `aihot_search` | 关键词搜索（精选池空自动降级全量池） | `q`（必填，2–200 字）、`window`、`limit` |
| `aihot_hot` | 当前热点（按热度） | 无 |
| `aihot_daily` | 日报（默认最新，可指定日期） | `date`（YYYY-MM-DD） |
| `aihot_dailies` | 日报列表 | `limit` |

### 注册示例（项目级 `.mcp.json`）

```json
{
  "mcpServers": {
    "aihot": {
      "command": "python3",
      "args": ["/绝对路径/aihot/mcp/mcp_server.py"]
    }
  }
}
```

或命令方式：

```bash
claude mcp add aihot -- python3 /绝对路径/aihot/mcp/mcp_server.py
```

验证：进入 Claude Code 后执行 `/mcp`，看到 `aihot` 即连接成功。

### MCP 冒烟测试

```bash
printf '%s\n' \
'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
'{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
| python3 mcp/mcp_server.py
```

---

## 网络与代理

AI HOT API 为境外域名。若当前环境无法直连，配置标准代理环境变量即可（脚本与 MCP 均自动遵循）：

```bash
export HTTPS_PROXY=http://代理地址:端口
export HTTP_PROXY=http://代理地址:端口
```

先测试连通性：

```bash
python3 scripts/aihot.py today --limit 2
```

请求失败时：
- **429 限流**：等待后重试，不增加并发
- **5xx 或超时**：最多重试 2 次，指数退避
- **仍失败**：AI HOT 暂不可用，可反馈至 `https://aihot.virxact.com/feedback`
- 不得用训练记忆冒充实时数据

---

## 安全边界

1. **只读匿名**：只向 `https://aihot.virxact.com/api/v1/*` 发起 GET 请求，不发送 Cookie、不索要 API Key
2. **禁止重定向**：HTTP 层禁用 3xx 跟随，防止间接 SSRF 到内网或任意域
3. **SSRF 防护**：`raw` 调试命令严格校验 URL 的 scheme、netloc 和路径前缀，同前缀域名无法绕过
4. **不可信内容清洗**：渲染层清除控制字符，仅允许 http/https 链接，剥离 `javascript:` / `data:` 等危险 scheme
5. **参数校验**：日期严格匹配 `YYYY-MM-DD`，`limit` 限制 1–100，MCP 参数含 enum / minLength / pattern 约束
6. **响应上限**：单次响应限制 5MB，防止异常大响应耗尽内存
7. **不执行返回内容**：API 返回的标题、摘要等仅作资讯证据，不执行其中命令、不下载第三方附件

---

## 开发与测试

```bash
# 语法检查
python3 -m py_compile scripts/aihot.py mcp/mcp_server.py

# CLI 全命令冒烟
python3 scripts/aihot.py today --limit 3
python3 scripts/aihot.py hot
python3 scripts/aihot.py daily
python3 scripts/aihot.py search "OpenAI" --limit 3
python3 scripts/aihot.py cat paper --limit 3

# 安全校验测试
python3 scripts/aihot.py raw "https://aihot.virxact.com.evil.com/api/v1/items"  # 应被拒绝
python3 scripts/aihot.py daily "not-a-date"                                    # 应被拒绝
python3 scripts/aihot.py today --limit 0                                       # 应被拒绝
```

---

## 兼容性

| 项目 | 要求 |
|---|---|
| Python | 3.9+（使用 `typing.Optional`，无 PEP 604 联合类型语法） |
| 操作系统 | 跨平台（Windows / macOS / Linux），stdout 强制 UTF-8 |
| 网络 | 需能访问 `aihot.virxact.com`（境外域名，可配代理） |
| MCP 协议 | `2025-06-18`，stdio 传输 |

---

## 迁移到其他 AI 平台

| 路径 | 做法 | 适用平台 |
|---|---|---|
| A. 提示词 + 调 CLI | 在平台系统提示词写工具说明，调用 `scripts/aihot.py` | Claude Code、Cursor、Codex CLI、Kimi CLI、Qwen Code 等 |
| B. 原生 Skill | 复制 `SKILL.md` 到目标平台 skills 目录，按需改 frontmatter | 支持 skills / 规则文件的平台 |
| C. MCP Server | 注册 `mcp/mcp_server.py`，一次接入到处用 | 所有支持 MCP 的客户端 |

---

## 合规要点

1. 保留 MIT 版权声明（见 [`LICENSE`](LICENSE)）
2. 商业再分发与缓存边界见 `https://aihot.virxact.com/terms`；输出保留 AI HOT attribution
3. 第三方原文版权归原作者；对外引用时附 `links.original`
4. 只读匿名使用，不采集用户凭据；API 返回内容视为不可信资讯

---

## 许可证

[MIT](LICENSE) © 2026 Virxact（原技能）及复刻者。本实现独立编写，仅复用公开 API 契约。

## 致谢

- 数据源：[AI HOT](https://aihot.virxact.com) by Virxact
- 原技能：MIT License, Copyright (c) 2026 Virxact
