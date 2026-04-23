#!/usr/bin/env python3
"""
根据抓取到的 CHANGELOG 数据生成 release-notes.mdx 模板

读取 fetch-changelogs.py 的 JSON 输出，
生成中英文两份 release-notes section 片段，
用于插入到 wuji-docs-center 的 release-notes.mdx 文件中。

输入: fetch-changelogs.py 的 JSON 输出 (stdin)
输出: 生成两个文件到指定目录
"""
import argparse
import json
import os
import re
import sys
from datetime import date


def format_date(d):
    """格式化日期为 YYYY.MM.DD（中英文统一格式）"""
    return d.strftime("%Y.%m.%d")


def render_update_method(template, public_repo, version):
    """渲染更新方式模板中的变量"""
    if not template:
        return ""
    return template.replace("{public_repo}", public_repo or "").replace("{version}", version)


def generate_version_table_zh(components, release_date):
    """生成中文版本表格"""
    lines = [
        f"## 发布日期：{format_date(release_date)}",
        "",
        "| 组件 | 版本号 | 更新方式 |",
        "| --- | --- | --- |",
    ]
    for c in components:
        name = c["display_name_zh"]
        version = f'v{c["version"]}'
        method = render_update_method(c["update_method_zh"], c.get("public_repo"), c["version"])
        lines.append(f"| {name} | {version} | {method} |")
    return "\n".join(lines)


def generate_version_table_en(components, release_date):
    """生成英文版本表格"""
    lines = [
        f"## Release Date: {format_date(release_date)}",
        "",
        "| Component | Version | Update Method |",
        "| --- | --- | --- |",
    ]
    for c in components:
        name = c["display_name_en"]
        version = f'v{c["version"]}'
        method = render_update_method(c["update_method_en"], c.get("public_repo"), c["version"])
        lines.append(f"| {name} | {version} | {method} |")
    return "\n".join(lines)


def generate_changelog_section_zh(components):
    """生成中文主要更新 section（CHANGELOG 原文）"""
    lines = [
        "",
        "",
        "### 主要更新",
        "",
        "<!-- TODO: 以下为 CHANGELOG 原文，请精简后删除此注释 -->",
        "",
    ]
    has_changelog = False
    for c in components:
        if c.get("changelog"):
            has_changelog = True
            lines.append(f'#### {c["display_name_zh"]} v{c["version"]}')
            lines.append("")
            lines.append(c["changelog"])
            lines.append("")

    if not has_changelog:
        lines.append("<!-- 未抓取到 CHANGELOG 内容，请手动填写 -->")
        lines.append("")

    return "\n".join(lines)


def generate_changelog_section_en(components):
    """生成英文 Key Updates section（CHANGELOG 原文）"""
    lines = [
        "",
        "",
        "### Key Updates",
        "",
        "<!-- TODO: Changelog content below is auto-collected. Please refine before publishing. -->",
        "",
    ]
    has_changelog = False
    for c in components:
        if c.get("changelog"):
            has_changelog = True
            lines.append(f'#### {c["display_name_en"]} v{c["version"]}')
            lines.append("")
            lines.append(c["changelog"])
            lines.append("")

    if not has_changelog:
        lines.append("<!-- No changelog content collected. Please fill in manually. -->")
        lines.append("")

    return "\n".join(lines)


def insert_new_release(existing_content, new_section, marker_pattern):
    """
    在现有 release-notes.mdx 文件中插入新版本 section

    新版本 section 插入在第一个 '## 发布日期' 或 '## Release Date' 之前

    Args:
        existing_content: 现有文件内容
        new_section: 新版本 section 文本
        marker_pattern: 标记模式 (正则)

    Returns:
        更新后的文件内容
    """
    match = re.search(marker_pattern, existing_content, re.MULTILINE)
    if match:
        insert_pos = match.start()
        return (
            existing_content[:insert_pos]
            + new_section
            + "\n---\n\n"
            + existing_content[insert_pos:]
        )
    else:
        # 如果没有找到已有 section，追加到文件末尾
        return existing_content.rstrip() + "\n\n" + new_section + "\n"


def main():
    parser = argparse.ArgumentParser(description="生成 release-notes.mdx 模板")
    parser.add_argument("--output-dir", required=True, help="输出目录（wuji-docs-center 根目录）")
    parser.add_argument("--release-date", default="", help="发布日期 YYYY-MM-DD，留空使用当天")
    parser.add_argument("--dry-run", action="store_true", help="仅输出到 stdout，不修改文件")
    args = parser.parse_args()

    # 读取配置
    config_path = os.path.join(os.path.dirname(__file__), "release-notes-config.json")
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"❌ 错误: 配置文件不存在: {config_path}", file=sys.stderr)
        sys.exit(1)

    # 从 stdin 读取 changelog 数据
    try:
        components = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(f"❌ 错误: stdin 输入的 JSON 格式无效: {e}", file=sys.stderr)
        sys.exit(1)

    # 发布日期
    if args.release_date:
        try:
            release_date = date.fromisoformat(args.release_date)
        except ValueError:
            print("❌ 错误: 发布日期格式应为 YYYY-MM-DD", file=sys.stderr)
            sys.exit(1)
    else:
        release_date = date.today()

    # 生成中文 section
    zh_section = generate_version_table_zh(components, release_date)
    zh_section += generate_changelog_section_zh(components)

    # 生成英文 section
    en_section = generate_version_table_en(components, release_date)
    en_section += generate_changelog_section_en(components)

    if args.dry_run:
        print("=== 中文 Release Notes Section ===")
        print(zh_section)
        print("\n=== 英文 Release Notes Section ===")
        print(en_section)
        return

    # 更新中文文件
    zh_path = os.path.join(args.output_dir, config["release_notes_path_zh"])
    try:
        with open(zh_path, encoding="utf-8") as f:
            zh_content = f.read()
    except FileNotFoundError:
        print(f"❌ 错误: 中文 Release Notes 文件不存在: {zh_path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"❌ 错误: 无权限读取文件: {zh_path}", file=sys.stderr)
        sys.exit(1)
    zh_updated = insert_new_release(zh_content, zh_section, r"^## 发布日期")
    try:
        with open(zh_path, "w", encoding="utf-8") as f:
            f.write(zh_updated)
    except PermissionError:
        print(f"❌ 错误: 无权限写入文件: {zh_path}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ 已更新中文 Release Notes: {zh_path}", file=sys.stderr)

    # 更新英文文件
    en_path = os.path.join(args.output_dir, config["release_notes_path_en"])
    try:
        with open(en_path, encoding="utf-8") as f:
            en_content = f.read()
    except FileNotFoundError:
        print(f"❌ 错误: 英文 Release Notes 文件不存在: {en_path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"❌ 错误: 无权限读取文件: {en_path}", file=sys.stderr)
        sys.exit(1)
    en_updated = insert_new_release(en_content, en_section, r"^## Release Date")
    try:
        with open(en_path, "w", encoding="utf-8") as f:
            f.write(en_updated)
    except PermissionError:
        print(f"❌ 错误: 无权限写入文件: {en_path}", file=sys.stderr)
        sys.exit(1)
    print(f"✅ 已更新英文 Release Notes: {en_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
