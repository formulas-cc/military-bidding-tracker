#!/bin/bash
# ============================================================
#  ClawHub Release Script - military-bidding-tracker
#  用途：将项目发布到 ClawHub（release-clawhub 孤儿分支）
#
#  发布内容：SKILL.md、milb_tracker/、pyproject.toml、README.md
#  排除内容：docs/、tests/、构建产物、开发配置文件
# ============================================================
set -euo pipefail

# 项目路径（当前工作空间）
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ============================================================
#  颜色输出
# ============================================================
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERR]${NC}  $*"; exit 1; }

# ============================================================
#  检查当前分支是否为 main
# ============================================================
check_main_branch() {
  info "检查当前分支..."
  local current_branch
  current_branch=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD)
  if [[ "$current_branch" != "main" ]]; then
    error "当前分支是 '$current_branch'，必须在 main 分支上执行发布脚本"
  fi
  info "当前分支: $current_branch"
  success "分支检查通过"
}

# ============================================================
#  发布项目到 ClawHub
# ============================================================
release_project() {
  echo ""
  echo -e "${BLUE}════════════════════════════════════════${NC}"
  info "开始发布: military-bidding-tracker"
  echo -e "${BLUE}════════════════════════════════════════${NC}"

  cd "$PROJECT_DIR" || error "目录不存在: $PROJECT_DIR"

  # 暂存当前未提交的变更
  info "暂存未提交的变更..."
  git stash push -m "release-clawhub pre-release stash" || true
  success "已暂存变更"

  # 若 release-clawhub 分支已存在则先删除
  if git show-ref --verify --quiet refs/heads/release-clawhub; then
    info "删除已有分支 release-clawhub ..."
    git branch -D release-clawhub
  fi

  # 创建孤儿分支并清空索引
  info "创建孤儿分支 release-clawhub ..."
  git checkout --orphan release-clawhub
  git rm -rf --cached . > /dev/null
  info "已清空 git 索引"

  # 删除不应发布的文件/目录
  info "清理非发布文件..."
  rm -rf \
    docs/ \
    tests/ \
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

  # 检查 SKILL.md 是否在根目录
  if [[ ! -f "SKILL.md" ]]; then
    error "SKILL.md 不在根目录！请检查项目结构。"
  fi
  success "SKILL.md 在根目录"

  # 验证 SKILL.md 中的 install 路径
  if grep -q 'install.*{baseDir}' SKILL.md; then
    success "SKILL.md install 路径使用 {baseDir}"
  else
    warn "SKILL.md 中未找到 {baseDir}，请确认 install 字段配置正确"
  fi

  success "孤儿分支 release-clawhub 已创建，当前处于该分支（未提交）"
}

# ============================================================
#  打印用法
# ============================================================
usage() {
  echo ""
  echo "用法:"
  echo "  ./release-clawhub.sh              # 发布到 ClawHub（本地模式）"
  echo "  ./release-clawhub.sh --help       # 显示此帮助"
  echo ""
}

# ============================================================
#  主流程
# ============================================================
case "${1:-}" in
  --help|-h)
    usage
    exit 0
    ;;
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

echo ""
echo -e "${GREEN}══════════════════════════════════════════${NC}"
success "发布完成！"
echo -e "${GREEN}══════════════════════════════════════════${NC}"
echo ""
echo "ClawHub 后台刷新 release-clawhub 分支后即可看到更新。"
