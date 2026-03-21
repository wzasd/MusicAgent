#!/bin/bash
# ============================================================
# Music Agent 一键部署到腾讯云脚本
# 用法：SERVER=root@YOUR_SERVER_IP bash deploy.sh
# ============================================================
set -e

SERVER="${SERVER:-root@YOUR_SERVER_IP}"
REMOTE_DIR="${REMOTE_DIR:-/app/music-agent}"

SERVER_IP=$(echo "$SERVER" | cut -d@ -f2)

echo "=========================================="
echo " 🚀 部署 Music Agent 到 $SERVER"
echo "    远程目录: $REMOTE_DIR"
echo "=========================================="

# ---------- 前置检查 ----------
if [[ "$SERVER" == *"YOUR_SERVER_IP"* ]]; then
  echo "❌ 请先设置服务器 IP，例如："
  echo "   SERVER=root@1.2.3.4 bash deploy.sh"
  exit 1
fi

if [ ! -f "setting.json" ]; then
  echo "❌ 未找到 setting.json，请先从 setting.prod.example.json 复制并填写密钥："
  echo "   cp setting.prod.example.json setting.json"
  exit 1
fi

# ---------- 步骤 1：初始化服务器环境 ----------
echo ""
echo "📦 [1/4] 检查并安装服务器 Docker 环境..."
ssh "$SERVER" 'bash -s' << 'ENDSSH'
set -e
# 安装 Docker（如已安装则跳过）
if ! command -v docker &> /dev/null; then
  echo "  安装 Docker..."
  curl -fsSL https://get.docker.com | bash
  systemctl enable docker
  systemctl start docker
fi
# 安装 docker-compose（如已安装则跳过）
if ! command -v docker-compose &> /dev/null; then
  echo "  安装 docker-compose..."
  curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
    -o /usr/local/bin/docker-compose
  chmod +x /usr/local/bin/docker-compose
fi
# 创建目标目录
mkdir -p /app/music-agent/data/chroma_db
echo "  Docker 环境就绪 ✓"
ENDSSH

# ---------- 步骤 2：同步代码 ----------
echo ""
echo "📂 [2/4] 同步代码..."
rsync -avz --progress \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.next' \
  --exclude='node_modules' \
  --exclude='data/chroma_db' \
  --exclude='data/raw' \
  --exclude='data/corpus.jsonl' \
  --exclude='data/music_corpus.jsonl' \
  --exclude='.cache' \
  . "$SERVER:$REMOTE_DIR/"
echo "  代码同步完成 ✓"

# ---------- 步骤 3：同步 ChromaDB 向量库（增量，首次较慢）----------
echo ""
echo "🗄️  [3/4] 同步 ChromaDB 向量库（增量传输，首次约 853MB）..."
rsync -avz --progress \
  data/chroma_db/ "$SERVER:$REMOTE_DIR/data/chroma_db/"
echo "  ChromaDB 同步完成 ✓"

# ---------- 步骤 4：在服务器上构建并启动容器 ----------
echo ""
echo "🐳 [4/4] 构建镜像并启动服务..."
ssh "$SERVER" "
  cd $REMOTE_DIR
  # 停止旧容器（如有）
  docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
  # 构建并后台启动
  docker-compose -f docker-compose.prod.yml up -d --build
  echo '  等待服务启动...'
  sleep 5
  docker-compose -f docker-compose.prod.yml ps
"

echo ""
echo "=========================================="
echo " ✅ 部署完成！"
echo ""
echo "   前端地址: http://$SERVER_IP:3000"
echo "   后端 API:  http://$SERVER_IP:8501"
echo "   API 文档:  http://$SERVER_IP:8501/docs"
echo ""
echo "   查看日志: ssh $SERVER 'cd $REMOTE_DIR && docker-compose -f docker-compose.prod.yml logs -f'"
echo "=========================================="
