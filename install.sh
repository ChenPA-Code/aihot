#!/usr/bin/env bash
# install.sh — 将 AIHOT 能力包安装到 Claude Code 生态(用户级 skills 目录)
# 用法:
#   bash install.sh            # 安装 Skill 包到 ~/.claude/skills/aihot/
#   bash install.sh --mcp      # 只打印 MCP Server 注册说明(不复制文件)
#   bash install.sh --all      # 安装 Skill 并打印 MCP 注册说明
set -euo pipefail

PACK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-skill}"

# 校验模式参数,非法模式直接报错(避免静默无操作)
case "$MODE" in
  skill|--mcp|--all) ;;
  *)
    echo "错误: 未知模式 '$MODE'。用法: bash install.sh [skill|--mcp|--all]" >&2
    exit 1
    ;;
esac

# --- 1. 安装 Skill 包 -------------------------------------------------------
if [ "$MODE" = "skill" ] || [ "$MODE" = "--all" ]; then
  SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
  TARGET="$SKILLS_DIR/aihot"

  # 目标已存在且非空:先备份再覆盖,避免静默丢失用户自定义修改
  if [ -d "$TARGET" ] && [ -n "$(ls -A "$TARGET" 2>/dev/null)" ]; then
    BACKUP="$TARGET.bak.$(date +%Y%m%d%H%M%S)"
    echo "[提示] 目标已存在: $TARGET"
    echo "       已自动备份到: $BACKUP"
    mv "$TARGET" "$BACKUP"
  fi

  mkdir -p "$TARGET/references" "$TARGET/scripts"

  cp "$PACK_DIR/SKILL.md" "$TARGET/SKILL.md"
  cp "$PACK_DIR/LICENSE" "$TARGET/LICENSE"
  cp "$PACK_DIR/references/api.md" "$TARGET/references/api.md"
  cp "$PACK_DIR/references/errors.md" "$TARGET/references/errors.md"
  cp "$PACK_DIR/scripts/aihot.py" "$TARGET/scripts/aihot.py"

  echo "[OK] Skill 已安装到: $TARGET"
  echo "     验证: cd $TARGET && python3 scripts/aihot.py today --limit 2"

  # 检查脚本可执行依赖
  if ! command -v python3 >/dev/null 2>&1; then
    echo "[警告] 未找到 python3,请确保目标环境有 Python 3.9+"
  fi
fi

# --- 2. 打印 MCP 注册说明 ---------------------------------------------------
if [ "$MODE" = "--mcp" ] || [ "$MODE" = "--all" ]; then
  cat <<'EOF'

[MCP] 可选接入方式(二选一,与 Skill 方式互不冲突):

  a) 项目级(推荐,随仓库共享):在项目根目录 .mcp.json 加入:
     {
       "mcpServers": {
         "aihot": {
           "command": "python3",
           "args": ["<本包绝对路径>/mcp/mcp_server.py"]
         }
       }
     }

  b) 用户级:在 ~/.claude.json 的 mcpServers 字段加入同名配置。
     或使用命令: claude mcp add aihot -- python3 <本包绝对路径>/mcp/mcp_server.py

  验证: 进入 Claude Code 后执行 /mcp 查看 aihot 是否已连接。
EOF
fi

echo ""
echo "完成。若内网无法直连 aihot.virxact.com,请参考 README.md 配置代理环境变量。"
