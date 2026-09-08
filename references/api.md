# AI HOT v1 API 参考(平台复刻版)

普通问答优先通过 `scripts/aihot.py` 完成,本文件仅在构建客户端、排查问题或需要完整契约时读取。

## 共同合同

- Base URL: `https://aihot.virxact.com`
- 匿名只读,不需要 API Key,不发送 cookie。
- OpenAPI: `https://aihot.virxact.com/openapi-v1.json`
- 所有 cursor 都是不透明书签:只原样回传给产生它的同一端点和同一查询,不解析、不修改、不跨查询复用。
- 未知参数、无效参数、损坏或跨查询 cursor 都返回明确的 Problem JSON。

## 端点速查

| 端点 | 用途 |
|---|---|
| `GET /api/v1/items?mode=selected\|all&window=24h\|7d&limit=N` | 资讯;支持 `q` 关键词、`category` 分类、`by=timeline\|published` 时间口径 |
| `GET /api/v1/items?q=<关键词>&mode=selected` | 关键词搜索(精选池空时同参再查 `mode=all`) |
| `GET /api/v1/hot-topics` | 当前热点(保持 API 热度顺序) |
| `GET /api/v1/stories/{publicId}` | 热点事件详情(publicId 只取自 hot-topics 的 `links.story` 路径末段,不得猜测) |
| `GET /api/v1/dailies/latest` \| `/api/v1/dailies/{YYYY-MM-DD}` | 最新/指定日报 |
| `GET /api/v1/dailies?limit=N` | 日报列表 |
| `GET /api/v1/selected/snapshot?fields=minimal&limit=500` | 完整精选同步(全量镜像用) |

## items 参数

| 参数 | 合同 |
|---|---|
| `mode` | `selected` 或 `all`;默认 `selected` |
| `window` | `24h` 或 `7d`;默认 `7d` |
| `by` | `timeline`(默认,与网页一致)或 `published`(严格按原文发布时间) |
| `category` | `ai-models`、`ai-products`、`industry`、`paper`、`tip` |
| `q` | 2—200 字;使用服务端搜索 |
| `limit` | 1—100;默认 50。做简报时 7 天窗口传 10 就够 |
| `cursor` | 原样回传上一页的 `page.nextCursor` |

### 时间口径(by)

- `by=timeline`(默认):原文发布 72 小时内被收录的按收录时间算,超过 72 小时的旧文回填归位到原文发布日。所以官方博客、公众号这类"原文两三天前发、今天才收录"的慢推信源仍会出现在 24h 窗口里。
- `by=published`:只按第三方原文发布时间,慢推信源会掉出短窗口。
- 切换 `by` 会让已有 cursor 失效,属正常行为。

### items 响应字段

每个 item:`id`、`title`、`originalTitle`、`summary`、`source.name`、`links.aihot`、`links.original`、`publishedAt`、`discoveredAt`、`category`、`score`、`selected`。
其中 `originalTitle`、`summary`、`publishedAt`、`category`、`score` 值可能为 `null`,展示前必须判空;`id`、`title`、`source.name`、`links.aihot`、`links.original`、`discoveredAt`、`selected` 非空。
`page.count` 是本页条数,不是全库总数。

## 日报结构

- 索引响应:`{schemaVersion, count, items}`(非可续页集合)。
- 最新/指定日报:`{schemaVersion, report}`。
- report 含 `lead`(可空)、`sections`(数组,每项 `{label, items:[{title, summary, source.name, links.aihot/original}]}`)。
- sections 中 `links.aihot` 可能为 null,此时用 `links.original`。
- 最新日报或指定日期 404 时:只查一次 `/api/v1/dailies?limit=7`,取实际返回的最近日期再请求一次;索引为空就报告无可用日报。绝不猜"昨天"或拼日期。

## 边界

- items 只返回标题、摘要、来源、时间、评分和链接,不返回正文,也没有 `/api/v1/items/{id}`。用户要深入阅读时提供 `links.aihot` 和 `links.original`。
- 周报/月报只有 `/weekly`、`/monthly` 网页,无 API/RSS/Skill 端点。
- v1 只承诺 `24h` 和 `7d` 两个服务端窗口;超过 7 天的普通公开池不承诺可用。
