"""Tools: trigger_release, get_workflow_status — 调用 GitHub Actions API"""
import httpx
from config import GITHUB_API, GITHUB_ORG, GITHUB_REPO, HEADERS


def trigger_release(repos_text: str, release_date: str = "", dry_run: bool = False) -> dict:
    """
    触发 release-centralized.yml workflow。

    Args:
        repos_text: 多行 repo=version 文本（workflow 的 repositories 输入）
        release_date: 发布日期 YYYY-MM-DD，留空用 workflow 默认（当天）
        dry_run: True 时 workflow 只预览不创建 PR

    Returns:
        {"ok": True, "run_url": "...", "message": "..."} 或 {"ok": False, "error": "..."}
    """
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/release-centralized.yml/dispatches"
    payload = {
        "ref": "main",
        "inputs": {
            "repositories": repos_text,
            "release_date": release_date,
            "dry_run": str(dry_run).lower(),
        },
    }
    try:
        resp = httpx.post(url, headers=HEADERS, json=payload, timeout=15)
        if resp.status_code == 404:
            return {"ok": False, "error": "workflow 文件不存在或仓库路径有误，检查 GITHUB_REPO 配置"}
        if resp.status_code == 422:
            return {"ok": False, "error": f"参数错误: {resp.text}"}
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        return {"ok": False, "error": f"HTTP {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    runs_url = f"https://github.com/{GITHUB_ORG}/{GITHUB_REPO}/actions"
    mode = "🧪 Dry run" if dry_run else "🚀 正式发布"
    return {
        "ok": True,
        "run_url": runs_url,
        "message": f"{mode} workflow 已触发，查看进度：{runs_url}",
    }


def get_workflow_status(workflow_file: str = "release-centralized.yml", limit: int = 5) -> dict:
    """
    查询最近几次 workflow run 的状态。

    Args:
        workflow_file: workflow 文件名，如 release-centralized.yml
        limit: 返回最近几条，默认 5

    Returns:
        {"ok": True, "runs": [...]} 或 {"ok": False, "error": "..."}
    """
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{GITHUB_REPO}/actions/workflows/{workflow_file}/runs"
    try:
        resp = httpx.get(url, headers=HEADERS, params={"per_page": limit}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    runs = []
    for r in data.get("workflow_runs", []):
        status = r.get("conclusion") or r.get("status", "unknown")
        emoji = {"success": "✅", "failure": "❌", "in_progress": "🔄", "cancelled": "⛔"}.get(status, "❓")
        runs.append({
            "id": r["id"],
            "status": f"{emoji} {status}",
            "created_at": r["created_at"][:16].replace("T", " "),
            "url": r["html_url"],
            "actor": r.get("actor", {}).get("login", "?"),
        })

    lines = [f"最近 {len(runs)} 次 `{workflow_file}` 运行：\n"]
    for r in runs:
        lines.append(f"- {r['status']} | {r['created_at']} | by {r['actor']} | [查看]({r['url']})")

    return {"ok": True, "runs": runs, "summary": "\n".join(lines)}