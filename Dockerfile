FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖（先复制 requirements.txt 利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（chroma_db 通过 volume 挂载，不打包进镜像）
COPY . .

# 确保数据目录存在
RUN mkdir -p data/chroma_db

EXPOSE 8501

CMD ["python", "run_api_server.py"]
