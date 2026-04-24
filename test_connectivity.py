#!/usr/bin/env python3
"""连通性测试脚本 — 逐个验证 GitHub / DashScope / Jira / 飞书 链路"""
import os
import sys
import json

# 从 .env 文件加载环境变量
def load_env(path=".env"):
    if not os.path.exists(path):
        print(f"[WARN] .env 文件不存在: {path}")
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

import httpx

results = {}

# ── 1. GitHub API ────────────────────────────────────────────
def test_github():
    token = os.environ.get("GITHUB_TOKEN", "")
    org = os.environ.get("GITHUB_ORG", "wuji-technology")
    if not token:
        return "SKIP", "未配置 GITHUB_TOKEN"
    try:
        resp = httpx.get(
            f"https://api.github.com/orgs/{org}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            return "OK", f"组织: {data.get('login')}, 公开仓库: {data.get('public_repos')}"
        elif resp.status_code == 401:
            return "FAIL", f"认证失败 (401): Token 无效或已过期"
        elif resp.status_code == 403:
            return "FAIL", f"权限不足 (403): {resp.json().get('message', '')}"
        elif resp.status_code == 404:
            return "FAIL", f"组织 {org} 不存在 (404)"
        else:
            return "FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return "FAIL", f"连接失败: {e}"

# ── 2. DashScope / Qwen API ─────────────────────────────────
def test_dashscope():
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("LLM_MODEL", "qwen-max")
    if not api_key:
        return "SKIP", "未配置 OPENAI_API_KEY"
    if not base_url:
        return "SKIP", "未配置 OPENAI_BASE_URL"
    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 32,
                "messages": [{"role": "user", "content": "请回复OK"}],
            },
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return "OK", f"模型: {model}, 回复: {content[:50]}"
        elif resp.status_code == 401:
            return "FAIL", f"认证失败 (401): API Key 无效"
        else:
            return "FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return "FAIL", f"连接失败: {e}"

# ── 3. Jira API ──────────────────────────────────────────────
def test_jira():
    jira_url = os.environ.get("JIRA_URL", "")
    jira_pat = os.environ.get("JIRA_PAT", "")
    if not jira_url:
        return "SKIP", "未配置 JIRA_URL"
    if not jira_pat:
        return "SKIP", "未配置 JIRA_PAT"
    try:
        # 用 PAT 做 Bearer 认证，测试 /rest/api/2/myself
        resp = httpx.get(
            f"{jira_url.rstrip('/')}/rest/api/2/myself",
            headers={
                "Authorization": f"Bearer {jira_pat}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            name = data.get("displayName", data.get("name", "未知"))
            return "OK", f"认证用户: {name}"
        elif resp.status_code == 401:
            return "FAIL", f"认证失败 (401): PAT 无效或已过期"
        elif resp.status_code == 403:
            return "FAIL", f"权限不足 (403)"
        else:
            return "FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return "FAIL", f"连接失败: {e}"

# ── 4. 飞书 API ──────────────────────────────────────────────
def test_feishu():
    app_id = os.environ.get("FEISHU_APP_ID", "")
    app_secret = os.environ.get("FEISHU_APP_SECRET", "")
    if not app_id or not app_secret:
        return "SKIP", "未配置 FEISHU_APP_ID / FEISHU_APP_SECRET"
    try:
        # 获取 tenant_access_token
        resp = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            token = data.get("tenant_access_token", "")
            return "OK", f"获取 tenant_access_token 成功 (token: {token[:10]}...)"
        else:
            return "FAIL", f"飞书返回错误: code={data.get('code')}, msg={data.get('msg')}"
    except Exception as e:
        return "FAIL", f"连接失败: {e}"


# ── 执行 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    tests = [
        ("GitHub API", test_github),
        ("DashScope / Qwen API", test_dashscope),
        ("Jira API", test_jira),
        ("飞书 API", test_feishu),
    ]

    print("=" * 60)
    print("  连通性测试")
    print("=" * 60)

    all_ok = True
    for name, fn in tests:
        status, msg = fn()
        icon = {"OK": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "?")
        print(f"\n{icon} [{status}] {name}")
        print(f"   {msg}")
        if status == "FAIL":
            all_ok = False

    print("\n" + "=" * 60)
    if all_ok:
        print("  🎉 所有链路测试通过！")
    else:
        print("  ⚠️  部分链路存在问题，请检查上方错误信息")
    print("=" * 60)
