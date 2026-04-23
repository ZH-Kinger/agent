#!/usr/bin/env python3
"""
从各仓库获取指定版本的 CHANGELOG 内容

使用 GitHub API 从 tag 获取 CHANGELOG.md 文件，
解析 Keep a Changelog 格式并提取指定版本的 section。

输入: parse-repos.py 的 JSON 输出 (stdin)
输出: 包含各仓库 CHANGELOG 内容的 JSON (stdout)
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request


ORG = "wuji-technology"


def github_api(endpoint, token):
    """调用 GitHub API"""
    url = f"https://api.github.com{endpoint}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "release-notes-automation",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def fetch_changelog_from_tag(repo, version, changelog_path, token):
    """
    从指定 tag 获取 CHANGELOG 文件内容

    Args:
        repo: 仓库名
        version: 版本号 (不含 v 前缀)
        changelog_path: CHANGELOG 文件路径
        token: GitHub token

    Returns:
        CHANGELOG 文件的原始文本，或 None
    """
    tag = f"v{version}"
    endpoint = f"/repos/{ORG}/{repo}/contents/{changelog_path}?ref={tag}"
    data = github_api(endpoint, token)
    if data is None:
        print(f"⚠️  {repo}: tag {tag} 或 {changelog_path} 不存在", file=sys.stderr)
        return None

    content = data.get("content", "")
    encoding = data.get("encoding", "")
    if encoding == "base64":
        try:
            return base64.b64decode(content).decode("utf-8")
        except UnicodeDecodeError:
            print(f"⚠️  {repo}: CHANGELOG 非 UTF-8，已跳过", file=sys.stderr)
            return None

    print(f"⚠️  {repo}: 未知编码格式 {encoding}", file=sys.stderr)
    return None


def extract_version_section(changelog_text, version):
    """
    从 Keep a Changelog 格式的文本中提取指定版本的 section

    匹配格式: ## [X.Y.Z] - YYYY-MM-DD 或 ## [X.Y.Z]
    提取从该 heading 到下一个 ## heading 之间的所有内容

    Args:
        changelog_text: CHANGELOG 全文
        version: 目标版本号 (不含 v 前缀)

    Returns:
        该版本的 changelog 内容 (不含 heading 本身)，或 None
    """
    # 匹配 ## [version] 或 ## [version] - date
    escaped_version = re.escape(version)
    pattern = rf"^## \[{escaped_version}\].*$"

    lines = changelog_text.split("\n")
    start_idx = None
    end_idx = None

    for i, line in enumerate(lines):
        if re.match(pattern, line):
            start_idx = i + 1
        elif start_idx is not None and re.match(r"^## \[", line):
            end_idx = i
            break

    if start_idx is None:
        return None

    if end_idx is None:
        end_idx = len(lines)

    section = "\n".join(lines[start_idx:end_idx]).strip()
    return section if section else None


def flatten_changelog(section_text):
    """
    将 Keep a Changelog 的分类格式（Added/Fixed/Changed 等）
    扁平化为统一列表

    Args:
        section_text: 版本 section 文本

    Returns:
        扁平化后的 markdown 列表文本
    """
    items = []
    for line in section_text.split("\n"):
        stripped = line.strip()
        # 跳过分类标题 (### Added, ### Fixed 等)
        if stripped.startswith("### "):
            continue
        # 跳过空行
        if not stripped:
            continue
        items.append(line)

    return "\n".join(items)


def main():
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("❌ 错误: 需要设置 GITHUB_TOKEN 环境变量", file=sys.stderr)
        sys.exit(1)

    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), "release-notes-config.json")
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    # 从 stdin 读取仓库列表 (parse-repos.py 的输出格式)
    repos_input = json.loads(sys.stdin.read())

    results = []
    for item in repos_input:
        repo = item["repo"]
        version = item["version"]

        # 从配置中获取组件信息
        component = config["components"].get(repo)
        if component is None:
            print(f"⚠️  {repo}: 未在 release-notes-config.json 中配置，跳过", file=sys.stderr)
            continue

        changelog_path = component.get("changelog_path")
        # 允许输入覆盖默认 changelog_path
        if item.get("changelog_path") and item["changelog_path"] != "CHANGELOG.md":
            changelog_path = item["changelog_path"]

        entry = {
            "repo": repo,
            "version": version,
            "display_name_zh": component["display_name_zh"],
            "display_name_en": component["display_name_en"],
            "public_repo": component.get("public_repo"),
            "update_method_zh": component.get("update_method_zh", ""),
            "update_method_en": component.get("update_method_en", ""),
            "order": component.get("order", 99),
            "changelog": None,
        }

        # firmware 等无仓库组件跳过抓取
        if changelog_path is None:
            print(f"ℹ️  {repo}: 无 CHANGELOG 路径，跳过抓取", file=sys.stderr)
            results.append(entry)
            continue

        # 获取 CHANGELOG
        print(f"📥 正在获取 {repo} v{version} 的 CHANGELOG...", file=sys.stderr)
        raw = fetch_changelog_from_tag(repo, version, changelog_path, token)
        if raw is None:
            results.append(entry)
            continue

        # 提取版本 section
        section = extract_version_section(raw, version)
        if section is None:
            print(f"⚠️  {repo}: CHANGELOG 中未找到版本 {version} 的 section", file=sys.stderr)
            results.append(entry)
            continue

        # 扁平化
        entry["changelog"] = flatten_changelog(section)
        print(f"✅ {repo} v{version}: 已提取 CHANGELOG", file=sys.stderr)
        results.append(entry)

    # 按 order 排序
    results.sort(key=lambda x: x["order"])

    # 输出 JSON
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析错误: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ 未知错误: {e}", file=sys.stderr)
        sys.exit(1)
