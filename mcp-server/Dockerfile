FROM python:3.11-slim

WORKDIR /app

# 复制整个仓库（server 需要 scripts/ 目录）
COPY . .

RUN pip install --no-cache-dir -e mcp-server/

WORKDIR /app/mcp-server

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
EXPOSE 8080

CMD ["python", "server.py"]