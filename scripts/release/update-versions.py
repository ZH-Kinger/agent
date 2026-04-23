#!/usr/bin/env python3
"""
更新版本号文件，根据 .release.yml 配置自动替换版本字符串

用法: python3 update-versions.py --config .release.yml --version 0.6.0 [--dry-run]
退出码: 0=成功或无配置文件, 1=错误
"""
import re
import argparse
import sys
from pathlib import Path

import yaml


def validate_version(version):
    """校验语义化版本号格式"""
    pattern = r'^\d+\.\d+\.\d+(?:-[a-zA-Z0-9.]+)?(?:\+[a-zA-Z0-9.]+)?$'
    return bool(re.match(pattern, version))


def validate_pattern(pattern):
    """校验正则表达式合法性且恰好有 2 个捕获组"""
    try:
        compiled = re.compile(pattern, re.MULTILINE)
    except re.error as e:
        return False, f"正则表达式不合法: {e}"

    if compiled.groups != 2:
        return False, f"需要恰好 2 个捕获组，实际有 {compiled.groups} 个"

    return True, ""


def validate_path(path_str):
    """校验路径为相对路径且不含 .."""
    p = Path(path_str)
    if p.is_absolute():
        return False, "路径必须为相对路径"
    if '..' in p.parts:
        return False, "路径不能包含 .."
    return True, ""


def update_versions(config_path, version, dry_run=False):
    """
    读取 .release.yml 配置并更新版本号文件

    Args:
        config_path: .release.yml 路径
        version: 新版本号 (如 0.6.0)
        dry_run: 仅预览，不实际修改文件

    Returns:
        {"success": bool, "message": str, "updated": list}
    """
    config_file = Path(config_path)
    if not config_file.exists():
        return {
            "success": True,
            "message": "未发现配置文件，跳过版本号更新",
            "updated": [],
        }

    # 校验版本号
    if not validate_version(version):
        return {
            "success": False,
            "message": f"版本号格式不合法: {version} (需要语义化版本，如 1.0.0)",
            "updated": [],
        }

    # 加载配置
    try:
        with open(config_file, encoding='utf-8') as f:
            config = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        return {
            "success": False,
            "message": f"读取配置文件失败: {e}",
            "updated": [],
        }

    if not config or 'version_files' not in config:
        return {
            "success": False,
            "message": "配置文件缺少 version_files 字段",
            "updated": [],
        }

    version_files = config['version_files']
    if not isinstance(version_files, list) or len(version_files) == 0:
        return {
            "success": False,
            "message": "version_files 必须为非空列表",
            "updated": [],
        }

    # 校验所有规则
    for entry in version_files:
        if not isinstance(entry, dict):
            return {
                "success": False,
                "message": f"version_files 条目必须为对象: {entry}",
                "updated": [],
            }
        if 'path' not in entry or 'pattern' not in entry:
            return {
                "success": False,
                "message": f"每条规则必须包含 path 和 pattern 字段: {entry}",
                "updated": [],
            }

        path_ok, path_err = validate_path(entry['path'])
        if not path_ok:
            return {
                "success": False,
                "message": f"路径校验失败 ({entry['path']}): {path_err}",
                "updated": [],
            }

        pattern_ok, pattern_err = validate_pattern(entry['pattern'])
        if not pattern_ok:
            return {
                "success": False,
                "message": f"正则校验失败 ({entry['path']}): {pattern_err}",
                "updated": [],
            }

    # 阶段 1：预读并生成所有替换结果，遇错立即返回（无副作用）
    pending_writes = []  # list of (file_path, new_content, entry_path)
    config_dir = config_file.parent

    for entry in version_files:
        file_path = config_dir / entry['path']
        pattern = entry['pattern']

        if not file_path.exists():
            return {
                "success": False,
                "message": f"文件不存在: {entry['path']}",
                "updated": [],
            }

        try:
            content = file_path.read_text(encoding='utf-8')
        except OSError as e:
            return {
                "success": False,
                "message": f"读取文件失败 ({entry['path']}): {e}",
                "updated": [],
            }

        replacement = rf'\g<1>{version}\g<2>'
        new_content, count = re.subn(
            pattern, replacement, content, count=1, flags=re.MULTILINE
        )

        if count == 0:
            return {
                "success": False,
                "message": f"未匹配到版本号 ({entry['path']}): pattern={pattern}",
                "updated": [],
            }

        if dry_run:
            match = re.search(pattern, content, re.MULTILINE)
            old_line = match.group(0).strip() if match else "?"
            new_match = re.search(pattern, new_content, re.MULTILINE)
            new_line = new_match.group(0).strip() if new_match else "?"
            print(f"  📦 [DRY RUN] {entry['path']}: {old_line} → {new_line}")
        else:
            pending_writes.append((file_path, new_content, entry['path']))

    # 阶段 2：统一写入（仅 non-dry-run 且所有预检通过后执行）
    updated = []
    for file_path, new_content, entry_path in pending_writes:
        try:
            file_path.write_text(new_content, encoding='utf-8')
        except OSError as e:
            return {
                "success": False,
                "message": f"写入文件失败 ({entry_path}): {e}",
                "updated": updated,
            }
        print(f"  📦 已更新: {entry_path} → {version}")
        updated.append(entry_path)

    if dry_run:
        updated = [e['path'] for e in version_files]

    action = "预览" if dry_run else "更新"
    return {
        "success": True,
        "message": f"成功{action} {len(updated)} 个版本号文件",
        "updated": updated,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='更新版本号文件，根据 .release.yml 配置自动替换版本字符串'
    )
    parser.add_argument('--config', required=True, help='.release.yml 配置文件路径')
    parser.add_argument('--version', required=True, help='版本号 (如 0.6.0)')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际修改文件')

    args = parser.parse_args()
    result = update_versions(args.config, args.version, args.dry_run)

    if result['success']:
        print(f"✅ {result['message']}")
        sys.exit(0)
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)
