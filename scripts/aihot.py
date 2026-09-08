#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
aihot.py — AI HOT 中文 AI 资讯 CLI 客户端(独立复刻版)

基于 aihot.virxact.com 公开匿名 v1 API,纯 Python 标准库实现,零第三方依赖。
可在任何支持 Python 3.9+ 的环境直接运行,不依赖任何 AI 平台。

MIT License,原技能版权归 Virxact(2026)。本实现独立编写,仅复用公开 API 契约。
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Optional

BASE_URL = "https://aihot.virxact.com"
API_PREFIX = "/api/v1/"
USER_AGENT = "aihot-cli/1.0 (+https://aihot.virxact.com/)"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 响应上限 5MB,防止异常大响应耗尽内存

CATEGORY_ZH = {
    "ai-models": "AI 模型",
    "ai-products": "AI 产品",
    "industry": "行业动态",
    "paper": "AI 论文",
    "tip": "技巧教程",
}

# 北京时间 = UTC+8,中国无夏令时,恒定偏移即可(避免依赖系统 tzdata)
SHANGHAI = timezone(timedelta(hours=8))

# 控制字符过滤(保留 \n \t,其余 C0 与 DEL 清除),防止不可信内容注入终端/渲染器
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# ---------------------------------------------------------------------------
# 安全与校验工具
# ---------------------------------------------------------------------------

