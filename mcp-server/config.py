import json
import os
import secrets
from pathlib import Path

# ── Redis ───────────────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis_client = None


def _get_redis():
    """Lazy Redis connection (shared across process)."""
    global _redis_client
    if _redis_client is None:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


def _redis_available() -> bool:
    try:
        r = _get_redis()
        r.ping()
        return True
    except Exception:
        return False


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
REVIEWERS_FILE = os.environ.get("REVIEWERS_FILE", "")

# ── LLM (通过 OpenAI 兼容接口，支持 DashScope / Qwen-Max) ──────────────────
LLM_MODEL      = os.environ.get("LLM_MODEL", "qwen-max")
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "2048"))

# ── Jira ───────────────────────────────────────────────────────────────────
JIRA_URL       = os.environ.get("JIRA_URL", "")
JIRA_PAT       = os.environ.get("JIRA_PAT", "")
JIRA_PROJECT_KEY = os.environ.get("JIRA_PROJECT_KEY", "DEMO")
JIRA_ISSUE_TYPE  = os.environ.get("JIRA_ISSUE_TYPE", "Task")
JIRA_BASE_URL  = os.environ.get("JIRA_BASE_URL", "") or (f"{JIRA_URL}/rest/api/2" if JIRA_URL else "")
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "") or JIRA_PAT
JIRA_SYNC_TO_JIRA      = os.environ.get("JIRA_SYNC_TO_JIRA", "false").lower() == "true"
JIRA_BLOCKER_STATUS_ID = os.environ.get("JIRA_BLOCKER_STATUS_ID", "3")

JIRA_ENABLED = bool((JIRA_URL and JIRA_PAT) or (JIRA_BASE_URL and JIRA_EMAIL and JIRA_API_TOKEN))
JIRA_CACHE_TTL = int(os.environ.get("JIRA_CACHE_TTL", "300"))

# ── Feishu ─────────────────────────────────────────────────────────────────
FEISHU_WEBHOOK    = os.environ.get("FEISHU_WEBHOOK_URL", "")
FEISHU_APP_ID     = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_CHAT_ID    = os.environ.get("FEISHU_CHAT_ID", "")
FEISHU_ENABLED    = bool(FEISHU_APP_ID and FEISHU_APP_SECRET)


# ── Redis-backed storage (with file fallback) ──────────────────────────────

REDIS_KEY_TOKENS   = "wuji:repo_tokens"
REDIS_KEY_REVIEWERS = "wuji:reviewers"
REDIS_KEY_JIRA      = "wuji:jira_cache"


def _file_read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _file_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ── Repo Tokens ────────────────────────────────────────────────────────────

def _repo_tokens_path() -> Path | None:
    return Path(REPO_TOKENS_FILE) if REPO_TOKENS_FILE else None


def load_repo_tokens() -> dict[str, str]:
    # Try Redis first
    if _redis_available():
        try:
            r = _get_redis()
            data = r.hgetall(REDIS_KEY_TOKENS)
            if data:
                return data
        except Exception:
            pass
    # Fallback to file
    path = _repo_tokens_path()
    if not path:
        return {}
    data = _file_read_json(path)
    return {str(k): str(v) for k, v in data.items()}


def save_repo_tokens(tokens: dict[str, str]) -> None:
    # Save to Redis
    if _redis_available():
        try:
            r = _get_redis()
            r.delete(REDIS_KEY_TOKENS)
            if tokens:
                r.hset(REDIS_KEY_TOKENS, mapping=tokens)
        except Exception:
            pass
    # Also persist to file
    path = _repo_tokens_path()
    if path:
        _file_write_json(path, tokens)


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


# ── Reviewers ──────────────────────────────────────────────────────────────

def _reviewers_path() -> Path | None:
    return Path(REVIEWERS_FILE) if REVIEWERS_FILE else None


def load_reviewers() -> dict[str, list[dict]]:
    # Try Redis first
    if _redis_available():
        try:
            r = _get_redis()
            raw = r.get(REDIS_KEY_REVIEWERS)
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    # Fallback to file
    path = _reviewers_path()
    if not path:
        return {}
    return _file_read_json(path)


def save_reviewers(reviewers: dict[str, list[dict]]) -> None:
    # Save to Redis
    if _redis_available():
        try:
            r = _get_redis()
            r.set(REDIS_KEY_REVIEWERS, json.dumps(reviewers, ensure_ascii=False))
        except Exception:
            pass
    # Also persist to file
    path = _reviewers_path()
    if path:
        _file_write_json(path, reviewers)


def get_repo_reviewers(org: str, repo: str) -> list[dict]:
    return load_reviewers().get(f"{org}/{repo}", [])


def set_repo_reviewers(org: str, repo: str, reviewers: list[dict]) -> None:
    all_reviewers = load_reviewers()
    all_reviewers[f"{org}/{repo}"] = reviewers
    save_reviewers(all_reviewers)


# ── Jira Cache (Redis-backed) ──────────────────────────────────────────────

def get_jira_cache(issue_id: str) -> dict | None:
    if not _redis_available():
        return None
    try:
        r = _get_redis()
        raw = r.get(f"{REDIS_KEY_JIRA}:{issue_id}")
        if raw:
            return json.loads(raw)
    except Exception:
        pass
    return None


def set_jira_cache(issue_id: str, data: dict) -> None:
    if not _redis_available():
        return
    try:
        r = _get_redis()
        r.setex(f"{REDIS_KEY_JIRA}:{issue_id}", JIRA_CACHE_TTL, json.dumps(data, ensure_ascii=False))
    except Exception:
        pass


# ── Runtime Config ─────────────────────────────────────────────────────────

def public_runtime_config() -> dict:
    repo_tokens_file = _repo_tokens_path()
    redis_ok = _redis_available()
    return {
        "transport": MCP_TRANSPORT,
        "port": MCP_PORT,
        "debug_mode": DEBUG_MODE,
        "log_level": LOG_LEVEL,
        "review_token_configured": bool(REVIEW_TOKEN),
        "bootstrap_token_configured": bool(BOOTSTRAP_TOKEN),
        "repo_tokens_enabled": bool(repo_tokens_file),
        "repo_tokens_file": str(repo_tokens_file) if repo_tokens_file else "",
        "reviewers_enabled": bool(_reviewers_path()),
        "redis_available": redis_ok,
        "github_org": GITHUB_ORG,
        "jira_enabled": JIRA_ENABLED,
        "jira_sync_to_jira": JIRA_SYNC_TO_JIRA,
        "feishu_enabled": FEISHU_ENABLED,
        "llm_model": LLM_MODEL,
    }
