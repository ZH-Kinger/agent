"""Tool: validate_release_input — 校验 repo=version 格式"""
import re
from pathlib import PurePosixPath


def parse_repos(input_text: str) -> list[dict]:
    """
    解析格式: repo1=1.5.0\\nrepo2=2.0.0:public/CHANGELOG.md
    返回: [{"repo": ..., "version": ..., "changelog_path": ..., "public_changelog_path": ...}, ...]
    """
    result = []
    input_text = re.sub(r'(?<!^)\s+(?=[a-zA-Z0-9_.-]+=)', '\n', input_text.strip())

    for line_num, line in enumerate(input_text.strip().split('\n'), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        match = re.match(r'^([a-zA-Z0-9_.-]+)\s*=\s*(.+)$', line)
        if not match:
            raise ValueError(f"第 {line_num} 行格式错误: {line}\n正确格式: repo=version")

        repo, value = match.groups()
        value = value.strip()
        parts = value.split(':')
        if len(parts) > 3:
            raise ValueError(f"第 {line_num} 行格式错误: {line}\n最多支持三段: repo=version:changelog_path:public_changelog_path")

        version = parts[0].strip()
        changelog_path = parts[1].strip() if len(parts) > 1 else "CHANGELOG.md"
        public_changelog_path = parts[2].strip() if len(parts) > 2 else ""

        if not re.match(r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$', version):
            raise ValueError(f"第 {line_num} 行版本号格式错误: {version}\n正确格式: X.Y.Z")

        path = PurePosixPath(changelog_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"第 {line_num} 行 CHANGELOG 路径非法: {changelog_path}")

        if public_changelog_path:
            pub_path = PurePosixPath(public_changelog_path)
            if pub_path.is_absolute() or ".." in pub_path.parts:
                raise ValueError(f"第 {line_num} 行公开 CHANGELOG 路径非法: {public_changelog_path}")

        result.append({
            "repo": repo.strip(),
            "version": version,
            "changelog_path": changelog_path,
            "public_changelog_path": public_changelog_path,
        })

    if not result:
        raise ValueError("未找到有效的仓库配置")

    repo_names = [item["repo"] for item in result]
    duplicates = set(x for x in repo_names if repo_names.count(x) > 1)
    if duplicates:
        raise ValueError(f"仓库名重复: {', '.join(duplicates)}")

    if len(result) > 10:
        raise ValueError(f"单次最多支持 10 个仓库，当前: {len(result)} 个")

    return result


def validate_release_input(repos_text: str) -> dict:
    try:
        repos = parse_repos(repos_text)
        summary = "\n".join(f"  ✅ {r['repo']} → v{r['version']} ({r['changelog_path']})" for r in repos)
        return {
            "ok": True,
            "repos": repos,
            "summary": f"解析成功，共 {len(repos)} 个仓库：\n{summary}",
        }
    except ValueError as e:
        return {"ok": False, "error": str(e)}
