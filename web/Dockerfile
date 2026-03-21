FROM node:18-alpine

WORKDIR /app

# 安装依赖（先复制 package 文件利用缓存）
COPY package*.json ./
RUN npm ci

# 复制源码
COPY . .

# 构建时注入后端地址（docker-compose 通过 build args 传入）
ARG BACKEND_URL=http://localhost:8501
ENV BACKEND_URL=$BACKEND_URL

# NEXT_PUBLIC_* 变量在构建时内联，必须作为 build arg 传入
ARG NEXT_PUBLIC_API_URL=http://localhost:8501
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# 构建 Next.js
RUN npm run build

EXPOSE 3000

ENV NODE_ENV=production

CMD ["npm", "start"]
