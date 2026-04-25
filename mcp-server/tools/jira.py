"""Tool: jira integration — 拉取需求详情、自动创建工单、回写 Review 结论（支持单机缓存）"""
import os
import re
import time
import hashlib
from config import (
    JIRA_URL, JIRA_PAT, JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
    JIRA_ENABLED, JIRA_CACHE_TTL, JIRA_PROJECT_KEY, JIRA_ISSUE_TYPE
)
import httpx


# ── 缓存层 ──────────────────────────────────────────────────────────────────
# 单机内存缓存：K=Jira ID + 时间窗口，V=issue data dict
jira_cache = {}

def _cache_key(issue_id: str) -> str:
    """带时间窗口的缓存键：JIRA-123 + 5min_ttl_window"""
    window = int(time.time() / JIRA_CACHE_TTL)
    return f"{issue_id}:{window}"

def _invalidate_cache():
    """清理过期缓存（定时任务可调用）"""
    now = time.time()
    global jira_cache
    # 简单实现：清空。生产环境可改为写时打 timestamp + 读时判断过期
    jira_cache.clear()


# ── 客户端 ───────────────────────────────────────────────────────────────────

def _get_auth_header():
    """根据配置选择认证方式：PAT (Bearer) 或 Basic (email:token)"""
    if JIRA_PAT:
        return f"Bearer {JIRA_PAT}"
    import base64
    text = f"{JIRA_EMAIL}:{JIRA_API_TOKEN}"
    return f"Basic {base64.b64encode(text.encode()).decode()}"


def fetch_jira_issue(issue_id: str, force_refresh: bool = False) -> dict:
    """
    拉取 Jira 单子的详情（带缓存，每 5min 刷新一次）

    Args:
        issue_id: PROJ-123
        force_refresh: 忽略缓存（开发调试用）

    Returns:
        {"ok": True, "data": {...}} 或 {"ok": False, "error": "..."}
    """
    if not JIRA_ENABLED:
        return {"ok": False, "error": "服务器未启用 Jira（缺 JIRA_BASE_URL/EMAIL/API_TOKEN 之一）"}

    if not issue_id:
        return {"ok": False, "error": "未提供 Jira 问题编号"}

    if not force_refresh:
        key = _cache_key(issue_id)
        if key in jira_cache:
            cached = jira_cache[key]
            return {"ok": True, "data": cached, "from_cache": True}

    headers = {
        "Authorization": _get_auth_header(),
        "Accept": "application/json",
    }

    # fields 中用 alias：acceptance%20criteria → AC
    fields = "summary,description,status,assignee,acceptance%20criteria,test%20notes"
    url = f"{JIRA_BASE_URL.rstrip('/')}/issue/{issue_id}?fields={fields}"

    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        fields_dict = data.get("fields", {})
        payload = {
            "summary": fields_dict.get("summary", ""),
            "description": fields_dict.get("description", ""),
            "acceptance_criteria": fields_dict.get("acceptance criteria", ""),
            "test_notes": fields_dict.get("test notes", "无测试备注"),
            "status": fields_dict.get("status", {}).get("name", "未知状态"),
            "assignee": fields_dict.get("assignee", {}).get("displayName", "未分配"),
        }

        # 写入缓存
        cached_key = _cache_key(issue_id)
        jira_cache[cached_key] = payload

        return {"ok": True, "data": payload, "from_cache": False}
    except Exception as e:
        return {"ok": False, "error": f"拉取 Jira 失败：{e}"}


def update_jira_status(issue_id: str, new_status_id: str, comment: str = "") -> dict:
    """更新 Jira 状态（状态变更会失效缓存）"""
    if not JIRA_ENABLED:
        return {"ok": False, "error": "未配置 Jira 凭证"}

    headers = {
        "Authorization": _get_auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{JIRA_BASE_URL.rstrip('/')}/issue/{issue_id}"
    payload = {"update": {"status": {"set": {"id": new_status_id}}}}

    try:
        resp = httpx.patch(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()

        if comment:
            add_jira_comment(issue_id, comment)

        # 状态变了，清空缓存
        _invalidate_cache()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"更新 Jira 失败：{e}"}


def add_jira_comment(issue_id: str, body: str) -> dict:
    """追加 Jira 评论"""
    if not JIRA_ENABLED:
        return {"ok": False, "error": "未配置 Jira 凭证"}

    headers = {
        "Authorization": _get_auth_header(),
        "Content-Type": "application/json",
    }
    url = f"{JIRA_BASE_URL.rstrip('/')}/issue/{issue_id}/comment"
    try:
        resp = httpx.post(url, headers=headers, json={"body": body}, timeout=30)
        resp.raise_for_status()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_jira_id_from_text(text: str) -> str:
    """正则 [A-Z]+-\d+（如 JIRA-123, PROJ-456）"""
    match = re.search(r"\b([A-Z]+-[A-Z0-9-]*\d+)\b", text)
    return match.group(1) if match else ""


def create_jira_issue(title: str, body: str, pr_url: str, repo: str = "") -> dict:
    """
    从 PR 信息自动创建 Jira 工单。

    PR 标题 feat → Story，fix → Bug，其余 → Task。

    Args:
        title: PR 标题（如 feat(detection): add grasp module）
        body: PR 描述
        pr_url: PR 链接
        repo: 仓库名

    Returns:
        {"ok": True, "issue_id": "DEMO-123", "issue_url": "..."} 或 {"ok": False, "error": "..."}
    """
    if not JIRA_ENABLED:
        return {"ok": False, "error": "Jira 未启用"}

    # 统一使用配置的工单类型（避免项目不支持 Story/Bug 导致 400 错误）
    issue_type = JIRA_ISSUE_TYPE  # 默认 Task

    # 清理标题：去掉 type(scope): 前缀，保留描述
    clean_title = re.sub(r"^\w+(\(.+?\))?!?:\s*", "", title).strip() or title
    summary = f"[{repo}] {clean_title}" if repo else clean_title

    description = (
        f"h3. PR 信息\n"
        f"*仓库*: {repo}\n"
        f"*标题*: {title}\n"
        f"*链接*: {pr_url}\n\n"
        f"h3. PR 描述\n"
        f"{body or '（无描述）'}\n\n"
        f"---\n"
        f"自动创建自 PR Pipeline"
    )

    headers = {
        "Authorization": _get_auth_header(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "summary": summary,
            "description": description,
            "issuetype": {"name": issue_type},
        }
    }

    url = f"{JIRA_BASE_URL.rstrip('/')}/issue"
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issue_key = data.get("key", "")
        issue_url = f"{JIRA_URL}/browse/{issue_key}" if JIRA_URL else ""
        return {"ok": True, "issue_id": issue_key, "issue_url": issue_url, "issue_type": issue_type}
    except Exception as e:
        return {"ok": False, "error": f"创建 Jira 工单失败：{e}"}