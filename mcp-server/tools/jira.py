"""Tool: jira integration — 拉取需求详情、验收标准，回写 Review 结论（支持单机缓存）"""
import os
import time
import hashlib
from functools import lru_cache
from config import (
    JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
    JIRA_ENABLED, JIRA_CACHE_TTL
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
    """Basic: base64<{email>:API {token}>"""
    import base64
    text = f"{JIRA_EMAIL}:API {JIRA_API_TOKEN}"
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
            # 回存``"{"ok": True, "data": cached, "from_cache": True}
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
    import re
    match = re.search(r"\b([A-Z]+-[A-Z0-9-]*\d+)\b", text)
    return match.group(1) if match else ""