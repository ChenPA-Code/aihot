#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_server.py — AI HOT MCP Server(零依赖版)

纯 Python 标准库实现 MCP stdio 协议(JSON-RPC 2.0,换行分隔),无需 pip install。
可直接被任何支持 MCP 的客户端(Claude Code、Claude Desktop、Cursor、Windsurf
及各类国产 Agent 平台)以 stdio 方式接入。

用法:
  python3 mcp_server.py            # 以 stdio 模式运行(供 MCP 客户端拉起)

或手动测试:
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' | python3 mcp_server.py

MIT License. 原技能版权归 Virxact(2026);本实现独立编写,仅复用公开 API 契约。
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

BASE_URL = "https://aihot.virxact.com"
USER_AGENT = "aihot-mcp/1.0 (+https://aihot.virxact.com/)"
SHANGHAI = timezone(timedelta(hours=8))
PROTOCOL_VERSION = "2025-06-18"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024

CATEGORY_ZH = {
    "ai-models": "AI 模型",
    "ai-products": "AI 产品",
    "industry": "行业动态",
    "paper": "AI 论文",
    "tip": "技巧教程",
}
CATEGORY_SET = set(CATEGORY_ZH.keys())
WINDOW_SET = {"24h", "7d"}

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# 安全与校验工具
# ---------------------------------------------------------------------------

