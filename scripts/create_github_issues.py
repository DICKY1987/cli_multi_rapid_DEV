from __future__ import annotations
"""
Create GitHub milestones and issues from roadmap/backlog docs.

Usage:
  - Dry-run (default):
      python scripts/create_github_issues.py --repo OWNER/REPO
  - Create for real:
      GITHUB_TOKEN=... python scripts/create_github_issues.py --repo OWNER/REPO --token $GITHUB_TOKEN

Inputs:
  - docs/roadmap/2025-09-20/detailed_roadmap.json
  - docs/roadmap/2025-09-20/implementation_backlog.json

Notes:
  - Idempotent: checks for existing milestones/issues by title.
  - Safe by default: --dry-run prints the plan without writing.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests


ROOT = os.path.dirname(os.path.dirname(__file__))
ROADMAP_DIR = os.path.join(ROOT, "docs", "roadmap", "2025-09-20")
DETAILED_ROADMAP_FP = os.path.join(ROADMAP_DIR, "detailed_roadmap.json")
BACKLOG_FP = os.path.join(ROADMAP_DIR, "implementation_backlog.json")


@dataclass
class Milestone:
    title: str
    description: str


@dataclass
class Task:
    id: str
    title: str
    phase: str
    priority: str
    acceptance_criteria: List[str]
    dependencies: List[str]
    validation_steps: List[str]


def load_roadmap() -> Dict[str, Milestone]:
    with open(DETAILED_ROADMAP_FP, "r", encoding="utf-8") as f:
        data = json.load(f)
    milestones: Dict[str, Milestone] = {}
    for phase in data.get("phases", []):
        pid = str(phase.get("id"))
        title = f"Phase {pid} – {phase.get('name', '').strip()}"
        qg = phase.get("quality_gates", {})
        qg_lines = [f"- {k}: {v}" for k, v in qg.items()]
        desc = [
            f"Goal: {phase.get('goal','').strip()}",
            "",
            "Quality Gates:",
            *(qg_lines or ["- (not specified)"]),
        ]
        milestones[pid] = Milestone(title=title, description="\n".join(desc))
    return milestones


def load_backlog() -> List[Task]:
    with open(BACKLOG_FP, "r", encoding="utf-8") as f:
        data = json.load(f)
    tasks: List[Task] = []
    for t in data.get("tasks", []):
        tasks.append(
            Task(
                id=t.get("id"),
                title=t.get("title"),
                phase=str(t.get("phase")),
                priority=t.get("priority", ""),
                acceptance_criteria=t.get("acceptance_criteria", []),
                dependencies=t.get("dependencies", []),
                validation_steps=t.get("validation_steps", []),
            )
        )
    return tasks


def gh_api(repo: str, token: Optional[str]) -> str:
    base = f"https://api.github.com/repos/{repo}"
    return base


def gh_headers(token: Optional[str]) -> Dict[str, str]:
    h = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cli-multi-rapid-issues-script",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_existing_milestones(repo: str, token: Optional[str]) -> Dict[str, int]:
    url = gh_api(repo, token) + "/milestones?state=all&per_page=100"
    r = requests.get(url, headers=gh_headers(token), timeout=30)
    r.raise_for_status()
    out = {}
    for m in r.json():
        out[m["title"]] = m["number"]
    return out


def ensure_milestone(repo: str, token: Optional[str], title: str, description: str, dry_run: bool) -> Optional[int]:
    existing = get_existing_milestones(repo, token)
    if title in existing:
        return existing[title]
    if dry_run:
        print(f"[dry-run] Would create milestone: {title}")
        return None
    url = gh_api(repo, token) + "/milestones"
    r = requests.post(url, headers=gh_headers(token), json={"title": title, "state": "open", "description": description}, timeout=30)
    r.raise_for_status()
    return r.json()["number"]


def search_issue_by_title(repo: str, token: Optional[str], title: str) -> Optional[int]:
    # GitHub search API. Note: not guaranteed exact; we filter locally.
    q = f"repo:{repo} in:title {title}"
    url = f"https://api.github.com/search/issues?q={requests.utils.quote(q)}"
    r = requests.get(url, headers=gh_headers(token), timeout=30)
    r.raise_for_status()
    for item in r.json().get("items", []):
        if item.get("title") == title:
            return item.get("number")
    return None


def create_issue(repo: str, token: Optional[str], title: str, body: str, labels: List[str], milestone_number: Optional[int], dry_run: bool) -> Optional[int]:
    if search_issue_by_title(repo, token, title):
        print(f"Exists: {title}")
        return None
    if dry_run:
        print(f"[dry-run] Would create issue: {title} labels={labels} milestone={milestone_number}")
        return None
    url = gh_api(repo, token) + "/issues"
    payload: Dict[str, object] = {"title": title, "body": body, "labels": labels}
    if milestone_number:
        payload["milestone"] = milestone_number
    r = requests.post(url, headers=gh_headers(token), json=payload, timeout=30)
    r.raise_for_status()
    return r.json()["number"]


def task_body(t: Task) -> str:
    lines = [
        f"Phase: {t.phase}",
        f"Priority: {t.priority}",
        "",
        "## Acceptance Criteria",
    ]
    lines += [f"- {x}" for x in t.acceptance_criteria] or ["- (none)"]
    lines += ["", "## Dependencies"]
    lines += [f"- {x}" for x in t.dependencies] or ["- (none)"]
    lines += ["", "## Validation Steps"]
    lines += [f"- {x}" for x in t.validation_steps] or ["- (none)"]
    lines += ["", "---", "Generated from docs/roadmap/2025-09-20"]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token (or set GITHUB_TOKEN)")
    ap.add_argument("--dry-run", action="store_true", help="Print actions without creating on GitHub")
    args = ap.parse_args()

    milestones = load_roadmap()
    tasks = load_backlog()

    # Create milestones
    milestone_numbers: Dict[str, Optional[int]] = {}
    for pid, m in milestones.items():
        num = ensure_milestone(args.repo, args.token, m.title, m.description, dry_run=args.dry_run)
        milestone_numbers[pid] = num

    # Create issues per task
    for t in tasks:
        labels = [f"phase-{t.phase.lower()}", f"priority-{t.priority.lower()}", "type:task"]
        title = f"[Phase {t.phase}] {t.id}: {t.title}"
        body = task_body(t)
        milestone_num = milestone_numbers.get(t.phase)
        create_issue(args.repo, args.token, title, body, labels, milestone_num, dry_run=args.dry_run)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

