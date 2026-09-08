# 错误与重试(平台复刻版)

请求失败时读取本文件。先保护用户问题的原意,再考虑重试;不得靠放宽参数或换数据源伪装成功。

## 错误分类(按 Problem code 分支)

标准错误使用 `application/problem+json`,含 `code`、`detail`、`requestId`。按稳定 `code` 分支,不解析 `detail` 人话:

- `invalid_request`:修正明确参数;不要自动改成另一个问题。
- `invalid_cursor`:书签已失效。恢复方式是从第一页重新发起同一查询,并如实说明列表已从头开始;禁止静默回退。
- `snapshot_required`:仅 selected changes 需按完整 snapshot 流程重建一次。
- `rate_limited`:遵守 `Retry-After`,串行重试。
- `temporarily_unavailable`:有限退避后告诉用户暂不可用。

未知 code 按 HTTP status 保守处理,并保留 `requestId` 供反馈。

CDN 安全层可能返回 566/567 极小 JSON,不保证 Problem 格式。这不改变匿名访问合同。保留 `requestId` 和 `help`,正常退避后最多重试一次;仍失败就停止并反馈。

## 重试规则

- `400/409`:除明确的 snapshot 恢复外,不盲目重试。
- `404`:普通资源不重试;日报按 api.md 只查一次有界索引,不猜日期。
- `429`:按 `Retry-After` 等待;没有该头时等待 60 秒。不增加并发。
- `5xx` 或超时:最多重试 2 次,指数退避。
- 仍失败:说明 AI HOT 暂不可用,并提供 `https://aihot.virxact.com/feedback`;不得用训练记忆冒充实时数据。

## 持久轮询

使用条件请求:

```text
If-None-Match: <上次同一完整 URL 的 ETag>
```

`304` 表示内容未变化,保留已有数据与 cursor,不把它当空响应。
正常轮询同一端点至少间隔 60 秒。
