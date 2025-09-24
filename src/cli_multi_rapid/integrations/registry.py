"""Configuration registry for tool integrations."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ToolConfig:
    """Configuration for a single tool."""

    name: str
    path: str
    available: bool = False
    version: Optional[str] = None

    def __post_init__(self):
        self.available = os.path.exists(self.path) if self.path else False


@dataclass
class IntegrationConfig:
    """Configuration for tool integrations."""

    vcs: Dict[str, Any]
    containers: Dict[str, Any]
    editor: Dict[str, Any]
    js_runtime: Dict[str, Any]
    ai_cli: Dict[str, Any]
    python_quality: Dict[str, Any]
    precommit: Dict[str, Any]

    def __init__(self, paths: Dict[str, str]):
        """Initialize integration config from tool paths."""

        # VCS tools
        self.vcs = {
            "git": ToolConfig("git", paths.get("git", "")),
            "git_lfs": ToolConfig("git-lfs", paths.get("git-lfs", "")),
        }

        # Container tools
        self.containers = {
            "docker": ToolConfig("docker", paths.get("docker", "")),
        }

        # Editor tools
        self.editor = {
            "code": ToolConfig("code", paths.get("code", "")),
        }

        # JavaScript runtime tools
        self.js_runtime = {
            "node": ToolConfig("node", paths.get("node", "")),
            "pnpm": ToolConfig("pnpm", paths.get("pnpm", "")),
        }

        # AI CLI tools
        self.ai_cli = {
            "claude": ToolConfig("claude", paths.get("claude", "")),
            "aider": ToolConfig("aider", paths.get("aider", "")),
            "openai": ToolConfig("openai", paths.get("openai", "")),
        }

        # Python quality tools
        self.python_quality = {
            "python": ToolConfig("python", paths.get("python", "")),
            "yamllint": ToolConfig("yamllint", paths.get("yamllint", "")),
            "markdownlint": ToolConfig("markdownlint", paths.get("markdownlint", "")),
            "detect_secrets": ToolConfig(
                "detect-secrets", paths.get("detect-secrets", "")
            ),
            "gitleaks": ToolConfig("gitleaks", paths.get("gitleaks", "")),
        }

        # Pre-commit tools
        self.precommit = {
            "git": ToolConfig("git", paths.get("git", "")),
        }


def load_config(config_path: str) -> IntegrationConfig:
    """Load tool configuration from YAML file.

    Args:
        config_path: Path to the configuration file

    Returns:
        IntegrationConfig object with tool configurations

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML
    """
    config_file = Path(config_path)

    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}")
        # Return empty config
        return IntegrationConfig({})

    try:
        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Extract paths section
        paths = data.get("paths", {}) if data else {}

        logger.info(f"Loaded configuration for {len(paths)} tools from {config_path}")
        return IntegrationConfig(paths)

    except yaml.YAMLError as e:
        logger.error(f"Invalid YAML in config file {config_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading config file {config_path}: {e}")
        # Return empty config on error
        return IntegrationConfig({})


def get_tool_path(
    config: IntegrationConfig, category: str, tool_name: str
) -> Optional[str]:
    """Get path for a specific tool from configuration.

    Args:
        config: Integration configuration
        category: Tool category (vcs, containers, etc.)
        tool_name: Name of the tool

    Returns:
        Tool path if found, None otherwise
    """
    try:
        category_config = getattr(config, category, {})
        tool_config = category_config.get(tool_name)

        if tool_config and hasattr(tool_config, "path"):
            return tool_config.path if tool_config.available else None

    except Exception as e:
        logger.warning(f"Error getting tool path for {category}.{tool_name}: {e}")

    return None


def validate_tool_availability(config: IntegrationConfig) -> Dict[str, Dict[str, bool]]:
    """Validate availability of all configured tools.

    Args:
        config: Integration configuration

    Returns:
        Dictionary mapping category -> tool -> availability status
    """
    availability = {}

    categories = [
        "vcs",
        "containers",
        "editor",
        "js_runtime",
        "ai_cli",
        "python_quality",
        "precommit",
    ]

    for category in categories:
        category_config = getattr(config, category, {})
        availability[category] = {}

        for tool_name, tool_config in category_config.items():
            if hasattr(tool_config, "available"):
                availability[category][tool_name] = tool_config.available
            else:
                availability[category][tool_name] = False

    return availability
