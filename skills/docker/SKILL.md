---
description: "Docker 容器与 Docker Compose 常用操作"
nanobot:
  always: false
  requires:
    bins: ["docker"]
---

# Docker 操作指南

## 镜像管理

```bash
docker images                        # 列出本地镜像
docker pull nginx:alpine             # 拉取镜像
docker build -t myapp:1.0 .          # 构建镜像
docker tag myapp:1.0 registry/myapp:1.0  # 打标签
docker push registry/myapp:1.0       # 推送镜像
docker rmi $(docker images -f "dangling=true" -q)  # 清理悬空镜像
```

## 容器操作

```bash
docker ps -a                         # 列出所有容器
docker run -d --name app -p 8080:80 nginx  # 后台运行
docker run --rm -it ubuntu bash      # 交互式运行（用完即删）
docker exec -it <container> bash     # 进入运行中容器
docker logs -f --tail=100 <container>  # 实时查看日志
docker stop <container>              # 优雅停止
docker rm -f <container>             # 强制删除
```

## Docker Compose

```yaml
# docker-compose.yml 示例
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=sqlite:///./data/app.db
    volumes:
      - ./data:/app/data
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_PASSWORD: secret
    volumes:
      - pgdata:/var/lib/postgresql/data

volumes:
  pgdata:
```

```bash
docker compose up -d                 # 后台启动所有服务
docker compose up -d --build         # 重新构建并启动
docker compose logs -f app           # 实时查看指定服务日志
docker compose down -v               # 停止并删除卷
docker compose exec app bash         # 进入服务容器
docker compose ps                    # 查看服务状态
```

## Dockerfile 最佳实践

```dockerfile
# 多阶段构建示例（Python）
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install --user -e .

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

关键原则：
- 使用 `-slim` 或 `alpine` 基础镜像减小体积
- 将不常变的层（依赖安装）放前面，充分利用缓存
- 使用 `.dockerignore` 排除 `.venv/`、`__pycache__/`、`node_modules/`

## 资源与排查

```bash
docker stats                         # 实时资源使用
docker inspect <container>           # 查看容器详情（JSON）
docker system df                     # 磁盘使用统计
docker system prune -af              # 清理所有未使用资源
```
