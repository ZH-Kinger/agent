"""Tools: get_current_versions, suggest_next_version — 版本查询与自动推断"""
import re
import base64
import httpx
from config import GITHUB_API, GITHUB_ORG, HEADERS

# Unreleased 各 section 对应的 semver bump 级别（优先级从高到低）
_BUMP_RULES = [
    ("major", re.compile(r"^### (?:Removed|移除|Breaking|破坏性)", re.IGNORECASE | re.MULTILINE)),
    ("minor", re.compile(r"^### (?:Added|新增)", re.IGNORECASE | re.MULTILINE)),
    ("patch", re.compile(r"^### (?:Fixed|修复|Changed|变更|Security|安全|Deprecated|废弃)", re.IGNORECASE | re.MULTILINE)),
]


def get_current_versions(repos: list[str] | None = None) -> dict:
    """
    查询各仓库当前已发布的最新版本。

    优先从 GitHub Releases API 获取（权威、快速）；
    若仓库无 Release，回退到读 CHANGELOG.md 第一个版本号。

    Args:
        repos: 仓库名列表，如 ["wujihandpy", "wujihandros2"]。
               留空则自动列出组织下所有有 Release 的仓库。

    Returns:
        {
          "ok": True,
          "versions": {"wujihandpy": {"version": "1.5.0", "date": "2026-04-23", "url": "..."}},
          "summary": "..."
        }
        或 {"ok": False, "error": "..."}
    """
    try:
        if repos:
            target_repos = repos
        else:
            target_repos = _list_org_repos()
    except Exception as e:
        return {"ok": False, "error": f"获取仓库列表失败: {e}"}

    if not target_repos:
        return {"ok": False, "error": "未找到任何仓库"}

    results = {}
    errors = []

    for repo in target_repos:
        info = _get_repo_version(repo)
        if info:
            results[repo] = info
        else:
            errors.append(repo)

    if not results:
        return {"ok": False, "error": f"所有仓库均未找到版本信息: {', '.join(errors)}"}

    summary = _format_summary(results, errors)
    return {"ok": True, "versions": results, "summary": summary}


