#!/usr/bin/env bash
# 自动安装 GitHub Actions 自托管 Runner 并注册到指定仓库
# 用法: bash scripts/setup-selfhosted-runner.sh <GITHUB_PAT> <OWNER>/<REPO>
set -euo pipefail

PAT="$1"
REPO="$2"  # e.g. qiri07/multi_agent_quant

WORK_DIR="/run/media/onai/MyDisk/Work/github-runner"
RUNNER_VERSION="2.331.0"

echo "=== 安装 GitHub Actions 自托管 Runner ==="
echo "仓库: $REPO"
echo "工作目录: $WORK_DIR"

# 创建目录
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

# 下载 runner
curl -sL "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
  -o runner.tar.gz
tar xzf runner.tar.gz

# 配置并注册
./bin/Config.sh \
  --url "https://github.com/${REPO}" \
  --token "${PAT}" \
  --work "work" \
  --labels "linux,x64" \
  --unattended

echo ""
echo "✅ Runner 注册成功！"
echo ""
echo "启动 Runner（前台运行，按 Ctrl+C 停止）:"
echo "  cd ${WORK_DIR} && ./run.sh"
echo ""
echo "或注册为 systemd 服务（开机自启）:"
echo "  sudo ./svc.sh install"
echo "  sudo systemctl start github-runner"
echo "  sudo systemctl enable github-runner"
