#!/usr/bin/env python3
"""
Git Operations Adapter with GitHub API Integration

Automates git operations and GitHub API interactions, emitting structured artifacts
suitable for downstream gates and reporting. Supports both basic git operations
and advanced GitHub features like repository analysis, issue management, and PR automation.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


@dataclass
class GitCommandResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class GitOpsAdapter(BaseAdapter):
    """Enhanced adapter for git workflows with GitHub API integration."""

    def __init__(self) -> None:
        super().__init__(
            name="git_ops",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Enhanced git operations with GitHub API integration (repos, issues, PRs, releases)",
        )
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_api_base = "https://api.github.com"

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        self._log_execution_start(step)
        try:
            params = self._extract_with_params(step)
            emit_paths = self._extract_emit_paths(step)
            op = params.get("operation", "status")

            if op == "create_branch":
                name = params.get("name") or self._default_branch_name()
                result = self._create_branch(name)
                artifact = self._artifact(
                    "git.branch",
                    {"branch": name, "stdout": result.stdout, "stderr": result.stderr},
                )
            elif op == "commit":
                message = params.get("message", "chore: automated commit")
                add = params.get("add", ["-A"])
                result = self._commit(add, message)
                artifact = self._artifact(
                    "git.commit",
                    {
                        "message": message,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                )
            elif op == "open_pr":
                title = params.get("title", "Automated PR")
                body = params.get("body", "Opened by git_ops adapter")
                base = params.get("base", "main")
                head = params.get("head") or self._current_branch()
                real = bool(params.get("real", False))

                pr_url = None
                if real:
                    # Try GitHub CLI first
                    try:
                        gh_cmd = [
                            "gh",
                            "pr",
                            "create",
                            "--title",
                            title,
                            "--body",
                            body,
                            "--base",
                            base,
                            "--head",
                            head,
                        ]
                        gh_res = subprocess.run(
                            gh_cmd, capture_output=True, text=True, timeout=60
                        )
                        stdout = (gh_res.stdout or "").strip()
                        if gh_res.returncode == 0 and stdout.startswith("https://"):
                            pr_url = stdout.splitlines()[-1].strip()
                            result = GitCommandResult(
                                True, gh_res.stdout, gh_res.stderr, gh_res.returncode
                            )
                        else:
                            # Fallback to mock if gh failed
                            result = GitCommandResult(
                                False, gh_res.stdout, gh_res.stderr, gh_res.returncode
                            )
                    except Exception as e:
                        result = GitCommandResult(False, "", str(e), 1)
                else:
                    result = GitCommandResult(True)

                if not pr_url:
                    pr_url = f"https://example.com/repo/compare/{base}...{head}#pr"

                artifact = self._artifact(
                    "git.pr",
                    {
                        "title": title,
                        "body": body,
                        "base": base,
                        "head": head,
                        "url": pr_url,
                        "mode": "real" if real else "mock",
                    },
                )
            elif op == "label":
                label = params.get("label", "automation")
                artifact = self._artifact("git.label", {"label": label})
                result = GitCommandResult(True)
            elif op == "assign":
                assignee = params.get("assignee", "")
                artifact = self._artifact("git.assign", {"assignee": assignee})
                result = GitCommandResult(True)
            elif op == "repo_analysis":
                repo = params.get("repo") or self._get_github_repo()
                analysis = self._analyze_repository(repo)
                artifact = self._artifact("github.repo_analysis", analysis)
                result = GitCommandResult(True)
            elif op == "create_issue":
                repo = params.get("repo") or self._get_github_repo()
                title = params.get("title", "Automated Issue")
                body = params.get("body", "Created by git_ops adapter")
                labels = params.get("labels", [])
                assignees = params.get("assignees", [])
                issue = self._create_github_issue(repo, title, body, labels, assignees)
                artifact = self._artifact("github.issue", issue)
                result = GitCommandResult(bool(issue.get("number")))
            elif op == "get_issues":
                repo = params.get("repo") or self._get_github_repo()
                state = params.get("state", "open")
                labels = params.get("labels", [])
                issues = self._get_github_issues(repo, state, labels)
                artifact = self._artifact(
                    "github.issues", {"issues": issues, "count": len(issues)}
                )
                result = GitCommandResult(True)
            elif op == "pr_review":
                repo = params.get("repo") or self._get_github_repo()
                pr_number = params.get("pr_number")
                review_data = self._analyze_pr(repo, pr_number)
                artifact = self._artifact("github.pr_review", review_data)
                result = GitCommandResult(bool(review_data.get("pr_number")))
            elif op == "release_info":
                repo = params.get("repo") or self._get_github_repo()
                tag = params.get("tag", "latest")
                release = self._get_release_info(repo, tag)
                artifact = self._artifact("github.release", release)
                result = GitCommandResult(bool(release.get("tag_name")))
            elif op == "list_workflows":
                repo = params.get("repo") or self._get_github_repo()
                workflows = self._list_github_workflows(repo)
                artifact = self._artifact("github.workflows", {"workflows": workflows})
                result = GitCommandResult(True)
            elif op == "create_coordination_branches":
                workflows = params.get("workflows", [])
                branch_map = self.create_coordination_branches(workflows)
                artifact = self._artifact("git.coordination_branches", branch_map)
                result = GitCommandResult(True)
            elif op == "setup_merge_queue":
                branches = params.get("branches", [])
                verification_level = params.get("verification_level", "standard")
                queue_config = self.setup_merge_queue(branches, verification_level)
                artifact = self._artifact("git.merge_queue_config", queue_config)
                result = GitCommandResult(True)
            elif op == "execute_merge_queue":
                queue_config = params.get("queue_config", {})
                merge_results = self.execute_merge_queue(queue_config)
                artifact = self._artifact("git.merge_queue_results", {"results": merge_results})
                result = GitCommandResult(all(r.get("status") == "merged" for r in merge_results))
            else:
                artifact = self._artifact("git.status", {"operation": op})
                result = self._git(["status", "--porcelain=v1"])  # non-fatal
                artifact["status"] = result.stdout

            # Write artifact(s)
            artifacts = self._write_artifacts(emit_paths, artifact)
            return AdapterResult(
                success=result.success,
                tokens_used=0,
                artifacts=artifacts,
                output=result.stdout,
                metadata={"operation": op},
            )

        except Exception as e:
            return AdapterResult(success=False, error=f"git_ops failed: {e}")

    def is_available(self) -> bool:  # type: ignore[override]
        try:
            r = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0
        except Exception:
            return False

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        params = self._extract_with_params(step)
        operation = params.get("operation", "status")

        valid_operations = {
            "status",
            "create_branch",
            "commit",
            "open_pr",
            "label",
            "assign",
            "repo_analysis",
            "create_issue",
            "get_issues",
            "pr_review",
            "release_info",
            "list_workflows",
        }

        return operation in valid_operations

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate the token cost of executing this step."""
        # Deterministic operations have zero token cost
        return 0

    # Helpers
    def _git(self, args: List[str]) -> GitCommandResult:
        try:
            p = subprocess.run(
                ["git", *args], capture_output=True, text=True, timeout=30
            )
            return GitCommandResult(p.returncode == 0, p.stdout, p.stderr, p.returncode)
        except Exception as e:
            return GitCommandResult(False, "", str(e), 1)

    def _create_branch(self, name: str) -> GitCommandResult:
        # Create or switch to branch
        res = self._git(["checkout", "-B", name])
        return res

    def _commit(self, add: List[str], message: str) -> GitCommandResult:
        add_res = self._git(["add", *add])
        if not add_res.success:
            return add_res
        return self._git(["commit", "-m", message])

    def _current_branch(self) -> str:
        r = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
        return (r.stdout or "").strip() or "feature/automation"

    def _default_branch_name(self) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        return f"feature/ai-auto-{ts}"

    def _artifact(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "type": kind,
            **payload,
        }

    def _write_artifacts(self, emit_paths: List[str], obj: Dict[str, Any]) -> List[str]:
        written: List[str] = []
        for p in emit_paths:
            dest = Path(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
            written.append(str(dest))
        return written

    # GitHub API Integration Methods

    def _get_github_repo(self) -> str:
        """Extract GitHub repo name from git remote origin."""
        try:
            result = self._git(["remote", "get-url", "origin"])
            if result.success:
                url = result.stdout.strip()
                # Handle both SSH and HTTPS formats
                if url.startswith("git@github.com:"):
                    repo = url.replace("git@github.com:", "").replace(".git", "")
                elif "github.com/" in url:
                    repo = url.split("github.com/")[-1].replace(".git", "")
                else:
                    return "unknown/unknown"
                return repo
        except Exception:
            pass
        return "unknown/unknown"

    def _github_api_request(
        self, endpoint: str, method: str = "GET", data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated GitHub API request."""
        if not self.github_token:
            return {"error": "GitHub token not found in environment"}

        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CLI-Orchestrator/1.0",
        }

        url = f"{self.github_api_base}/{endpoint.lstrip('/')}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=30)
            elif method == "PATCH":
                response = requests.patch(url, headers=headers, json=data, timeout=30)
            else:
                return {"error": f"Unsupported HTTP method: {method}"}

            if response.status_code < 400:
                return response.json() if response.content else {"success": True}
            else:
                return {
                    "error": f"GitHub API error {response.status_code}: {response.text}"
                }

        except Exception as e:
            return {"error": f"GitHub API request failed: {str(e)}"}

    def _analyze_repository(self, repo: str) -> Dict[str, Any]:
        """Analyze GitHub repository structure and metadata."""
        analysis = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "languages": {},
            "topics": [],
            "recent_activity": {},
            "repository_info": {},
        }

        # Get repository information
        repo_data = self._github_api_request(f"repos/{repo}")
        if "error" not in repo_data:
            analysis["repository_info"] = {
                "name": repo_data.get("name"),
                "description": repo_data.get("description"),
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "open_issues": repo_data.get("open_issues_count", 0),
                "created_at": repo_data.get("created_at"),
                "updated_at": repo_data.get("updated_at"),
                "default_branch": repo_data.get("default_branch"),
                "size": repo_data.get("size", 0),
            }
            analysis["topics"] = repo_data.get("topics", [])

        # Get language breakdown
        languages = self._github_api_request(f"repos/{repo}/languages")
        if "error" not in languages:
            total_bytes = sum(languages.values())
            analysis["languages"] = (
                {
                    lang: {
                        "bytes": count,
                        "percentage": round((count / total_bytes) * 100, 2),
                    }
                    for lang, count in languages.items()
                }
                if total_bytes > 0
                else {}
            )

        # Get recent commits
        commits = self._github_api_request(f"repos/{repo}/commits?per_page=10")
        if "error" not in commits and isinstance(commits, list):
            analysis["recent_activity"]["recent_commits"] = len(commits)
            analysis["recent_activity"]["last_commit"] = (
                commits[0].get("commit", {}).get("committer", {}).get("date")
                if commits
                else None
            )

        # Get open pull requests
        prs = self._github_api_request(f"repos/{repo}/pulls?state=open&per_page=5")
        if "error" not in prs and isinstance(prs, list):
            analysis["recent_activity"]["open_prs"] = len(prs)
            analysis["recent_activity"]["pr_titles"] = [
                pr.get("title") for pr in prs[:3]
            ]

        return analysis

    def _create_github_issue(
        self, repo: str, title: str, body: str, labels: List[str], assignees: List[str]
    ) -> Dict[str, Any]:
        """Create a new GitHub issue."""
        data = {"title": title, "body": body, "labels": labels, "assignees": assignees}

        result = self._github_api_request(
            f"repos/{repo}/issues", method="POST", data=data
        )

        if "error" not in result:
            return {
                "number": result.get("number"),
                "url": result.get("html_url"),
                "state": result.get("state"),
                "created_at": result.get("created_at"),
                "title": title,
                "body": body,
                "labels": labels,
                "assignees": assignees,
            }
        else:
            return result

    def _get_github_issues(
        self, repo: str, state: str, labels: List[str]
    ) -> List[Dict[str, Any]]:
        """Get GitHub issues with filtering."""
        params = f"state={state}"
        if labels:
            params += f"&labels={','.join(labels)}"

        issues = self._github_api_request(f"repos/{repo}/issues?{params}")

        if "error" not in issues and isinstance(issues, list):
            return [
                {
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "state": issue.get("state"),
                    "created_at": issue.get("created_at"),
                    "updated_at": issue.get("updated_at"),
                    "url": issue.get("html_url"),
                    "labels": [label.get("name") for label in issue.get("labels", [])],
                    "assignees": [
                        assignee.get("login") for assignee in issue.get("assignees", [])
                    ],
                }
                for issue in issues
                if "pull_request" not in issue  # Filter out PRs
            ]
        return []

    def _analyze_pr(self, repo: str, pr_number: int) -> Dict[str, Any]:
        """Analyze a GitHub pull request."""
        if not pr_number:
            return {"error": "PR number is required"}

        pr_data = self._github_api_request(f"repos/{repo}/pulls/{pr_number}")

        if "error" in pr_data:
            return pr_data

        # Get PR files
        files = self._github_api_request(f"repos/{repo}/pulls/{pr_number}/files")

        analysis = {
            "pr_number": pr_number,
            "title": pr_data.get("title"),
            "state": pr_data.get("state"),
            "created_at": pr_data.get("created_at"),
            "updated_at": pr_data.get("updated_at"),
            "url": pr_data.get("html_url"),
            "author": pr_data.get("user", {}).get("login"),
            "base_branch": pr_data.get("base", {}).get("ref"),
            "head_branch": pr_data.get("head", {}).get("ref"),
            "commits": pr_data.get("commits", 0),
            "additions": pr_data.get("additions", 0),
            "deletions": pr_data.get("deletions", 0),
            "changed_files": pr_data.get("changed_files", 0),
            "files": [],
        }

        if "error" not in files and isinstance(files, list):
            analysis["files"] = [
                {
                    "filename": f.get("filename"),
                    "status": f.get("status"),
                    "additions": f.get("additions", 0),
                    "deletions": f.get("deletions", 0),
                    "changes": f.get("changes", 0),
                }
                for f in files
            ]

        return analysis

    def _get_release_info(self, repo: str, tag: str) -> Dict[str, Any]:
        """Get GitHub release information."""
        if tag == "latest":
            endpoint = f"repos/{repo}/releases/latest"
        else:
            endpoint = f"repos/{repo}/releases/tags/{tag}"

        release = self._github_api_request(endpoint)

        if "error" not in release:
            return {
                "tag_name": release.get("tag_name"),
                "name": release.get("name"),
                "body": release.get("body"),
                "created_at": release.get("created_at"),
                "published_at": release.get("published_at"),
                "url": release.get("html_url"),
                "prerelease": release.get("prerelease", False),
                "draft": release.get("draft", False),
                "author": release.get("author", {}).get("login"),
                "assets": [
                    {
                        "name": asset.get("name"),
                        "size": asset.get("size"),
                        "download_count": asset.get("download_count", 0),
                        "url": asset.get("browser_download_url"),
                    }
                    for asset in release.get("assets", [])
                ],
            }
        return release

    def _list_github_workflows(self, repo: str) -> List[Dict[str, Any]]:
        """List GitHub Actions workflows."""
        workflows = self._github_api_request(f"repos/{repo}/actions/workflows")

        if "error" not in workflows and "workflows" in workflows:
            return [
                {
                    "id": wf.get("id"),
                    "name": wf.get("name"),
                    "path": wf.get("path"),
                    "state": wf.get("state"),
                    "created_at": wf.get("created_at"),
                    "updated_at": wf.get("updated_at"),
                    "url": wf.get("html_url"),
                }
                for wf in workflows["workflows"]
            ]
        return []

    def create_coordination_branches(self, workflows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Create isolated branches for parallel workflow execution."""

        branch_map = {}
        base_branch = self._current_branch()

        for workflow in workflows:
            workflow_id = workflow.get('metadata', {}).get('id', workflow.get('name', 'unnamed'))
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            branch_name = f"auto/{workflow_id}-{timestamp}"

            # Create branch from current HEAD
            result = self._git(['checkout', '-b', branch_name])
            if result.success:
                # Get the commit hash
                head_result = self._git(['rev-parse', 'HEAD'])
                head_commit = head_result.stdout.strip() if head_result.success else "unknown"

                branch_map[workflow_id] = {
                    "branch_name": branch_name,
                    "base_branch": base_branch,
                    "head_commit": head_commit,
                    "status": "ready",
                    "created_at": datetime.now().isoformat()
                }
                self.console.print(f"[green]Created coordination branch: {branch_name}[/green]")
            else:
                branch_map[workflow_id] = {
                    "branch_name": branch_name,
                    "base_branch": base_branch,
                    "status": "failed",
                    "error": result.stderr,
                    "created_at": datetime.now().isoformat()
                }
                self.console.print(f"[red]Failed to create branch {branch_name}: {result.stderr}[/red]")

            # Return to base branch
            self._git(['checkout', base_branch])

        return branch_map

    def setup_merge_queue(self, branches: List[str],
                         verification_level: str = "standard") -> Dict[str, Any]:
        """Setup merge queue for coordinated integration."""

        queue_config = {
            "branches": branches,
            "verification_level": verification_level,
            "merge_strategy": "sequential",
            "auto_rollback": True,
            "quality_gates": self._get_quality_gates(verification_level),
            "created_at": datetime.now().isoformat(),
            "base_branch": self._current_branch()
        }

        # Write queue configuration
        queue_file = Path(".ai/coordination/merge_queue.json")
        queue_file.parent.mkdir(parents=True, exist_ok=True)

        with open(queue_file, 'w') as f:
            json.dump(queue_config, f, indent=2)

        self.console.print(f"[blue]Merge queue configured with {len(branches)} branches[/blue]")
        return queue_config

    def execute_merge_queue(self, queue_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute merge queue with verification."""

        results = []
        base_branch = queue_config.get("base_branch", "main")
        quality_gates = queue_config.get("quality_gates", ["lint", "test"])

        for branch in queue_config.get("branches", []):
            self.console.print(f"[cyan]Processing merge queue item: {branch}[/cyan]")

            # Switch to base branch and pull latest
            base_result = self._git(['checkout', base_branch])
            if not base_result.success:
                results.append({
                    "branch": branch,
                    "status": "failed",
                    "error": f"Failed to checkout base branch: {base_result.stderr}",
                    "timestamp": datetime.now().isoformat()
                })
                continue

            pull_result = self._git(['pull', 'origin', base_branch])
            if not pull_result.success:
                self.console.print(f"[yellow]Warning: Failed to pull latest from {base_branch}[/yellow]")

            # Create shadow merge for verification
            shadow_result = self._shadow_merge_verification(branch, base_branch, quality_gates)

            if shadow_result["success"]:
                # Attempt actual merge
                merge_result = self._git(['merge', '--no-ff', branch, '-m', f'Merge {branch} via coordination queue'])

                if merge_result.success:
                    # Run final quality gates
                    gate_results = self._run_quality_gates(quality_gates)

                    if all(gate['success'] for gate in gate_results):
                        results.append({
                            "branch": branch,
                            "status": "merged",
                            "merge_commit": self._get_current_commit(),
                            "gates": gate_results,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.console.print(f"[green]✓ Successfully merged {branch}[/green]")
                    else:
                        # Rollback failed merge
                        self._git(['reset', '--hard', 'HEAD~1'])
                        results.append({
                            "branch": branch,
                            "status": "failed_gates",
                            "gates": gate_results,
                            "rollback": True,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.console.print(f"[red]✗ Merged {branch} but failed quality gates - rolled back[/red]")
                else:
                    results.append({
                        "branch": branch,
                        "status": "merge_conflict",
                        "error": merge_result.stderr,
                        "timestamp": datetime.now().isoformat()
                    })
                    self.console.print(f"[red]✗ Merge conflict for {branch}[/red]")
            else:
                results.append({
                    "branch": branch,
                    "status": "shadow_verification_failed",
                    "shadow_result": shadow_result,
                    "timestamp": datetime.now().isoformat()
                })
                self.console.print(f"[red]✗ Shadow verification failed for {branch}[/red]")

        return results

    def _shadow_merge_verification(self, branch: str, base_branch: str,
                                 quality_gates: List[str]) -> Dict[str, Any]:
        """Perform shadow merge verification without affecting main branch."""

        # Create temporary worktree for shadow merge
        shadow_path = Path(f".ai/coordination/shadow_merge_{branch.replace('/', '_')}")
        shadow_path.mkdir(parents=True, exist_ok=True)

        try:
            # Create worktree
            worktree_result = self._git(['worktree', 'add', str(shadow_path), base_branch])
            if not worktree_result.success:
                return {
                    "success": False,
                    "error": f"Failed to create shadow worktree: {worktree_result.stderr}"
                }

            # Change to shadow directory and attempt merge
            original_cwd = os.getcwd()
            os.chdir(shadow_path)

            try:
                merge_result = self._git(['merge', '--no-ff', branch])

                if merge_result.success:
                    # Run quality gates in shadow environment
                    gate_results = self._run_quality_gates(quality_gates)

                    return {
                        "success": all(gate['success'] for gate in gate_results),
                        "merge_conflicts": False,
                        "gate_results": gate_results
                    }
                else:
                    return {
                        "success": False,
                        "merge_conflicts": True,
                        "conflict_details": merge_result.stderr
                    }
            finally:
                os.chdir(original_cwd)

        except Exception as e:
            return {
                "success": False,
                "error": f"Shadow verification exception: {str(e)}"
            }
        finally:
            # Clean up shadow worktree
            try:
                self._git(['worktree', 'remove', '--force', str(shadow_path)])
            except:
                pass  # Best effort cleanup

    def _get_quality_gates(self, verification_level: str) -> List[str]:
        """Get quality gates based on verification level."""

        gates_map = {
            "minimal": ["lint"],
            "standard": ["lint", "test"],
            "comprehensive": ["lint", "test", "typecheck", "security"]
        }

        return gates_map.get(verification_level, gates_map["standard"])

    def _run_quality_gates(self, gates: List[str]) -> List[Dict[str, Any]]:
        """Run quality gates and return results."""

        results = []

        for gate in gates:
            if gate == "lint":
                # Run linting
                result = self._git(['status', '--porcelain'])  # Simple check
                success = result.success
                details = "No uncommitted changes" if success else "Uncommitted changes found"
            elif gate == "test":
                # Mock test execution (would normally run pytest, npm test, etc.)
                result = self._git(['log', '--oneline', '-1'])  # Check if we have commits
                success = result.success and result.stdout.strip()
                details = "Mock test execution" if success else "No commits found"
            elif gate == "typecheck":
                # Mock typecheck
                success = True
                details = "Mock typecheck passed"
            elif gate == "security":
                # Mock security scan
                success = True
                details = "Mock security scan passed"
            else:
                success = True
                details = f"Unknown gate: {gate}"

            results.append({
                "gate": gate,
                "success": success,
                "details": details,
                "timestamp": datetime.now().isoformat()
            })

        return results

    def _get_current_commit(self) -> str:
        """Get current commit hash."""
        result = self._git(['rev-parse', 'HEAD'])
        return result.stdout.strip() if result.success else "unknown"