class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """禁止跟随 3xx 重定向,防止间接 SSRF 到内网或任意域。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, msg, headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirectHandler)


def _clean_text(value) -> str:
    """清除不可信文本中的控制字符;非字符串原样返回。"""
    if not isinstance(value, str):
        return value
    return _CTRL_RE.sub("", value)


def _safe_url(value) -> str:
    """只允许 http/https 链接,其它 scheme(含 javascript:/data:)返回空串。"""
    if not isinstance(value, str) or not value:
        return ""
    parsed = urllib.parse.urlsplit(value)
    return value if parsed.scheme in ("http", "https") else ""


def _validate_date(date_str: str) -> str:
    """校验 YYYY-MM-DD 格式且为真实日期,防止路径注入。"""
    if not _DATE_RE.match(date_str):
        raise RuntimeError("日期格式应为 YYYY-MM-DD")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise RuntimeError(f"无效日期: {date_str}")
    return date_str


def _limit_type(value: str) -> int:
    """argparse type:limit 须在 1-100 之间。"""
    n = int(value)
    if not (1 <= n <= 100):
        raise argparse.ArgumentTypeError("limit 须在 1-100 之间")
    return n


# ---------------------------------------------------------------------------
# 基础 HTTP 层
# ---------------------------------------------------------------------------

def fetch(path: str, params: Optional[dict] = None, timeout: int = 30) -> dict:
    """发起匿名只读请求,返回解析后的 JSON。失败抛 RuntimeError(带中文说明)。"""
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
        detail = ""
        try:
            body = json.loads(e.read().decode("utf-8"))
            detail = body.get("title") or body.get("detail") or ""
        except Exception:
            pass
        raise RuntimeError(f"API 返回 HTTP {e.code}{(' - ' + str(detail)) if detail else ''}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"无法连接 AI HOT API: {e.reason}") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"API 响应不是合法 JSON: {e}") from e


# ---------------------------------------------------------------------------
# 展示层
# ---------------------------------------------------------------------------

def fmt_time(iso: Optional[str], *, fallback_label: bool = False) -> str:
    """ISO 时间转北京时间字符串。iso 为空返回 '时间未知'。"""
    if not iso:
        return "时间未知"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(SHANGHAI)
    except ValueError:
        return iso
    label = "AI HOT 收录时间" if fallback_label else ""
    s = dt.strftime("%m-%d %H:%M")
    return f"{s}({label})" if label else s


def display_time(item: dict) -> str:
    """publishedAt 为空时回退 discoveredAt,并按规范标注收录时间。"""
    if item.get("publishedAt"):
        return fmt_time(item["publishedAt"])
    return fmt_time(item.get("discoveredAt"), fallback_label=True)


def render_items(items: list, title: str, with_source: bool = False) -> str:
    """把 items 渲染成中文 Markdown 简报(与官方技能输出风格一致)。"""
    if not items:
        return f"## {title}\n\n(当前没有匹配的条目)\n"
    lines = [f"## {title}", ""]
    for i, it in enumerate(items, 1):
        title_text = _clean_text(it.get("title") or it.get("originalTitle") or "(无标题)")
        link = _safe_url((it.get("links") or {}).get("aihot") or "")
        source = _clean_text(((it.get("source") or {}).get("name")) or "未知来源")
        lines.append(f"{i}. [{title_text}]({link})" if link else f"{i}. {title_text}")
        origin = _safe_url((it.get("links") or {}).get("original") or "")
        source_part = f"[{source}]({origin})" if with_source and origin else source
        lines.append(f"   - {source_part} · {display_time(it)}")
        summary = _clean_text(it.get("summary"))
        if summary:
            lines.append(f"   - {summary}")
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def render_hot(items: list) -> str:
    """渲染当前热点,保持 API 热度顺序。"""
    if not items:
        return "## 当前热点\n\n(当前没有热点数据)\n"
    lines = ["## 当前热点", ""]
    for i, it in enumerate(items, 1):
        title_text = _clean_text(it.get("title") or "(无标题)")
        src = it.get("sourceNames") or []
        n = it.get("sourceCount") or len(src)
        ts = fmt_time(it.get("latestAt"))
        lines.append(f"{i}. **{title_text}**")
        lines.append(f"   - 独立信源 {n} 个 · 最新动态 {ts}")
        links = it.get("links") or {}
        story = _safe_url(links.get("story") or "")
        if story:
            lines.append(f"   - 事件页: {story}")
        lines.append("")
    lines.append("---")
    return "\n".join(lines)


def render_daily(report: dict) -> str:
    """渲染日报:保留 sections 的 label/items 原始结构,不重排。"""
    out = []
    title = _clean_text(report.get("date") or "AI HOT 日报")
    link = _safe_url((report.get("links") or {}).get("aihot") or "")
    out.append(f"# {title} 日报" + (f" [站内阅读]({link})" if link else ""))
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
            s = _clean_text(it.get("summary"))
            if s:
                out.append(f"  {s}")
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
    """渲染日报列表。"""
    if not items:
        return "当前没有可用日报。\n"
    lines = ["可用日报:", ""]
    for it in items:
        d = _clean_text(it.get("date") or it.get("title") or "")
        link = _safe_url((it.get("links") or {}).get("aihot") or "")
        lines.append(f"- **{d}**" + (f" [阅读]({link})" if link else ""))
    lines.append("")
    lines.append("提示: 用 `daily YYYY-MM-DD` 获取指定日期完整日报。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

def _resolve_items_args(args) -> None:
    """把 today/week/search/cat/all 的语义参数归一化到 args.mode/q/category/window/limit。"""
    cmd = args.cmd
    if cmd == "search":
        args.q, args.mode, args.category = args.q, "selected", None
        if args.limit is None:
            args.limit = 8
    elif cmd == "cat":
        args.q, args.mode, args.category = None, "selected", args.category
        if args.limit is None:
            args.limit = 8
    elif cmd == "all":
        args.q, args.mode, args.category = None, "all", None
        if args.limit is None:
            args.limit = 10
    else:  # today / week
        args.q, args.mode, args.category = None, "selected", None
        if cmd == "week":
            args.window = "7d"
        if args.limit is None:
            args.limit = 10 if args.window == "7d" else 8


def cmd_items(args) -> str:
    params = {"mode": args.mode, "window": args.window, "limit": args.limit}
    if args.q:
        params["q"] = args.q
    if args.category:
        params["category"] = args.category
    if args.by:
        params["by"] = args.by
    data = fetch("/api/v1/items", params)
    items = data.get("items") or []
    fell_back = False
    # 关键词在精选池无结果时,按官方契约用相同参数再查全量池
    if args.q and args.mode == "selected" and not items:
        data = fetch("/api/v1/items", {**params, "mode": "all"})
        items = data.get("items") or []
        fell_back = True
    total = data.get("page", {}).get("count") or len(items)
    if args.q:
        head = f"“{args.q}”相关资讯({args.window} 内)"
    elif args.category:
        head = f"{CATEGORY_ZH.get(args.category, args.category)}动态({args.window} 内)"
    else:
        head = "过去 24 小时 AI 圈重点" if args.window == "24h" else "最近一周 AI 圈重点"
    if args.mode == "all":
        head = "全部公开动态" if not (args.q or args.category) else head
    body = render_items(items, head, with_source=args.with_source)
    if fell_back:
        body += "\n> 注: 精选池无匹配,以上为未进入精选的全量池结果。\n"
    return body + f"\n时间窗:{'过去 24 小时' if args.window=='24h' else '最近 7 天'} · 共 {total} 条\n"


def cmd_hot(args) -> str:
    data = fetch("/api/v1/hot-topics")
    return render_hot(data.get("items") or [])


def cmd_daily(args) -> str:
    if args.date:
        args.date = _validate_date(args.date)
        data = fetch(f"/api/v1/dailies/{args.date}")
        return render_daily(data.get("report") or {})
    # 最新日报:404 时降级到有界索引,绝不猜日期
    try:
        data = fetch("/api/v1/dailies/latest")
        return render_daily(data.get("report") or {})
    except RuntimeError as e:
        if "404" not in str(e):
            raise
        idx = fetch("/api/v1/dailies", {"limit": 7})
        items = idx.get("items") or []
        if not items:
            return "当前没有可用日报。\n"
        date = items[0].get("date")
        if not date:
            return "当前没有可用日报。\n"
        date = _validate_date(date)
        data = fetch(f"/api/v1/dailies/{date}")
        return f"(最新日报暂不可用,已取最近一份: {date})\n\n" + render_daily(data.get("report") or {})


def cmd_dailies(args) -> str:
    data = fetch("/api/v1/dailies", {"limit": args.limit or 7})
    return render_daily_index(data.get("items") or [])


def cmd_raw(args) -> str:
    """调试:直接输出原始 JSON。URL 仅限本站 https API 路径(严格校验,防 SSRF)。"""
    url = args.url
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https"
            or parsed.netloc != "aihot.virxact.com"
            or not parsed.path.startswith(API_PREFIX)):
        raise RuntimeError("raw 只接受本站 https://aihot.virxact.com/api/v1/* 完整 URL,防止 SSRF")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _OPENER.open(req, timeout=30) as resp:
        raw = resp.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("API 响应超过 5MB 上限,已中止读取")
        text = raw.decode("utf-8")
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        return text


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

ITEMS_CMDS = {"today", "week", "search", "cat", "all"}


def main() -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--window", choices=["24h", "7d"], default="24h", help="时间窗(默认 24h)")
    common.add_argument("--limit", type=_limit_type, default=None,
                        help="条数上限(1-100;默认 8,7 天窗口默认 10)")
    common.add_argument("--by", choices=["timeline", "published"], default=None, help="时间口径(默认 timeline)")
    common.add_argument("--with-source", action="store_true", help="同时附上第三方原文链接")
    common.add_argument("--json", dest="as_json", action="store_true", help="输出原始 JSON(仅 items 类命令)")

    p = argparse.ArgumentParser(
        prog="aihot",
        parents=[common],
        description="AI HOT 中文 AI 资讯查询(独立复刻版,匿名免 Key)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例:\n"
            "  aihot today              # 过去 24 小时精选\n"
            "  aihot week --limit 10    # 最近一周精选\n"
            "  aihot hot                # 当前热点\n"
            "  aihot daily              # 最新日报\n"
            "  aihot daily 2026-07-24   # 指定日期日报\n"
            "  aihot dailies            # 日报列表\n"
            "  aihot search OpenAI      # 关键词搜索\n"
            "  aihot cat paper          # 分类: ai-models/ai-products/industry/paper/tip\n"
            "  aihot all                # 全部公开动态\n"
        ),
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("today", parents=[common], help="过去 24 小时精选")
    sub.add_parser("week", parents=[common], help="最近一周精选")
    sub.add_parser("hot", parents=[common], help="当前热点")
    sp = sub.add_parser("daily", parents=[common], help="最新日报,或指定日期")
    sp.add_argument("date", nargs="?", help="YYYY-MM-DD")
    sub.add_parser("dailies", parents=[common], help="日报列表")
    sp = sub.add_parser("search", parents=[common], help="关键词搜索")
    sp.add_argument("q")
    sp = sub.add_parser("cat", parents=[common], help="按分类查询")
    sp.add_argument("category", choices=list(CATEGORY_ZH.keys()))
    sub.add_parser("all", parents=[common], help="全部公开动态")
    sp = sub.add_parser("raw", parents=[common], help="调试:输出指定 API URL 的原始响应")
    sp.add_argument("url")

    args = p.parse_args()
    cmd = args.cmd

    # items 类命令:先归一化参数;--json 直接输出原始响应,不重复请求
    if cmd in ITEMS_CMDS:
        _resolve_items_args(args)
        if args.as_json:
            data = fetch("/api/v1/items", {
                "mode": args.mode, "window": args.window, "limit": args.limit,
                **({"q": args.q} if args.q else {}),
                **({"category": args.category} if args.category else {}),
                **({"by": args.by} if args.by else {}),
            })
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0

    if cmd == "hot":
        result = cmd_hot(args)
    elif cmd == "daily":
        result = cmd_daily(args)
    elif cmd == "dailies":
        result = cmd_dailies(args)
    elif cmd == "raw":
        result = cmd_raw(args)
    else:  # today / week / search / cat / all(已在上面归一化)
        result = cmd_items(args)

    if args.as_json and cmd not in ITEMS_CMDS:
        print("提示: 该命令不支持 --json,已按文本输出。", file=sys.stderr)
    print(result)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except RuntimeError as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
