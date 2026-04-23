#!/usr/bin/env python3
"""
更新 CHANGELOG.md，将 Unreleased 替换为指定版本

符合 Keep a Changelog 规范
"""
import re
import argparse
import sys
from datetime import date
from pathlib import Path


def _find_previous_version(content, current_version):
    """从 CHANGELOG 内容中找到当前版本之后的上一个版本号"""
    # 匹配所有 ## [x.y.z] 格式的版本标题（支持完整 SemVer：prerelease + build metadata）
    versions = re.findall(r'## \[(\d+\.\d+\.\d+(?:-[a-zA-Z0-9._-]+)?(?:\+[a-zA-Z0-9._-]+)?)\]', content)
    for i, v in enumerate(versions):
        if v == current_version and i + 1 < len(versions):
            return versions[i + 1]
    return None


def update_changelog(file_path, version, release_date=None, repo=None):
    """
    更新 CHANGELOG.md

    Args:
        file_path: CHANGELOG.md 路径
        version: 版本号 (如 1.5.0)
        release_date: 发布日期 (默认今天，格式 YYYY-MM-DD)
        repo: 仓库名 (如 wujihandpy)，用于生成底部比较链接

    Returns:
        {"success": bool, "message": str}
    """
    if release_date is None:
        release_date = date.today().strftime('%Y-%m-%d')

    file_path = Path(file_path)
    if not file_path.exists():
        return {"success": False, "message": f"文件不存在: {file_path}"}

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        return {"success": False, "message": f"读取文件失败: {e}"}

    # 检查 Unreleased 章节（支持中英文）
    unreleased_pattern = r'## (?:\[)?(?:Unreleased|未发布)(?:\])?'
    if not re.search(unreleased_pattern, content, re.IGNORECASE):
        return {"success": False, "message": "未找到 Unreleased 或 未发布 章节"}

    # 检查版本是否已存在
    version_pattern = rf'## \[{re.escape(version)}\]'
    if re.search(version_pattern, content):
        return {"success": False, "message": f"版本 {version} 已存在"}

    # 替换 Unreleased（第一个匹配项）
    content_new = re.sub(
        unreleased_pattern,
        f'## [{version}] - {release_date}',
        content,
        count=1,
        flags=re.IGNORECASE
    )

    # 在顶部添加新的 Unreleased 占位符
    # 找到第一个 ## 标题的位置（应该是刚才替换的版本标题）
    match = re.search(r'(^|\n)## ', content_new)
    if match:
        insert_pos = match.start()
        # 如果匹配到的是行首（位置0），在之前插入
        if insert_pos == 0:
            content_new = f"## [Unreleased]\n\n{content_new}"
        else:
            before = content_new[:insert_pos].rstrip('\n')
            after = content_new[insert_pos:].lstrip('\n')
            content_new = f"{before}\n\n## [Unreleased]\n\n{after}"
    else:
        # 如果没有找到，说明文件格式可能有问题，但还是尝试添加
        content_new = f"## [Unreleased]\n\n{content_new}"

    # 更新底部比较链接
    if repo:
        base_url = f"https://github.com/wuji-technology/{repo}"
        # 查找已有的 [Unreleased] 链接定义
        unreleased_link_pattern = r'^\[Unreleased\]:\s*\S+'
        unreleased_link_match = re.search(
            unreleased_link_pattern, content_new, re.MULTILINE | re.IGNORECASE
        )

        new_unreleased_link = f"[Unreleased]: {base_url}/compare/v{version}...HEAD"
        new_version_link = f"[{version}]: {base_url}/compare/v{prev_version}...v{version}" if (prev_version := _find_previous_version(content_new, version)) else f"[{version}]: {base_url}/releases/tag/v{version}"

        if unreleased_link_match:
            # 替换已有的 [Unreleased] 链接，并在其后插入新版本链接
            old_link = unreleased_link_match.group(0)
            content_new = content_new.replace(
                old_link,
                f"{new_unreleased_link}\n{new_version_link}",
                1,
            )
        else:
            # 没有已有链接，在文件末尾追加
            content_new = content_new.rstrip('\n') + '\n\n' + new_unreleased_link + '\n' + new_version_link + '\n'

    # 写回文件
    try:
        file_path.write_text(content_new, encoding='utf-8')
    except Exception as e:
        return {"success": False, "message": f"写入文件失败: {e}"}

    return {
        "success": True,
        "message": f"成功: Unreleased → [{version}] - {release_date}"
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='更新 CHANGELOG.md，将 Unreleased 替换为指定版本'
    )
    parser.add_argument('--file', required=True, help='CHANGELOG.md 路径')
    parser.add_argument('--version', required=True, help='版本号 (如 1.5.0)')
    parser.add_argument('--date', help='发布日期 YYYY-MM-DD (默认今天)', default=None)
    parser.add_argument('--repo', help='仓库名 (用于生成底部比较链接)', default=None)

    args = parser.parse_args()
    result = update_changelog(args.file, args.version, args.date, args.repo)

    if result['success']:
        print(f"✅ {result['message']}")
        sys.exit(0)
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)
