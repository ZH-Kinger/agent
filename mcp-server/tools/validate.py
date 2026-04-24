"""Tool: validate_release_input — 校验 repo=version 格式"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "release"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "parse_repos",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "release", "parse-repos.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
parse_repos = _mod.parse_repos


def validate_release_input(repos_text: str) -> dict:
    """
    校验并解析 repo=version 格式输入。

    Args:
        repos_text: 多行文本，每行 repo=version 或 repo=version:changelog_path

    Returns:
        {"ok": True, "repos": [...]} 或 {"ok": False, "error": "..."}
    """
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