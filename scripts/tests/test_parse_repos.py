#!/usr/bin/env python3
"""Tests for scripts/release/parse-repos.py"""

import importlib.util
import os
import sys
import unittest

# parse-repos.py uses a hyphen in the filename; load via importlib
_spec = importlib.util.spec_from_file_location(
    "parse_repos",
    os.path.join(os.path.dirname(__file__), "..", "release", "parse-repos.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
parse_repos = _mod.parse_repos


class TestParseRepos(unittest.TestCase):
    def test_basic(self):
        result = parse_repos("wujihandpy=1.5.0")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["repo"], "wujihandpy")
        self.assertEqual(result[0]["version"], "1.5.0")
        self.assertEqual(result[0]["changelog_path"], "CHANGELOG.md")
        self.assertEqual(result[0]["public_changelog_path"], "")

    def test_multiple_repos(self):
        result = parse_repos("repoA=1.0.0\nrepoB=2.3.4")
        self.assertEqual(len(result), 2)

    def test_custom_changelog_path(self):
        result = parse_repos("myrepo=1.0.0:docs/CHANGELOG.md")
        self.assertEqual(result[0]["changelog_path"], "docs/CHANGELOG.md")

    def test_public_changelog_path(self):
        result = parse_repos("myrepo=1.0.0:CHANGELOG.md:public/CHANGELOG.md")
        self.assertEqual(result[0]["public_changelog_path"], "public/CHANGELOG.md")

    def test_skips_comments_and_blank_lines(self):
        text = "# comment\n\nwujihandpy=1.5.0\n"
        result = parse_repos(text)
        self.assertEqual(len(result), 1)

    def test_prerelease_version(self):
        result = parse_repos("myrepo=1.0.0-hotfix.1")
        self.assertEqual(result[0]["version"], "1.0.0-hotfix.1")

    def test_invalid_version(self):
        with self.assertRaises(ValueError):
            parse_repos("myrepo=bad-version")

    def test_duplicate_repo_raises(self):
        with self.assertRaises(ValueError):
            parse_repos("myrepo=1.0.0\nmyrepo=2.0.0")

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            parse_repos("# only comments\n")

    def test_path_traversal_raises(self):
        with self.assertRaises(ValueError):
            parse_repos("myrepo=1.0.0:../evil.md")

    def test_non_md_path_raises(self):
        with self.assertRaises(ValueError):
            parse_repos("myrepo=1.0.0:CHANGELOG.txt")

    def test_too_many_repos_raises(self):
        lines = "\n".join(f"repo{i}=1.0.0" for i in range(11))
        with self.assertRaises(ValueError):
            parse_repos(lines)


if __name__ == "__main__":
    unittest.main()