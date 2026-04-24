"""Tool: preview_changelog — 预览 CHANGELOG 更新结果（dry-run）"""
import sys, os, re
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "release"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "update_changelog",
    os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "release", "update-changelog.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
_update_changelog = _mod.update_changelog


def preview_changelog(changelog_content: str, version: str, release_date: str = "") -> dict:
    """
    预览将 CHANGELOG 中 Unreleased 替换为指定版本后的效果。

    Args:
        changelog_content: CHANGELOG.md 的文本内容
        version: 目标版本号，如 1.5.0
        release_date: 发布日期 YYYY-MM-DD，留空用今天

    Returns:
        {"ok": True, "preview": "..."} 或 {"ok": False, "error": "..."}
    """
    import tempfile, pathlib

    rd = release_date or date.today().strftime("%Y-%m-%d")

    # 写入临时文件，调用现有函数，再读回
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(changelog_content)
        tmp = f.name

    try:
        result = _update_changelog(tmp, version, rd, repo=None)
        if not result["success"]:
            return {"ok": False, "error": result["message"]}
        preview = pathlib.Path(tmp).read_text(encoding="utf-8")
        return {"ok": True, "preview": preview, "message": result["message"]}
    finally:
        os.unlink(tmp)


def fetch_unreleased_section(changelog_content: str) -> str:
    """提取 CHANGELOG 中 Unreleased section 的内容，用于确认发布内容。"""
    lines = changelog_content.split("\n")
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
    section = "\n".join(result).strip()
    return section or "（Unreleased section 为空）"