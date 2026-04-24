"""Tool: fetch_changelog — 从 GitHub tag 抓取指定版本的 CHANGELOG 内容"""
import base64
import httpx
from config import GITHUB_API, GITHUB_ORG, HEADERS


def fetch_changelog(repo: str, version: str, changelog_path: str = "CHANGELOG.md") -> dict:
    """
    从指定 tag 获取 CHANGELOG 中某版本的 section。

    Args:
        repo: 仓库名，如 wujihandpy
        version: 版本号，如 1.5.0（不带 v 前缀）
        changelog_path: CHANGELOG 文件路径，默认 CHANGELOG.md

    Returns:
        {"ok": True, "content": "...", "version": "..."} 或 {"ok": False, "error": "..."}
    """
    tag = f"v{version}"
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/contents/{changelog_path}"
    try:
        resp = httpx.get(url, headers=HEADERS, params={"ref": tag}, timeout=15)
        if resp.status_code == 404:
            return {"ok": False, "error": f"tag {tag} 或 {changelog_path} 在 {repo} 中不存在"}
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    raw = base64.b64decode(data["content"]).decode("utf-8")
    section = _extract_version_section(raw, version)
    if section is None:
        return {"ok": False, "error": f"CHANGELOG 中未找到版本 {version} 的 section"}

    return {
        "ok": True,
        "repo": repo,
        "version": version,
        "content": section,
        "summary": f"## {repo} v{version}\n\n{section}",
    }


def _extract_version_section(text: str, version: str) -> str | None:
    import re
    pattern = rf"^## \[{re.escape(version)}\].*$"
    lines = text.split("\n")
    start = end = None
    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start = i + 1
        elif start is not None and re.match(r"^## \[", line):
            end = i
            break
    if start is None:
        return None
    section = "\n".join(lines[start : end or len(lines)]).strip()
    return section or None