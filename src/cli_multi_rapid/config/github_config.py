#!/usr/bin/env python3
"""
GitHub Configuration Management

Handles GitHub token management, API configuration, and integration setup
for the CLI Orchestrator.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple


class GitHubConfig:
    """GitHub configuration and token management."""

    def __init__(self):
        self.github_token = os.environ.get("GITHUB_TOKEN")
        self.github_api_base = "https://api.github.com"
        self.config_file = Path.home() / ".cli-orchestrator" / "github-config.json"

    def is_configured(self) -> bool:
        """Check if GitHub integration is properly configured."""
        return bool(self.github_token) and self.is_github_cli_available()

    def is_github_cli_available(self) -> bool:
        """Check if GitHub CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_repository_info(self) -> Optional[Dict[str, str]]:
        """Get current repository information from git remote."""
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                return self.parse_github_url(url)
        except Exception:
            pass
        return None

    def parse_github_url(self, url: str) -> Dict[str, str]:
        """Parse GitHub URL to extract owner and repo."""
        # Handle SSH format: git@github.com:owner/repo.git
        if url.startswith("git@github.com:"):
            repo_path = url.replace("git@github.com:", "").replace(".git", "")
        # Handle HTTPS format: https://github.com/owner/repo.git
        elif "github.com/" in url:
            repo_path = url.split("github.com/")[-1].replace(".git", "")
        else:
            return {
                "owner": "unknown",
                "repo": "unknown",
                "full_name": "unknown/unknown",
            }

        if "/" in repo_path:
            owner, repo = repo_path.split("/", 1)
            return {"owner": owner, "repo": repo, "full_name": f"{owner}/{repo}"}
        return {"owner": "unknown", "repo": "unknown", "full_name": "unknown/unknown"}

    def validate_token(self) -> Tuple[bool, str]:
        """Validate GitHub token by making a test API call."""
        if not self.github_token:
            return False, "No GitHub token found in environment"

        try:
            import requests

            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CLI-Orchestrator/1.0",
            }

            response = requests.get(
                f"{self.github_api_base}/user", headers=headers, timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get("login", "unknown")
                return True, f"Token valid for user: {username}"
            elif response.status_code == 401:
                return False, "Token is invalid or expired"
            else:
                return False, f"API error: {response.status_code}"

        except Exception as e:
            return False, f"Token validation failed: {str(e)}"

    def setup_configuration(self) -> Dict[str, str]:
        """Set up GitHub integration configuration."""
        config = {"status": "not_configured", "issues": [], "recommendations": []}

        # Check GitHub token
        if not self.github_token:
            config["issues"].append("GITHUB_TOKEN environment variable not set")
            config["recommendations"].append(
                "Set GITHUB_TOKEN environment variable with a GitHub personal access token"
            )
        else:
            is_valid, message = self.validate_token()
            if is_valid:
                config["token_status"] = "valid"
                config["token_user"] = (
                    message.split(": ")[-1] if ": " in message else "unknown"
                )
            else:
                config["issues"].append(f"GitHub token validation failed: {message}")
                config["recommendations"].append(
                    "Check your GITHUB_TOKEN and ensure it has proper permissions"
                )

        # Check GitHub CLI
        if not self.is_github_cli_available():
            config["issues"].append(
                "GitHub CLI (gh) not available or not authenticated"
            )
            config["recommendations"].append(
                "Install GitHub CLI and run 'gh auth login'"
            )
        else:
            config["github_cli_status"] = "available"

        # Check repository configuration
        repo_info = self.get_repository_info()
        if repo_info:
            config["repository"] = repo_info
        else:
            config["issues"].append(
                "Not in a GitHub repository or remote origin not set"
            )
            config["recommendations"].append(
                "Ensure you're in a git repository with GitHub remote origin"
            )

        # Set overall status
        if not config["issues"]:
            config["status"] = "configured"
        elif len(config["issues"]) <= 1:
            config["status"] = "partially_configured"
        else:
            config["status"] = "not_configured"

        return config

    def generate_token_instructions(self) -> str:
        """Generate instructions for creating a GitHub token."""
        return """
To set up GitHub integration:

1. Create a GitHub Personal Access Token:
   - Go to https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Select scopes: repo, workflow, read:org, read:user, read:discussion

2. Set the environment variable:
   - Windows: set GITHUB_TOKEN=your_token_here
   - Linux/Mac: export GITHUB_TOKEN=your_token_here
   - Or add to your shell profile for persistence

3. Install GitHub CLI (optional but recommended):
   - Visit https://cli.github.com/
   - Install and run: gh auth login

4. Verify configuration:
   - Run: cli-orchestrator config github --validate
"""

    def save_config(self, config: Dict) -> None:
        """Save configuration to local file."""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def load_config(self) -> Optional[Dict]:
        """Load configuration from local file."""
        if self.config_file.exists():
            try:
                with open(self.config_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def get_token_permissions(self) -> Optional[Dict[str, bool]]:
        """Check GitHub token permissions."""
        if not self.github_token:
            return None

        try:
            import requests

            headers = {
                "Authorization": f"token {self.github_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "CLI-Orchestrator/1.0",
            }

            # Check rate limit endpoint which shows scopes
            response = requests.get(
                f"{self.github_api_base}/rate_limit", headers=headers, timeout=10
            )

            if response.status_code == 200:
                scopes = response.headers.get("X-OAuth-Scopes", "").split(", ")
                return {
                    "repo": "repo" in scopes,
                    "workflow": "workflow" in scopes,
                    "read:org": "read:org" in scopes,
                    "read:user": "read:user" in scopes,
                    "read:discussion": "read:discussion" in scopes,
                }

        except Exception:
            pass

        return None


def validate_github_setup() -> Dict[str, any]:
    """Validate GitHub setup and return status report."""
    config = GitHubConfig()
    setup_info = config.setup_configuration()

    # Add permission check
    permissions = config.get_token_permissions()
    if permissions:
        setup_info["token_permissions"] = permissions
        missing_perms = [perm for perm, has_perm in permissions.items() if not has_perm]
        if missing_perms:
            setup_info["issues"].append(
                f"GitHub token missing permissions: {', '.join(missing_perms)}"
            )

    return setup_info


def get_github_config() -> GitHubConfig:
    """Get GitHub configuration instance."""
    return GitHubConfig()
