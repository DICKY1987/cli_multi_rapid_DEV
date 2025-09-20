#!/usr/bin/env python3
"""
GitHub Integration Adapter

Specialized adapter for comprehensive GitHub repository analysis, issue management,
PR reviews, and release operations with Claude AI integration.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


@dataclass
class GitHubAnalysisResult:
    """Result structure for GitHub analysis operations."""

    success: bool
    analysis_type: str
    data: Dict[str, Any]
    recommendations: List[str] = None
    issues_found: List[str] = None

    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []
        if self.issues_found is None:
            self.issues_found = []


class GitHubIntegrationAdapter(BaseAdapter):
    """Specialized adapter for GitHub repository analysis and automation."""

    def __init__(self) -> None:
        super().__init__(
            name="github_integration",
            adapter_type=AdapterType.DETERMINISTIC,
            description="GitHub repository analysis, issue automation, PR reviews, and release management",
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
            analysis_type = params.get("analysis_type", "repository")

            if analysis_type == "repository":
                result = self._perform_repository_analysis(params)
            elif analysis_type == "security":
                result = self._perform_security_analysis(params)
            elif analysis_type == "code_quality":
                result = self._perform_code_quality_analysis(params)
            elif analysis_type == "performance":
                result = self._perform_performance_analysis(params)
            elif analysis_type == "dependencies":
                result = self._perform_dependency_analysis(params)
            elif analysis_type == "workflow_health":
                result = self._analyze_workflow_health(params)
            elif analysis_type == "issue_triage":
                result = self._perform_issue_triage(params)
            elif analysis_type == "pr_automation":
                result = self._perform_pr_automation(params)
            elif analysis_type == "release_management":
                result = self._perform_release_management(params)
            else:
                result = GitHubAnalysisResult(
                    success=False,
                    analysis_type=analysis_type,
                    data={"error": f"Unknown analysis type: {analysis_type}"},
                )

            # Create artifact structure
            artifact = self._create_analysis_artifact(result, analysis_type)

            # Write artifact(s)
            artifacts = self._write_artifacts(emit_paths, artifact)

            return AdapterResult(
                success=result.success,
                tokens_used=0,
                artifacts=artifacts,
                output=json.dumps(artifact, indent=2),
                metadata={"analysis_type": analysis_type},
            )

        except Exception as e:
            return AdapterResult(success=False, error=f"github_integration failed: {e}")

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        params = self._extract_with_params(step)
        analysis_type = params.get("analysis_type", "repository")

        valid_analysis_types = {
            "repository",
            "security",
            "code_quality",
            "performance",
            "dependencies",
            "workflow_health",
            "issue_triage",
            "pr_automation",
            "release_management",
        }

        return analysis_type in valid_analysis_types

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate the token cost of executing this step."""
        return 0

    def is_available(self) -> bool:
        """Check if this adapter is available."""
        return bool(self.github_token)

    # GitHub API Helper Methods

    def _get_github_repo(self, params: Dict[str, Any]) -> str:
        """Get GitHub repository from params or git remote."""
        repo = params.get("repo")
        if repo:
            return repo

        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                if url.startswith("git@github.com:"):
                    return url.replace("git@github.com:", "").replace(".git", "")
                elif "github.com/" in url:
                    return url.split("github.com/")[-1].replace(".git", "")
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
            "User-Agent": "CLI-Orchestrator-GitHub-Integration/1.0",
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

    # Analysis Methods

    def _perform_repository_analysis(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Comprehensive repository analysis."""
        repo = self._get_github_repo(params)

        analysis_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "overview": {},
            "activity": {},
            "health_metrics": {},
            "recommendations": [],
        }

        # Repository overview
        repo_data = self._github_api_request(f"repos/{repo}")
        if "error" not in repo_data:
            analysis_data["overview"] = {
                "name": repo_data.get("name"),
                "description": repo_data.get("description"),
                "language": repo_data.get("language"),
                "size": repo_data.get("size", 0),
                "stars": repo_data.get("stargazers_count", 0),
                "forks": repo_data.get("forks_count", 0),
                "open_issues": repo_data.get("open_issues_count", 0),
                "watchers": repo_data.get("watchers_count", 0),
                "default_branch": repo_data.get("default_branch"),
                "created_at": repo_data.get("created_at"),
                "updated_at": repo_data.get("updated_at"),
                "pushed_at": repo_data.get("pushed_at"),
                "visibility": "private" if repo_data.get("private") else "public",
                "archived": repo_data.get("archived", False),
                "disabled": repo_data.get("disabled", False),
            }

        # Recent activity analysis
        commits = self._github_api_request(f"repos/{repo}/commits?per_page=50")
        if "error" not in commits and isinstance(commits, list):
            commit_dates = [
                c.get("commit", {}).get("committer", {}).get("date")
                for c in commits
                if c.get("commit")
            ]
            analysis_data["activity"] = {
                "recent_commits": len(commits),
                "last_commit": commit_dates[0] if commit_dates else None,
                "commit_frequency": self._calculate_commit_frequency(commit_dates),
                "contributors": len(
                    set(
                        c.get("author", {}).get("login")
                        for c in commits
                        if c.get("author")
                    )
                ),
            }

        # Health metrics
        prs = self._github_api_request(f"repos/{repo}/pulls?state=all&per_page=20")
        issues = self._github_api_request(f"repos/{repo}/issues?state=all&per_page=20")

        if "error" not in prs and "error" not in issues:
            analysis_data["health_metrics"] = {
                "open_prs": len([p for p in prs if p.get("state") == "open"]),
                "merged_prs_last_30d": self._count_recent_items(prs, "merged", 30),
                "open_issues": len(
                    [
                        i
                        for i in issues
                        if i.get("state") == "open" and "pull_request" not in i
                    ]
                ),
                "closed_issues_last_30d": self._count_recent_items(
                    issues, "closed", 30
                ),
            }

        # Generate recommendations
        recommendations = self._generate_repository_recommendations(analysis_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="repository",
            data=analysis_data,
            recommendations=recommendations,
        )

    def _perform_security_analysis(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Security-focused repository analysis."""
        repo = self._get_github_repo(params)

        security_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "vulnerability_alerts": {},
            "security_advisories": {},
            "branch_protection": {},
            "secrets_scanning": {},
            "dependency_vulnerabilities": {},
        }

        # Check vulnerability alerts
        alerts = self._github_api_request(f"repos/{repo}/vulnerability-alerts")
        if "error" not in alerts:
            security_data["vulnerability_alerts"] = alerts

        # Check security advisories
        advisories = self._github_api_request(f"repos/{repo}/security-advisories")
        if "error" not in advisories:
            security_data["security_advisories"] = advisories

        # Branch protection analysis
        default_branch = params.get("branch", "main")
        branch_protection = self._github_api_request(
            f"repos/{repo}/branches/{default_branch}/protection"
        )
        if "error" not in branch_protection:
            security_data["branch_protection"] = branch_protection

        issues_found = self._identify_security_issues(security_data)
        recommendations = self._generate_security_recommendations(security_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="security",
            data=security_data,
            recommendations=recommendations,
            issues_found=issues_found,
        )

    def _perform_code_quality_analysis(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Code quality analysis."""
        repo = self._get_github_repo(params)

        quality_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "languages": {},
            "file_structure": {},
            "documentation": {},
            "testing": {},
        }

        # Language breakdown
        languages = self._github_api_request(f"repos/{repo}/languages")
        if "error" not in languages:
            total_bytes = sum(languages.values())
            quality_data["languages"] = (
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

        # Check for documentation files
        contents = self._github_api_request(f"repos/{repo}/contents")
        if "error" not in contents and isinstance(contents, list):
            quality_data["documentation"] = self._analyze_documentation(contents)
            quality_data["file_structure"] = self._analyze_file_structure(contents)

        recommendations = self._generate_quality_recommendations(quality_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="code_quality",
            data=quality_data,
            recommendations=recommendations,
        )

    def _perform_performance_analysis(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Performance analysis of GitHub Actions and workflows."""
        repo = self._get_github_repo(params)

        performance_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "workflow_runs": {},
            "action_performance": {},
            "build_times": {},
        }

        # Analyze workflow runs
        workflow_runs = self._github_api_request(
            f"repos/{repo}/actions/runs?per_page=50"
        )
        if "error" not in workflow_runs and "workflow_runs" in workflow_runs:
            performance_data["workflow_runs"] = self._analyze_workflow_performance(
                workflow_runs["workflow_runs"]
            )

        recommendations = self._generate_performance_recommendations(performance_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="performance",
            data=performance_data,
            recommendations=recommendations,
        )

    def _perform_dependency_analysis(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Dependency analysis and vulnerability scanning."""
        repo = self._get_github_repo(params)

        dependency_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "dependencies": {},
            "vulnerabilities": {},
            "outdated_packages": {},
        }

        # Get dependency graph (requires special permissions)
        dependencies = self._github_api_request(f"repos/{repo}/dependency-graph/sbom")
        if "error" not in dependencies:
            dependency_data["dependencies"] = dependencies

        # Check for known vulnerabilities
        alerts = self._github_api_request(f"repos/{repo}/dependabot/alerts")
        if "error" not in alerts:
            dependency_data["vulnerabilities"] = alerts

        issues_found = self._identify_dependency_issues(dependency_data)
        recommendations = self._generate_dependency_recommendations(dependency_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="dependencies",
            data=dependency_data,
            recommendations=recommendations,
            issues_found=issues_found,
        )

    def _analyze_workflow_health(self, params: Dict[str, Any]) -> GitHubAnalysisResult:
        """Analyze GitHub Actions workflow health."""
        repo = self._get_github_repo(params)

        workflow_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "workflows": [],
            "success_rates": {},
            "failure_patterns": {},
        }

        # Get all workflows
        workflows = self._github_api_request(f"repos/{repo}/actions/workflows")
        if "error" not in workflows and "workflows" in workflows:
            for workflow in workflows["workflows"]:
                workflow_analysis = self._analyze_single_workflow(repo, workflow["id"])
                workflow_data["workflows"].append(workflow_analysis)

        recommendations = self._generate_workflow_recommendations(workflow_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="workflow_health",
            data=workflow_data,
            recommendations=recommendations,
        )

    def _perform_issue_triage(self, params: Dict[str, Any]) -> GitHubAnalysisResult:
        """Automated issue triage and categorization."""
        repo = self._get_github_repo(params)

        triage_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "issues": [],
            "categorization": {},
            "priority_suggestions": {},
        }

        # Get recent issues
        issues = self._github_api_request(f"repos/{repo}/issues?state=open&per_page=50")
        if "error" not in issues and isinstance(issues, list):
            for issue in issues:
                if "pull_request" not in issue:  # Filter out PRs
                    issue_analysis = self._analyze_issue(issue)
                    triage_data["issues"].append(issue_analysis)

        recommendations = self._generate_triage_recommendations(triage_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="issue_triage",
            data=triage_data,
            recommendations=recommendations,
        )

    def _perform_pr_automation(self, params: Dict[str, Any]) -> GitHubAnalysisResult:
        """Automated PR analysis and suggestions."""
        repo = self._get_github_repo(params)

        pr_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "open_prs": [],
            "review_suggestions": {},
            "merge_readiness": {},
        }

        # Get open PRs
        prs = self._github_api_request(f"repos/{repo}/pulls?state=open&per_page=20")
        if "error" not in prs and isinstance(prs, list):
            for pr in prs:
                pr_analysis = self._analyze_pr_for_automation(repo, pr)
                pr_data["open_prs"].append(pr_analysis)

        recommendations = self._generate_pr_recommendations(pr_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="pr_automation",
            data=pr_data,
            recommendations=recommendations,
        )

    def _perform_release_management(
        self, params: Dict[str, Any]
    ) -> GitHubAnalysisResult:
        """Release management analysis and automation."""
        repo = self._get_github_repo(params)

        release_data = {
            "repo": repo,
            "timestamp": datetime.utcnow().isoformat(),
            "latest_release": {},
            "release_cadence": {},
            "changelog_analysis": {},
        }

        # Get latest release
        latest = self._github_api_request(f"repos/{repo}/releases/latest")
        if "error" not in latest:
            release_data["latest_release"] = latest

        # Get all releases for cadence analysis
        releases = self._github_api_request(f"repos/{repo}/releases?per_page=10")
        if "error" not in releases and isinstance(releases, list):
            release_data["release_cadence"] = self._analyze_release_cadence(releases)

        recommendations = self._generate_release_recommendations(release_data)

        return GitHubAnalysisResult(
            success=True,
            analysis_type="release_management",
            data=release_data,
            recommendations=recommendations,
        )

    # Analysis Helper Methods

    def _calculate_commit_frequency(self, commit_dates: List[str]) -> Dict[str, Any]:
        """Calculate commit frequency metrics."""
        if not commit_dates:
            return {"daily": 0, "weekly": 0, "monthly": 0}

        now = datetime.utcnow()
        daily = weekly = monthly = 0

        for date_str in commit_dates:
            if date_str:
                try:
                    commit_date = datetime.fromisoformat(
                        date_str.replace("Z", "+00:00")
                    )
                    days_ago = (now - commit_date).days
                    if days_ago <= 1:
                        daily += 1
                    if days_ago <= 7:
                        weekly += 1
                    if days_ago <= 30:
                        monthly += 1
                except Exception:
                    continue

        return {"daily": daily, "weekly": weekly, "monthly": monthly}

    def _count_recent_items(self, items: List[Dict], state: str, days: int) -> int:
        """Count items in specified state within last N days."""
        if not items:
            return 0

        cutoff = datetime.utcnow() - timedelta(days=days)
        count = 0

        for item in items:
            if item.get("state") == state:
                date_field = "merged_at" if state == "merged" else "closed_at"
                date_str = item.get(date_field)
                if date_str:
                    try:
                        item_date = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                        if item_date >= cutoff:
                            count += 1
                    except Exception:
                        continue

        return count

    def _analyze_documentation(self, contents: List[Dict]) -> Dict[str, Any]:
        """Analyze repository documentation."""
        doc_files = ["README.md", "CONTRIBUTING.md", "LICENSE", "CHANGELOG.md", "docs/"]
        found_docs = {}

        for item in contents:
            name = item.get("name", "")
            if any(doc in name.upper() for doc in [d.upper() for d in doc_files]):
                found_docs[name] = {
                    "type": item.get("type"),
                    "size": item.get("size", 0),
                }

        return {
            "found_files": found_docs,
            "documentation_score": len(found_docs) / len(doc_files),
        }

    def _analyze_file_structure(self, contents: List[Dict]) -> Dict[str, Any]:
        """Analyze repository file structure."""
        structure = {
            "total_files": len(contents),
            "directories": 0,
            "files": 0,
            "config_files": 0,
        }

        config_patterns = [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"]

        for item in contents:
            if item.get("type") == "dir":
                structure["directories"] += 1
            else:
                structure["files"] += 1
                name = item.get("name", "").lower()
                if any(pattern in name for pattern in config_patterns):
                    structure["config_files"] += 1

        return structure

    def _analyze_workflow_performance(
        self, workflow_runs: List[Dict]
    ) -> Dict[str, Any]:
        """Analyze workflow performance metrics."""
        if not workflow_runs:
            return {}

        total_runs = len(workflow_runs)
        successful = sum(
            1 for run in workflow_runs if run.get("conclusion") == "success"
        )
        failed = sum(1 for run in workflow_runs if run.get("conclusion") == "failure")

        durations = []
        for run in workflow_runs:
            created = run.get("created_at")
            updated = run.get("updated_at")
            if created and updated:
                try:
                    start = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                    duration = (end - start).total_seconds()
                    durations.append(duration)
                except Exception:
                    continue

        avg_duration = sum(durations) / len(durations) if durations else 0

        return {
            "total_runs": total_runs,
            "success_rate": (successful / total_runs) * 100 if total_runs > 0 else 0,
            "failure_rate": (failed / total_runs) * 100 if total_runs > 0 else 0,
            "average_duration_seconds": avg_duration,
            "average_duration_minutes": avg_duration / 60,
        }

    def _analyze_single_workflow(self, repo: str, workflow_id: int) -> Dict[str, Any]:
        """Analyze a single workflow."""
        workflow = self._github_api_request(
            f"repos/{repo}/actions/workflows/{workflow_id}"
        )
        runs = self._github_api_request(
            f"repos/{repo}/actions/workflows/{workflow_id}/runs?per_page=20"
        )

        analysis = {
            "id": workflow_id,
            "name": workflow.get("name", "Unknown"),
            "state": workflow.get("state", "unknown"),
            "runs_analysis": {},
        }

        if "error" not in runs and "workflow_runs" in runs:
            analysis["runs_analysis"] = self._analyze_workflow_performance(
                runs["workflow_runs"]
            )

        return analysis

    def _analyze_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single issue for triage."""
        title = issue.get("title", "")
        body = issue.get("body", "")
        labels = [label.get("name") for label in issue.get("labels", [])]

        # Simple categorization based on keywords
        category = "general"
        priority = "medium"

        if any(word in title.lower() for word in ["bug", "error", "crash", "fail"]):
            category = "bug"
            priority = "high"
        elif any(
            word in title.lower() for word in ["feature", "enhancement", "improvement"]
        ):
            category = "enhancement"
        elif any(word in title.lower() for word in ["question", "help", "how"]):
            category = "question"
            priority = "low"
        elif any(word in title.lower() for word in ["urgent", "critical", "blocking"]):
            priority = "critical"

        return {
            "number": issue.get("number"),
            "title": title,
            "category": category,
            "priority": priority,
            "labels": labels,
            "created_at": issue.get("created_at"),
            "updated_at": issue.get("updated_at"),
            "comments": issue.get("comments", 0),
            "assignees": [
                assignee.get("login") for assignee in issue.get("assignees", [])
            ],
        }

    def _analyze_pr_for_automation(
        self, repo: str, pr: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze PR for automation opportunities."""
        pr_number = pr.get("number")

        # Get PR details
        files = self._github_api_request(f"repos/{repo}/pulls/{pr_number}/files")
        reviews = self._github_api_request(f"repos/{repo}/pulls/{pr_number}/reviews")

        analysis = {
            "number": pr_number,
            "title": pr.get("title"),
            "state": pr.get("state"),
            "author": pr.get("user", {}).get("login"),
            "created_at": pr.get("created_at"),
            "updated_at": pr.get("updated_at"),
            "mergeable": pr.get("mergeable"),
            "checks_status": "unknown",
            "review_status": "pending",
            "file_changes": {},
        }

        if "error" not in files and isinstance(files, list):
            analysis["file_changes"] = {
                "total_files": len(files),
                "additions": sum(f.get("additions", 0) for f in files),
                "deletions": sum(f.get("deletions", 0) for f in files),
                "changes": sum(f.get("changes", 0) for f in files),
            }

        if "error" not in reviews and isinstance(reviews, list):
            approved = sum(1 for r in reviews if r.get("state") == "APPROVED")
            changes_requested = sum(
                1 for r in reviews if r.get("state") == "CHANGES_REQUESTED"
            )

            if approved > 0 and changes_requested == 0:
                analysis["review_status"] = "approved"
            elif changes_requested > 0:
                analysis["review_status"] = "changes_requested"

        return analysis

    def _analyze_release_cadence(self, releases: List[Dict]) -> Dict[str, Any]:
        """Analyze release cadence and patterns."""
        if len(releases) < 2:
            return {"insufficient_data": True}

        intervals = []
        for i in range(len(releases) - 1):
            current = releases[i].get("published_at")
            previous = releases[i + 1].get("published_at")

            if current and previous:
                try:
                    current_date = datetime.fromisoformat(
                        current.replace("Z", "+00:00")
                    )
                    previous_date = datetime.fromisoformat(
                        previous.replace("Z", "+00:00")
                    )
                    interval = (current_date - previous_date).days
                    intervals.append(interval)
                except Exception:
                    continue

        if not intervals:
            return {"insufficient_data": True}

        avg_interval = sum(intervals) / len(intervals)

        return {
            "total_releases": len(releases),
            "average_interval_days": avg_interval,
            "last_release": releases[0].get("published_at"),
            "release_frequency": (
                "frequent"
                if avg_interval < 30
                else "moderate" if avg_interval < 90 else "infrequent"
            ),
        }

    # Recommendation Generation Methods

    def _generate_repository_recommendations(
        self, analysis_data: Dict[str, Any]
    ) -> List[str]:
        """Generate repository improvement recommendations."""
        recommendations = []

        overview = analysis_data.get("overview", {})
        activity = analysis_data.get("activity", {})
        health = analysis_data.get("health_metrics", {})

        if not overview.get("description"):
            recommendations.append(
                "Add a repository description to help users understand the project's purpose"
            )

        if activity.get("commit_frequency", {}).get("weekly", 0) == 0:
            recommendations.append(
                "Consider increasing development activity - no commits in the last week"
            )

        open_issues = health.get("open_issues", 0)
        if open_issues > 20:
            recommendations.append(
                f"High number of open issues ({open_issues}) - consider issue triage and resolution"
            )

        open_prs = health.get("open_prs", 0)
        if open_prs > 10:
            recommendations.append(
                f"High number of open PRs ({open_prs}) - consider reviewing and merging"
            )

        return recommendations

    def _generate_security_recommendations(
        self, security_data: Dict[str, Any]
    ) -> List[str]:
        """Generate security improvement recommendations."""
        recommendations = []

        branch_protection = security_data.get("branch_protection", {})
        if "error" in branch_protection:
            recommendations.append(
                "Enable branch protection rules for the default branch"
            )

        vulnerability_alerts = security_data.get("vulnerability_alerts", {})
        if vulnerability_alerts and "error" not in vulnerability_alerts:
            recommendations.append("Review and address vulnerability alerts")

        recommendations.append("Enable Dependabot security updates")
        recommendations.append("Consider enabling GitHub Advanced Security features")

        return recommendations

    def _generate_quality_recommendations(
        self, quality_data: Dict[str, Any]
    ) -> List[str]:
        """Generate code quality recommendations."""
        recommendations = []

        docs = quality_data.get("documentation", {})
        doc_score = docs.get("documentation_score", 0)

        if doc_score < 0.5:
            recommendations.append(
                "Improve documentation - missing key files like README, CONTRIBUTING, or LICENSE"
            )

        if "README.md" not in docs.get("found_files", {}):
            recommendations.append("Add a README.md file to document your project")

        if "LICENSE" not in docs.get("found_files", {}):
            recommendations.append("Add a LICENSE file to clarify usage rights")

        return recommendations

    def _generate_performance_recommendations(
        self, performance_data: Dict[str, Any]
    ) -> List[str]:
        """Generate performance improvement recommendations."""
        recommendations = []

        workflow_runs = performance_data.get("workflow_runs", {})
        success_rate = workflow_runs.get("success_rate", 100)

        if success_rate < 80:
            recommendations.append(
                f"Improve workflow reliability - current success rate is {success_rate:.1f}%"
            )

        avg_duration = workflow_runs.get("average_duration_minutes", 0)
        if avg_duration > 30:
            recommendations.append(
                f"Optimize workflow performance - average duration is {avg_duration:.1f} minutes"
            )

        return recommendations

    def _generate_dependency_recommendations(
        self, dependency_data: Dict[str, Any]
    ) -> List[str]:
        """Generate dependency management recommendations."""
        recommendations = []

        vulnerabilities = dependency_data.get("vulnerabilities", {})
        if vulnerabilities and "error" not in vulnerabilities:
            recommendations.append(
                "Address dependency vulnerabilities found by Dependabot"
            )

        recommendations.append("Keep dependencies up to date")
        recommendations.append("Consider using dependency scanning tools")

        return recommendations

    def _generate_workflow_recommendations(
        self, workflow_data: Dict[str, Any]
    ) -> List[str]:
        """Generate workflow improvement recommendations."""
        recommendations = []

        workflows = workflow_data.get("workflows", [])

        failed_workflows = [
            w
            for w in workflows
            if w.get("runs_analysis", {}).get("success_rate", 100) < 80
        ]
        if failed_workflows:
            recommendations.append("Fix failing workflows to improve CI/CD reliability")

        if not workflows:
            recommendations.append("Consider adding GitHub Actions workflows for CI/CD")

        return recommendations

    def _generate_triage_recommendations(
        self, triage_data: Dict[str, Any]
    ) -> List[str]:
        """Generate issue triage recommendations."""
        recommendations = []

        issues = triage_data.get("issues", [])
        critical_issues = [i for i in issues if i.get("priority") == "critical"]

        if critical_issues:
            recommendations.append(
                f"Address {len(critical_issues)} critical issues immediately"
            )

        old_issues = [i for i in issues if self._is_old_issue(i.get("created_at"))]
        if old_issues:
            recommendations.append(
                f"Review {len(old_issues)} stale issues (>90 days old)"
            )

        return recommendations

    def _generate_pr_recommendations(self, pr_data: Dict[str, Any]) -> List[str]:
        """Generate PR automation recommendations."""
        recommendations = []

        open_prs = pr_data.get("open_prs", [])
        approved_prs = [pr for pr in open_prs if pr.get("review_status") == "approved"]

        if approved_prs:
            recommendations.append(f"Consider merging {len(approved_prs)} approved PRs")

        stale_prs = [pr for pr in open_prs if self._is_old_pr(pr.get("created_at"))]
        if stale_prs:
            recommendations.append(f"Review {len(stale_prs)} stale PRs (>30 days old)")

        return recommendations

    def _generate_release_recommendations(
        self, release_data: Dict[str, Any]
    ) -> List[str]:
        """Generate release management recommendations."""
        recommendations = []

        cadence = release_data.get("release_cadence", {})
        frequency = cadence.get("release_frequency", "unknown")

        if frequency == "infrequent":
            recommendations.append(
                "Consider more frequent releases for better user experience"
            )

        latest = release_data.get("latest_release", {})
        if not latest or "error" in latest:
            recommendations.append("Create your first release to mark stable versions")

        return recommendations

    # Utility Methods

    def _identify_security_issues(self, security_data: Dict[str, Any]) -> List[str]:
        """Identify security issues from analysis."""
        issues = []

        if "error" in security_data.get("branch_protection", {}):
            issues.append("No branch protection enabled")

        vulnerability_alerts = security_data.get("vulnerability_alerts", {})
        if vulnerability_alerts and "error" not in vulnerability_alerts:
            issues.append("Vulnerability alerts present")

        return issues

    def _identify_dependency_issues(self, dependency_data: Dict[str, Any]) -> List[str]:
        """Identify dependency issues from analysis."""
        issues = []

        vulnerabilities = dependency_data.get("vulnerabilities", {})
        if vulnerabilities and "error" not in vulnerabilities:
            issues.append("Dependency vulnerabilities found")

        return issues

    def _is_old_issue(self, created_at: str) -> bool:
        """Check if issue is older than 90 days."""
        if not created_at:
            return False
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return (datetime.utcnow() - created).days > 90
        except Exception:
            return False

    def _is_old_pr(self, created_at: str) -> bool:
        """Check if PR is older than 30 days."""
        if not created_at:
            return False
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            return (datetime.utcnow() - created).days > 30
        except Exception:
            return False

    def _create_analysis_artifact(
        self, result: GitHubAnalysisResult, analysis_type: str
    ) -> Dict[str, Any]:
        """Create structured artifact from analysis result."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "analysis_type": analysis_type,
            "success": result.success,
            "data": result.data,
            "recommendations": result.recommendations,
            "issues_found": result.issues_found,
            "metadata": {"adapter": "github_integration", "version": "1.0"},
        }

    def _write_artifacts(self, emit_paths: List[str], obj: Dict[str, Any]) -> List[str]:
        """Write artifacts to specified paths."""
        written: List[str] = []
        for p in emit_paths:
            dest = Path(p)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
            written.append(str(dest))
        return written
