import os

# ── GitHub ─────────────────────────────────────────────────────────────────
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
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

# ── LLM (通过 OpenAI 兼容接口，支持 DashScope / Qwen-Max) ──────────────────
LLM_MODEL      = os.environ.get("LLM_MODEL", "qwen-max")
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2048"))

# ── Jira ───────────────────────────────────────────────────────────────────
JIRA_URL       = os.environ.get("JIRA_URL", "")              # https://jira.wuji.tech
JIRA_PAT       = os.environ.get("JIRA_PAT", "")              # Personal Access Token
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "DEMO")
JIRA_ISSUE_TYPE  = os.environ.get("JIRA_ISSUE_TYPE", "Task")
# 兼容旧配置
JIRA_BASE_URL  = os.environ.get("JIRA_BASE_URL", "") or (f"{JIRA_URL}/rest/api/2" if JIRA_URL else "")
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "") or JIRA_PAT
JIRA_SYNC_TO_JIRA      = os.environ.get("JIRA_SYNC_TO_JIRA", "false").lower() == "true"
JIRA_BLOCKER_STATUS_ID = os.environ.get("JIRA_BLOCKER_STATUS_ID", "3")

# Jira 启用条件：有 URL + PAT，或者有 BASE_URL + EMAIL + API_TOKEN
JIRA_ENABLED = bool((JIRA_URL and JIRA_PAT) or (JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN))

# ── Jira issue cache ───────────────────────────────────────────────────────
JIRA_CACHE_TTL = int(os.environ.get("JIRA_CACHE_TTL", "300"))  # 默认 5 min

# ── Feishu ─────────────────────────────────────────────────────────────────
FEISHU_WEBHOOK    = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_APP_ID     = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_CHAT_ID    = os.environ.get("FEISHU_CHAT_ID", "")
FEISHU_ENABLED    = bool(FEISHU_APP_ID and FEISHU_APP_SECRET)