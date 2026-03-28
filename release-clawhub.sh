#!/bin/bash
# ============================================================
#  ClawHub Release Script - military-bidding-tracker
#  用途：将项目发布到 ClawHub（release-clawhub 孤儿分支）
#
#  发布内容：SKILL.md、milb_tracker/、pyproject.toml、README.md
#  排除内容：docs/、tests/、conftest.py、run_tests.sh、构建产物
# ============================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 颜色输出 ────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ── 检查当前分支必须为 main ─────────────────────────────────
check_main_branch() {
  local branch
  branch=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)
  [[ "$branch" == "main" ]] || error "必须在 main 分支执行，当前分支：$branch"
  success "当前分支：main"
}

# ── 主发布流程 ──────────────────────────────────────────────
release_project() {
  echo ""
  echo -e "${BLUE}════════════════════════════════════════${NC}"
  info "开始发布: military-bidding-tracker → release-clawhub"
  echo -e "${BLUE}════════════════════════════════════════${NC}"

  cd "$PROJECT_DIR" || error "目录不存在: $PROJECT_DIR"

  # 1. 暂存未提交变更，以便发布后恢复
  local stash_result
  stash_result=$(git stash push -m "release-clawhub pre-release stash" 2>&1) || true
  if echo "$stash_result" | grep -q "No local changes"; then
    info "没有未提交变更，无需暂存"
  else
    success "已暂存未提交变更"
  fi

  # 2. 删除已有 release-clawhub 分支
  if git show-ref --verify --quiet refs/heads/release-clawhub; then
    info "删除已有 release-clawhub 分支..."
    git branch -D release-clawhub
  fi

  # 3. 创建孤儿分支并清空索引
  info "创建孤儿分支 release-clawhub..."
  git checkout --orphan release-clawhub
  git rm -rf --cached . > /dev/null
  success "索引已清空"

  # 4. 删除不应发布的文件/目录
  info "清理非发布文件..."
  rm -rf \
    docs/ \
    tests/ \
    conftest.py \
    run_tests.sh \
    .env \
    .env.example \
    .gitignore \
    __pycache__ \
    milb_tracker/__pycache__ \
    milb_tracker/scripts/__pycache__ \
    milb_tracker.egg-info/ \
    milb_email.egg-info/ \
    milb_fetcher.egg-info/ \
    .pytest_cache/ \
    .coverage \
    htmlcov/ \
    release-clawhub.sh \
    2>/dev/null || true
  success "非发布文件已删除"

  # 5. 验证必要文件存在
  [[ -f "SKILL.md" ]]       || error "SKILL.md 不存在，终止发布"
  [[ -f "pyproject.toml" ]] || error "pyproject.toml 不存在，终止发布"
  [[ -d "milb_tracker" ]]   || error "milb_tracker/ 目录不存在，终止发布"
  success "必要文件验证通过"

  # 6. 验证 SKILL.md 中 install 使用 {baseDir}
  if grep -q 'install.*{baseDir}' SKILL.md; then
    success "SKILL.md install 路径使用 {baseDir}"
  else
    warn "SKILL.md 中未找到 {baseDir}，请确认 install 字段配置正确"
  fi

  # 7. 暂存发布文件并提交
  info "暂存发布文件..."
  git add SKILL.md pyproject.toml milb_tracker/
  [[ -f "README.md" ]] && git add README.md

  local version
  version=$(python3 -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(d['project']['version'])" 2>/dev/null \
            || grep '^version' pyproject.toml | head -1 | sed 's/.*= *"\(.*\)"/\1/')
  local commit_msg="release: v${version} $(date '+%Y-%m-%d')"
  git commit -m "$commit_msg"
  success "已提交：$commit_msg"

  # 8. 切回 main 并恢复暂存
  info "切回 main 分支..."
  git checkout main
  if git stash list | grep -q "release-clawhub pre-release stash"; then
    git stash pop
    success "已恢复暂存变更"
  fi

  echo ""
  echo -e "${GREEN}══════════════════════════════════════════${NC}"
  success "发布完成！release-clawhub 分支已就绪"
  echo -e "${GREEN}══════════════════════════════════════════${NC}"
  echo ""
  echo "  推送到远端："
  echo "    git push origin release-clawhub --force"
  echo ""
  echo "  ClawHub 后台刷新 release-clawhub 分支后即可看到更新。"
}

# ── 用法说明 ────────────────────────────────────────────────
usage() {
  echo ""
  echo "用法:"
  echo "  ./release-clawhub.sh            发布到 ClawHub（本地模式）"
  echo "  ./release-clawhub.sh --help     显示此帮助"
  echo ""
}

# ── 主流程 ──────────────────────────────────────────────────
case "${1:-}" in
  --help|-h) usage ;;
  "")
    check_main_branch
    release_project
    ;;
  *)
    echo "未知参数: $1"
    usage
    exit 1
    ;;
esac
