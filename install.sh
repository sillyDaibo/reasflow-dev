#!/usr/bin/env bash
set -euo pipefail

mode="local"
dev_mode=0
force=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --local)
      mode="local"
      ;;
    --global)
      mode="global"
      ;;
    --dev)
      dev_mode=1
      ;;
    --force)
      force=1
      ;;
    --help|-h)
      cat <<'EOF'
Usage: install.sh [--global] [--dev] [--force]

Default:
  install.sh
  -> local release install into the current project

Modes:
  --global  install into $HOME
  --dev     clone with git and symlink for continuous development
  --force   replace conflicting reasflow-dev targets
EOF
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

repo="${REASFLOW_DEV_REPO:-sillyDaibo/reasflow-dev}"
ref="${REASFLOW_DEV_REF:-main}"
source_override="${REASFLOW_DEV_SOURCE_DIR:-}"

if [ "$mode" = "global" ]; then
  target_root="$HOME"
  state_dir="${REASFLOW_DEV_STATE_DIR:-$HOME/.local/share/reasflow-dev}"
else
  target_root="$PWD"
  state_dir="${REASFLOW_DEV_STATE_DIR:-$target_root/.reasflow-dev}"
fi

agents_dir="$target_root/.codex/agents"
skills_dir="$target_root/.agents/skills"
manifest="$state_dir/manifest.txt"

tmp_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$tmp_dir"
}
trap cleanup EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

download_to() {
  url="$1"
  dest="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$dest"
    return
  fi
  if command -v wget >/dev/null 2>&1; then
    wget -qO "$dest" "$url"
    return
  fi
  echo "curl or wget is required" >&2
  exit 1
}

remove_previous() {
  [ -f "$manifest" ] || return 0
  while IFS= read -r line; do
    case "$line" in
      FILE\ *)
        path="${line#FILE }"
        if [ -L "$path" ] || [ -f "$path" ]; then
          rm -f "$path"
        elif [ -d "$path" ]; then
          rm -rf "$path"
        fi
        ;;
    esac
  done < "$manifest"
}

ensure_clear_target() {
  path="$1"
  if [ -e "$path" ] || [ -L "$path" ]; then
    if [ "$force" -eq 1 ]; then
      rm -rf "$path"
    else
      echo "target already exists: $path" >&2
      echo "re-run with --force to replace it" >&2
      exit 1
    fi
  fi
}

mkdir -p "$agents_dir" "$skills_dir" "$state_dir"
remove_previous

if [ -n "$source_override" ]; then
  source_dir="$(cd "$source_override" && pwd)"
elif [ "$dev_mode" -eq 1 ]; then
  need_cmd git
  source_dir="$state_dir/source"
  if [ ! -d "$source_dir/.git" ]; then
    git clone "https://github.com/$repo.git" "$source_dir" >/dev/null 2>&1
  fi
  git -C "$source_dir" fetch --tags origin >/dev/null 2>&1
  git -C "$source_dir" checkout "$ref" >/dev/null 2>&1
  if git -C "$source_dir" rev-parse --verify "origin/$ref" >/dev/null 2>&1; then
    git -C "$source_dir" pull --ff-only origin "$ref" >/dev/null 2>&1
  fi
else
  need_cmd tar
  archive="$tmp_dir/reasflow-dev.tar.gz"
  download_to "https://codeload.github.com/$repo/tar.gz/$ref" "$archive"
  tar -xzf "$archive" -C "$tmp_dir"
  source_dir="$(find "$tmp_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
fi

[ -d "$source_dir/skills" ] || {
  echo "invalid source: missing skills directory" >&2
  exit 1
}
[ -d "$source_dir/agents" ] || {
  echo "invalid source: missing agents directory" >&2
  exit 1
}

manifest_tmp="$tmp_dir/manifest.txt"
: > "$manifest_tmp"
printf 'MODE %s\n' "$( [ "$dev_mode" -eq 1 ] && echo dev || echo release )" >> "$manifest_tmp"
printf 'SCOPE %s\n' "$mode" >> "$manifest_tmp"
printf 'SOURCE %s\n' "$source_dir" >> "$manifest_tmp"

for skill_path in "$source_dir"/skills/*; do
  [ -d "$skill_path" ] || continue
  skill_name="$(basename "$skill_path")"
  dest="$skills_dir/$skill_name"
  ensure_clear_target "$dest"
  if [ "$dev_mode" -eq 1 ]; then
    ln -s "$skill_path" "$dest"
  else
    cp -R "$skill_path" "$dest"
  fi
  printf 'FILE %s\n' "$dest" >> "$manifest_tmp"
done

for agent_path in "$source_dir"/agents/*.toml; do
  [ -f "$agent_path" ] || continue
  agent_name="$(basename "$agent_path")"
  dest="$agents_dir/$agent_name"
  ensure_clear_target "$dest"
  if [ "$dev_mode" -eq 1 ]; then
    ln -s "$agent_path" "$dest"
  else
    cp "$agent_path" "$dest"
  fi
  printf 'FILE %s\n' "$dest" >> "$manifest_tmp"
done

cp "$manifest_tmp" "$manifest"

skill_count="$(find "$skills_dir" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
agent_count="$(find "$agents_dir" -mindepth 1 -maxdepth 1 -type f -name '*.toml' | wc -l | tr -d ' ')"

echo "Installed reasflow-dev"
echo "  scope: $mode"
echo "  mode: $( [ "$dev_mode" -eq 1 ] && echo dev || echo release )"
echo "  skills: $skill_count -> $skills_dir"
echo "  agents: $agent_count -> $agents_dir"
echo "  manifest: $manifest"