class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """禁止跟随 3xx 重定向,防止间接 SSRF。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _clean_text(value) -> str:
    if not isinstance(value, str):
        return value
    return _CTRL_RE.sub("", value)


def _safe_url(value) -> str:
    if not isinstance(value, str) or not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    return value if parsed.scheme in ("http", "https") else ""


def _validate_date(date_str: str) -> str:
    if not _DATE_RE.match(date_str):
        raise RuntimeError("date 格式应为 YYYY-MM-DD")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise RuntimeError(f"无效日期: {date_str}")
    return date_str


def _validate_limit(limit, default: int) -> int:
    if limit is None:
        return default
    if not isinstance(limit, int) or not (1 <= limit <= 100):
        raise RuntimeError("limit 须为 1-100 的整数")
    return limit


def _validate_window(window: str) -> str:
    if window not in WINDOW_SET:
        raise RuntimeError("window 须为 24h 或 7d")
    return window


# ---------------------------------------------------------------------------
# API 层(与 scripts/aihot.py 相同契约)
# ---------------------------------------------------------------------------

def fetch(path: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("API 响应超过 5MB 上限,已中止读取")
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API 返回 HTTP {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 AI HOT API: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"API 响应不是合法 JSON: {e}") from e


# ---------------------------------------------------------------------------
# 展示层
# ---------------------------------------------------------------------------

def fmt_time(iso: Optional[str], fallback: bool = False) -> str:
    if not iso:
        return "时间未知"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(SHANGHAI)
    except ValueError:
        return iso
    s = dt.strftime("%m-%d %H:%M")
    return f"{s}(AI HOT 收录时间)" if fallback else s


def item_time(item: dict) -> str:
    if item.get("publishedAt"):
        return fmt_time(item["publishedAt"])
    return fmt_time(item.get("discoveredAt"), fallback=True)


def render_items(items: list, head: str, with_source: bool = False) -> str:
    if not items:
        return f"## {head}\n\n(当前没有匹配的条目)\n"
    lines = [f"## {head}", ""]
    for i, it in enumerate(items, 1):
        title = _clean_text(it.get("title") or it.get("originalTitle") or "(无标题)")
        link = _safe_url((it.get("links") or {}).get("aihot") or "")
        source = _clean_text(((it.get("source") or {}).get("name")) or "未知来源")
        lines.append(f"{i}. [{title}]({link})" if link else f"{i}. {title}")
        origin = _safe_url((it.get("links") or {}).get("original") or "")
        sp = f"[{source}]({origin})" if with_source and origin else source
        lines.append(f"   - {sp} · {item_time(it)}")
        if it.get("summary"):
            lines.append(f"   - {_clean_text(it['summary'])}")
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def render_hot(items: list) -> str:
    if not items:
        return "## 当前热点\n\n(当前没有热点数据)\n"
    lines = ["## 当前热点", ""]
    for i, it in enumerate(items, 1):
        title = _clean_text(it.get("title") or "(无标题)")
        n = it.get("sourceCount") or 0
        lines.append(f"{i}. **{title}**")
        lines.append(f"   - 独立信源 {n} 个 · 最新动态 {fmt_time(it.get('latestAt'))}")
        story = _safe_url((it.get("links") or {}).get("story") or "")
        if story:
            lines.append(f"   - 事件页: {story}")
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def render_daily(report: dict) -> str:
    out = []
    date = _clean_text(report.get("date") or "AI HOT 日报")
    link = _safe_url((report.get("links") or {}).get("aihot") or "")
    out.append(f"# {date} 日报" + (f" [站内阅读]({link})" if link else ""))
    if report.get("lead"):
        out += ["", _clean_text(report["lead"])]
    for sec in report.get("sections") or []:
        label = _clean_text(sec.get("label") or sec.get("title") or "快讯")
        out += ["", f"## {label}"]
        for it in sec.get("items") or []:
            t = _clean_text(it.get("title") or it.get("text") or "(无标题)")
            links = it.get("links") or {}
            l = _safe_url(links.get("aihot") or links.get("original") or "")
            out.append(f"- {t}" + (f" [原文]({l})" if l else ""))
            if it.get("summary"):
                out.append(f"  {_clean_text(it['summary'])}")
    flashes = report.get("flashes") or []
    if flashes and not report.get("sections"):
        out += ["", "## 快讯"]
        for it in flashes:
            t = _clean_text(it.get("title") or it.get("text") or "(无标题)")
            links = it.get("links") or {}
            l = _safe_url(links.get("aihot") or links.get("original") or "")
            out.append(f"- {t}" + (f" [原文]({l})" if l else ""))
    out += ["", "---"]
    return "\n".join(out)


def render_daily_index(items: list) -> str:
    if not items:
        return "当前没有可用日报。\n"
    lines = ["可用日报:", ""]
    for it in items:
        d = _clean_text(it.get("date") or it.get("title") or "")
        link = _safe_url((it.get("links") or {}).get("aihot") or "")
        lines.append(f"- **{d}**" + (f" [阅读]({link})" if link else ""))
    lines.append("")
    lines.append("提示: ai_news 或 aihot_daily 传 date 参数获取指定日期完整日报。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 工具实现
# ---------------------------------------------------------------------------

def tool_ai_news(window: str = "24h", limit: Optional[int] = None, category: str = "") -> str:
    window = _validate_window(window)
    limit = _validate_limit(limit, 8)
    if category and category not in CATEGORY_SET:
        raise RuntimeError(f"category 须为: {', '.join(sorted(CATEGORY_SET))}")
    params: dict = {"mode": "selected", "window": window, "limit": limit}
    if category:
        params["category"] = category
    data = fetch("/api/v1/items", params)
    items = data.get("items") or []
    head = f"{CATEGORY_ZH.get(category, category)}动态({window} 内)" if category else \
        ("过去 24 小时 AI 圈重点" if window == "24h" else "最近一周 AI 圈重点")
    total = data.get("page", {}).get("count") or len(items)
    return render_items(items, head) + f"\n时间窗:{'过去 24 小时' if window=='24h' else '最近 7 天'} · 共 {total} 条\n"


def tool_search(q: str, window: str = "24h", limit: Optional[int] = None) -> str:
    if not isinstance(q, str) or not (2 <= len(q) <= 200):
        raise RuntimeError("q 须为 2-200 字的关键词")
    window = _validate_window(window)
    limit = _validate_limit(limit, 5)
    params = {"mode": "selected", "window": window, "limit": limit, "q": q}
    data = fetch("/api/v1/items", params)
    items = data.get("items") or []
    fell_back = False
    if not items:
        data = fetch("/api/v1/items", {**params, "mode": "all"})
        items = data.get("items") or []
        fell_back = True
    total = data.get("page", {}).get("count") or len(items)
    body = render_items(items, f"“{q}”相关资讯({window} 内)")
    if fell_back:
        body += "\n> 注: 精选池无匹配,以上为未进入精选的全量池结果。\n"
    return body + f"\n时间窗:{'过去 24 小时' if window=='24h' else '最近 7 天'} · 共 {total} 条\n"


def tool_hot() -> str:
    data = fetch("/api/v1/hot-topics")
    return render_hot(data.get("items") or [])


def tool_daily(date: str = "") -> str:
    if date:
        date = _validate_date(date)
        data = fetch(f"/api/v1/dailies/{date}")
        return render_daily(data.get("report") or {})
    try:
        data = fetch("/api/v1/dailies/latest")
        return render_daily(data.get("report") or {})
    except RuntimeError as e:
        if "404" not in str(e):
            raise
        idx = fetch("/api/v1/dailies", {"limit": 7})
        items = idx.get("items") or []
        if not items or not items[0].get("date"):
            return "当前没有可用日报。\n"
        d = _validate_date(items[0]["date"])
        data = fetch(f"/api/v1/dailies/{d}")
        return f"(最新日报暂不可用,已取最近一份: {d})\n\n" + render_daily(data.get("report") or {})


def tool_dailies(limit: Optional[int] = None) -> str:
    limit = _validate_limit(limit, 7)
    data = fetch("/api/v1/dailies", {"limit": limit})
    return render_daily_index(data.get("items") or [])


TOOLS: dict = {
    "ai_news": {
        "description": "查询 AI HOT 中文 AI 资讯精选。window 取 24h 或 7d;category 可选 ai-models/ai-products/industry/paper/tip。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "window": {"type": "string", "enum": ["24h", "7d"], "description": "时间窗,默认 24h"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "条数上限,默认 8"},
                "category": {"type": "string", "enum": ["ai-models", "ai-products", "industry", "paper", "tip"], "description": "分类,默认空(全部)"},
            },
        },
    },
    "aihot_search": {
        "description": "按关键词搜索 AI HOT 资讯(公司、产品、主题)。精选池无结果时自动查全量池并注明。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "minLength": 2, "maxLength": 200, "description": "关键词,2-200 字"},
                "window": {"type": "string", "enum": ["24h", "7d"], "description": "时间窗,默认 24h"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "条数上限,默认 5"},
            },
            "required": ["q"],
        },
    },
    "aihot_hot": {
        "description": "查询 AI HOT 当前热点(按热度排序,含独立信源数与事件页链接)。",
        "inputSchema": {"type": "object", "properties": {}},
    },
    "aihot_daily": {
        "description": "获取 AI HOT 日报。date 为空返回最新日报;指定 YYYY-MM-DD 返回该日期日报。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$", "description": "YYYY-MM-DD,为空取最新日报"},
            },
        },
    },
    "aihot_dailies": {
        "description": "列出最近可用的 AI HOT 日报日期列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "列表条数,默认 7"},
            },
        },
    },
}

HANDLERS = {
    "ai_news": tool_ai_news,
    "aihot_search": tool_search,
    "aihot_hot": tool_hot,
    "aihot_daily": tool_daily,
    "aihot_dailies": tool_dailies,
}


# ---------------------------------------------------------------------------
# MCP stdio 协议(JSON-RPC 2.0,换行分隔)
# ---------------------------------------------------------------------------

def _reply(msg_id, result=None, error=None) -> str:
    body: dict = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    return json.dumps(body, ensure_ascii=False)


def handle(msg: dict) -> Optional[str]:
    method = msg.get("method")
    msg_id = msg.get("id")
    params = msg.get("params") or {}
    is_request = msg_id is not None

    if method == "initialize":
        # 恒返服务端支持的协议版本,不回显客户端值
        return _reply(msg_id, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "aihot-mcp", "version": "1.0.0"},
        })
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return _reply(msg_id, {}) if is_request else None
    if method == "tools/list":
        tools = [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
                 for n, t in TOOLS.items()]
        return _reply(msg_id, {"tools": tools})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if not handler:
            return _reply(msg_id, error={"code": -32601, "message": f"unknown tool: {name}"})
        try:
            text = handler(**args)
        except RuntimeError as e:
            return _reply(msg_id, error={"code": -32000, "message": str(e)})
        except TypeError as e:
            return _reply(msg_id, error={"code": -32602, "message": f"invalid arguments: {e}"})
        return _reply(msg_id, {"content": [{"type": "text", "text": text}]})

    if is_request:
        return _reply(msg_id, error={"code": -32601, "message": f"method not found: {method}"})
    return None


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stdin and hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        out = handle(msg)
        if out is not None:
            sys.stdout.write(out + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
