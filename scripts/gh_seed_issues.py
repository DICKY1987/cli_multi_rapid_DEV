#!/usr/bin/env python3
"""
Seed GitHub milestones and issues from planning/*.yaml using the GitHub CLI.

Prerequisites:
  - Install GitHub CLI: https://cli.github.com/
  - Authenticate: gh auth login

Usage:
  python scripts/gh_seed_issues.py --repo <owner/repo> [--milestones planning/issues_phase_*.yaml] [--issues planning/issues_phase_*.yaml]

Notes:
  - Safe to re-run; attempts to skip existing milestones by title.
  - Issues are created idempotently by checking open issues with same title.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List

import yaml


def run(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemError(f"Command failed: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout


def gh_json(cmd: List[str]) -> List[Dict]:
    out = run(cmd)
    try:
        return json.loads(out)
    except Exception:
        return []


def ensure_milestones(repo: str, paths: List[Path]):
    existing = {m["title"] for m in gh_json(["gh", "api", f"repos/{repo}/milestones"]) }
    for p in paths:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for m in data.get("milestones", []) or []:
            title = m.get("title")
            if not title or title in existing:
                continue
            desc = m.get("description", "")
            run(["gh", "api", f"repos/{repo}/milestones", "-f", f"title={title}", "-f", f"state=open", "-f", f"description={desc}"])
            print(f"[milestone] created: {title}")


def ensure_issues(repo: str, paths: List[Path]):
    existing_titles = {i["title"] for i in gh_json(["gh", "issue", "list", "--repo", repo, "--state", "open", "--json", "title"]) }
    for p in paths:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for it in data.get("issues", []) or []:
            title = it.get("title")
            if not title or title in existing_titles:
                continue
            body = it.get("body", "")
            labels = it.get("labels", [])
            milestone = it.get("milestone")
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
            if labels:
                cmd += ["--label", ",".join(labels)]
            if milestone:
                cmd += ["--milestone", milestone]
            run(cmd)
            print(f"[issue] created: {title}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--milestones", nargs="*", default=[], help="YAML files containing milestones")
    ap.add_argument("--issues", nargs="*", default=[], help="YAML files containing issues")
    args = ap.parse_args()

    milestone_paths = [Path(p) for p in (args.milestones or []) if Path(p).exists()]
    issue_paths = [Path(p) for p in (args.issues or []) if Path(p).exists()]

    if milestone_paths:
        ensure_milestones(args.repo, milestone_paths)
    if issue_paths:
        ensure_issues(args.repo, issue_paths)


if __name__ == "__main__":
    main()

