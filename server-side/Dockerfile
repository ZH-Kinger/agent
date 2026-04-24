FROM python:3.11-slim

WORKDIR /app

# 只复制服务器端代码
COPY mcp-server/ ./mcp-server/
COPY scripts/ ./scripts/

# 安装依赖
RUN pip install --no-cache-dir mcp-server/

WORKDIR /app/mcp-server

ENV PYTHONUNBUFFERED=1
ENV MCP_TRANSPORT=http
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8080/health', timeout=5)" || exit 1

CMD ["python", "server.py"]