def _list_org_repos() -> list[str]:
    """列出组织下所有有 Release 的仓库名。"""
    repos = []
    page = 1
    while True:
        url = f"{GITHUB_API}/orgs/{GITHUB_ORG}/repos"
        resp = httpx.get(url, headers=HEADERS, params={"per_page": 100, "page": page, "type": "all"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            break
        repos.extend(r["name"] for r in data if not r.get("archived"))
        if len(data) < 100:
            break
        page += 1
    return repos


def _get_repo_version(repo: str) -> dict | None:
    """
    先查 GitHub Latest Release，失败则解析 CHANGELOG.md。
    返回 {"version": "1.5.0", "date": "2026-04-23", "url": "...", "source": "release|changelog"}
    或 None。
    """
    # 优先：GitHub Latest Release API
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/releases/latest"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            tag = data.get("tag_name", "")
            version = tag.lstrip("v")
            published = (data.get("published_at") or "")[:10]
            return {
                "version": version,
                "date": published,
                "url": data.get("html_url", ""),
                "source": "release",
            }
    except Exception:
        pass

    # 回退：解析 CHANGELOG.md 第一个版本号
    try:
        cl_url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/contents/CHANGELOG.md"
        resp = httpx.get(cl_url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            content = base64.b64decode(resp.json()["content"]).decode("utf-8")
            match = re.search(
                r"^## \[(\d+\.\d+\.\d+[^\]]*)\](?:\s*-\s*(\d{4}-\d{2}-\d{2}))?",
                content,
                re.MULTILINE,
            )
            if match:
                version = match.group(1)
                date = match.group(2) or ""
                compare_url = f"https://github.com/{GITHUB_ORG}/{repo}/blob/main/CHANGELOG.md"
                return {
                    "version": version,
                    "date": date,
                    "url": compare_url,
                    "source": "changelog",
                }
    except Exception:
        pass

    return None


def suggest_next_version(repo: str, changelog_path: str = "CHANGELOG.md") -> dict:
    """
    根据当前版本 + Unreleased section 内容，自动推断下一个版本号。

    推断规则（semver）：
      - Unreleased 含 Removed / Breaking → major bump
      - Unreleased 含 Added / 新增       → minor bump
      - 其余（Fixed / Changed 等）        → patch bump
      - Unreleased 为空                   → patch bump（默认）

    Args:
        repo: 仓库名，如 wujihandpy
        changelog_path: CHANGELOG 路径，默认 CHANGELOG.md

    Returns:
        {
          "ok": True,
          "current": "1.5.0",
          "next": "1.6.0",
          "bump": "minor",
          "reason": "Unreleased 包含 Added（新功能）",
          "unreleased": "...",   # Unreleased section 原文
          "summary": "..."
        }
    """
    # 1. 获取当前版本
    info = _get_repo_version(repo)
    if info is None:
        return {"ok": False, "error": f"无法获取 {repo} 的当前版本"}
    current = info["version"]

    # 2. 读取 main 分支上的 CHANGELOG
    url = f"{GITHUB_API}/repos/{GITHUB_ORG}/{repo}/contents/{changelog_path}"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=10)
        if resp.status_code == 404:
            return {"ok": False, "error": f"{repo} 中未找到 {changelog_path}"}
        resp.raise_for_status()
        content = base64.b64decode(resp.json()["content"]).decode("utf-8")
    except Exception as e:
        return {"ok": False, "error": f"读取 CHANGELOG 失败: {e}"}

    # 3. 提取 Unreleased section
    unreleased = _extract_unreleased(content)

    # 4. 推断 bump 类型
    bump, reason = _infer_bump(unreleased)

    # 5. 计算下一个版本
    next_version = _bump_version(current, bump)
    if next_version is None:
        return {"ok": False, "error": f"无法解析版本号格式: {current}"}

    summary = (
        f"**{repo}** 版本推断\n\n"
        f"- 当前版本: v{current}\n"
        f"- 推断类型: **{bump}** bump\n"
        f"- 原因: {reason}\n"
        f"- 建议下一版本: **v{next_version}**\n"
    )
    if unreleased:
        summary += f"\nUnreleased 内容预览:\n```\n{unreleased[:500]}\n```"
    else:
        summary += "\n⚠️ Unreleased section 为空，请先补充变更内容。"

    return {
        "ok": True,
        "current": current,
        "next": next_version,
        "bump": bump,
        "reason": reason,
        "unreleased": unreleased,
        "summary": summary,
    }


def _extract_unreleased(content: str) -> str:
    """提取 CHANGELOG 中 Unreleased section 的内容。"""
    lines = content.split("\n")
    in_section = False
    result = []
    for line in lines:
        if re.match(r"^## (?:\[)?(?:Unreleased|未发布)(?:\])?", line, re.IGNORECASE):
            in_section = True
            continue
        if in_section and re.match(r"^## ", line):
            break
        if in_section:
            result.append(line)
    return "\n".join(result).strip()


def _infer_bump(unreleased: str) -> tuple[str, str]:
    """根据 Unreleased 内容推断 bump 类型，返回 (bump, reason)。"""
    if not unreleased:
        return "patch", "Unreleased 为空，默认 patch"
    for bump, pattern in _BUMP_RULES:
        match = pattern.search(unreleased)
        if match:
            section = match.group(0).strip().lstrip("### ")
            return bump, f"Unreleased 包含「{section}」"
    return "patch", "Unreleased 仅含次要变更，默认 patch"


def _bump_version(version: str, bump: str) -> str | None:
    """对版本号执行 major/minor/patch bump，忽略预发布后缀。"""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return None
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def _format_summary(results: dict, errors: list[str]) -> str:
    lines = [f"📦 {GITHUB_ORG} 各仓库当前版本\n"]
    for repo, info in sorted(results.items()):
        source_tag = "" if info["source"] == "release" else " *(changelog)*"
        date_str = f"  {info['date']}" if info["date"] else ""
        lines.append(f"- **{repo}**: v{info['version']}{date_str}{source_tag}")

    if errors:
        lines.append(f"\n⚠️ 未找到版本信息: {', '.join(errors)}")

    return "\n".join(lines)