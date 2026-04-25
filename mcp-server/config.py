import json
import os
import secrets
from pathlib import Path

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
MCP_TRANSPORT  = os.environ.get("MCP_TRANSPORT", "stdio")
MCP_PORT       = int(os.environ.get("MCP_PORT", "8080"))
REVIEW_TOKEN   = os.environ.get("REVIEW_TOKEN", "")
BOOTSTRAP_TOKEN = os.environ.get("BOOTSTRAP_TOKEN", "")
LOG_LEVEL      = os.environ.get("LOG_LEVEL", "INFO").upper()
DEBUG_MODE     = os.environ.get("DEBUG_MODE", "false").lower() == "true"
REPO_TOKENS_FILE = os.environ.get("REPO_TOKENS_FILE", "")

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


def _repo_tokens_path() -> Path | None:
    if not REPO_TOKENS_FILE:
        return None
    return Path(REPO_TOKENS_FILE)


def load_repo_tokens() -> dict[str, str]:
    path = _repo_tokens_path()
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items()}


def save_repo_tokens(tokens: dict[str, str]) -> None:
    path = _repo_tokens_path()
    if not path:
        raise RuntimeError("REPO_TOKENS_FILE is not configured")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tokens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def issue_repo_token(org: str, repo: str) -> str:
    repo_key = f"{org}/{repo}"
    tokens = load_repo_tokens()
    token = tokens.get(repo_key)
    if token:
        return token
    token = f"wr_{secrets.token_urlsafe(24)}"
    tokens[repo_key] = token
    save_repo_tokens(tokens)
    return token


def get_repo_token(org: str, repo: str) -> str:
    return load_repo_tokens().get(f"{org}/{repo}", "")


def public_runtime_config() -> dict:
    repo_tokens_file = _repo_tokens_path()
    return {
        "transport": MCP_TRANSPORT,
        "port": MCP_PORT,
        "debug_mode": DEBUG_MODE,
        "log_level": LOG_LEVEL,
        "review_token_configured": bool(REVIEW_TOKEN),
        "bootstrap_token_configured": bool(BOOTSTRAP_TOKEN),
        "repo_tokens_enabled": bool(repo_tokens_file),
        "repo_tokens_file": str(repo_tokens_file) if repo_tokens_file else "",
        "github_org": GITHUB_ORG,
        "jira_enabled": JIRA_ENABLED,
        "jira_sync_to_jira": JIRA_SYNC_TO_JIRA,
        "feishu_enabled": FEISHU_ENABLED,
        "llm_model": LLM_MODEL,
    }
