import os

# ── GitHub ─────────────────────────────────────────────────────────────────
GITHUB_TOKEN   = os.environ["GITHUB_TOKEN"]
GITHUB_ORG     = os.environ.get("GITHUB_ORG", "wuji-technology")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", ".github")
GITHUB_API     = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# ── MCP Server ─────────────────────────────────────────────────────────────
MCP_PORT       = int(os.environ.get("MCP_PORT", "8080"))
REVIEW_TOKEN   = os.environ.get("REVIEW_TOKEN", "")

# ── Feishu ─────────────────────────────────────────────────────────────────
FEISHU_WEBHOOK = os.environ.get("FEISHU_WEBHOOK_URL", "")

# ── LLM (通过 OpenAI 兼容接口，支持 DashScope / Qwen-Max) ──────────────────
LLM_MODEL      = os.environ.get("LLM_MODEL", "qwen-max")
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2048"))

# ── Jira ───────────────────────────────────────────────────────────────────
JIRA_BASE_URL  = os.environ.get("JIRA_BASE_URL", "")         # https://company.atlassian.net/rest/api/3
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_SYNC_TO_JIRA      = os.environ.get("JIRA_SYNC_TO_JIRA", "false").lower() == "true"
JIRA_BLOCKER_STATUS_ID = os.environ.get("JIRA_BLOCKER_STATUS_ID", "3")

JIRA_ENABLED = bool(JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN)

# ── Jira issue cache ───────────────────────────────────────────────────────
# TTL (seconds): Jira 单子数据在 server 进程内缓存多久
JIRA_CACHE_TTL = int(os.environ.get("JIRA_CACHE_TTL", "300"))  # 默认 5 min