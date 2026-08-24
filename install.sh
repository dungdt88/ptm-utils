#!/bin/bash
# Install (or upgrade) ptm-utils: the ptmutils CLI and the agent skills.
# Safe to re-run — that is also how you upgrade:
#
#   git pull && ./install.sh
#
# Usage: ./install.sh [options]
#   (no options)     install or upgrade everything
#   --check          verify the installation and change nothing
#   --no-skills      do not link the agent skills
#   --universal      link skills into ~/.agents/skills/ instead of ~/.claude/skills/
#   --method M       force uv | pip (default: auto-detect, prefers uv)
#   -h, --help       show this help
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="ptmutils"
PYTHON_VERSION="3.11" # must satisfy requires-python in pyproject.toml
CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/ptm"

CHECK_ONLY=0
LINK_SKILLS=1
SKILLS_DST="$HOME/.claude/skills"
METHOD=""

while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=1 ;;
        --no-skills) LINK_SKILLS=0 ;;
        --universal) LINK_SKILLS=1; SKILLS_DST="$HOME/.agents/skills" ;;
        --method) METHOD="${2:-}"; shift ;;
        -h|--help) awk 'NR>1 && /^#/ {sub(/^# ?/, ""); print; next} NR>1 {exit}' "$0"
                   exit 0 ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 1 ;;
    esac
    shift
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; }
step() { printf '\n\033[1m%s\033[0m\n' "$1"; }

[ -f "$DIR/pyproject.toml" ] || { echo "Run this from the ptm-utils checkout." >&2; exit 1; }

# ---------------------------------------------------------------- check mode
if [ "$CHECK_ONLY" -eq 1 ]; then
    step "Command"
    if command -v "$TOOL" >/dev/null 2>&1 && "$TOOL" --help >/dev/null 2>&1; then
        ok "$TOOL -> $(command -v "$TOOL")"
    else
        bad "$TOOL not on PATH or failing to run (try: ./install.sh)"
    fi

    step "Contexts"
    if command -v "$TOOL" >/dev/null 2>&1; then
        "$TOOL" contexts 2>&1 | sed 's/^/  /'
    fi

    step "Skills"
    for skill in "$DIR"/skills/*/; do
        name="$(basename "$skill")"
        if [ -L "$SKILLS_DST/$name" ]; then ok "$name linked"; else warn "$name not linked"; fi
    done
    exit 0
fi

# ------------------------------------------------------------------- install
step "Installing $TOOL"

if [ -z "$METHOD" ]; then
    if command -v uv >/dev/null 2>&1; then METHOD="uv"; else METHOD="pip"; fi
fi

case "$METHOD" in
    uv)
        uv tool install --force --python "$PYTHON_VERSION" --editable "$DIR"
        ok "installed with uv (editable)"
        ;;
    pip)
        python3 -m pip install --user --upgrade --editable "$DIR"
        ok "installed with pip --user (editable)"
        ;;
    *)
        echo "Unknown method '$METHOD' (use uv or pip)" >&2; exit 1 ;;
esac

if ! command -v "$TOOL" >/dev/null 2>&1; then
    warn "$TOOL is installed but not on PATH — add the install bin dir to PATH"
fi

# --------------------------------------------------------------------- skills
if [ "$LINK_SKILLS" -eq 1 ]; then
    step "Linking agent skills into $SKILLS_DST"
    mkdir -p "$SKILLS_DST"
    for skill in "$DIR"/skills/*/; do
        name="$(basename "$skill")"
        [ -f "$skill/SKILL.md" ] || continue
        ln -sfn "${skill%/}" "$SKILLS_DST/$name"
        ok "$name"
    done
fi

# --------------------------------------------------------------------- config
step "Configuration"
mkdir -p "$CONFIG_HOME"
if [ ! -f "$CONFIG_HOME/ptm.env" ]; then
    cp "$DIR/ptm.env.example" "$CONFIG_HOME/ptm.env"
    ok "wrote $CONFIG_HOME/ptm.env (everything in it is optional)"
else
    ok "$CONFIG_HOME/ptm.env already exists — left alone"
fi

if [ -f "$CONFIG_HOME/contexts.yaml" ]; then
    ok "context registry: $CONFIG_HOME/contexts.yaml"
else
    warn "no contexts registered yet"
fi

step "Next"
cat <<'EOF'
  1. Register a vault per context (create the folder first, or let Obsidian):
       ptmutils context add work --vault ~/Documents/vaults/work     --name "Work"
       ptmutils context add priv --vault ~/Documents/vaults/personal --name "Personal"
  2. Scaffold this month's pages and the Obsidian dashboards:
       ptmutils init --all
  3. Open each vault in Obsidian and install the Dataview plugin.
  4. Capture something:
       ptmutils task "Fix login redirect" --due 2026-08-30
       ptmutils note --title "Sprint planning" --body "..."
EOF
