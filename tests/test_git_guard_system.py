"""
Comprehensive tests for the Git guard and validation system.

Tests all critical paths to ensure the system prevents repository pollution
and maintains security.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.git_guard import GitGuard


class TestGitGuard:
    """Test the Git guard system"""

    def test_check_repo_location_safe(self):
        """Test safe repository location detection"""
        guard = GitGuard()

        # Mock a safe repository location
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "/home/user/project"

            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/home/user")

                success, message = guard.check_repo_location()
                assert success
                assert "Repository location OK" in message

    def test_check_repo_location_dangerous(self):
        """Test dangerous repository location detection (HOME)"""
        guard = GitGuard()

        # Mock HOME as repository root
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "/home/user"

            with patch("pathlib.Path.home") as mock_home:
                mock_home.return_value = Path("/home/user")

                success, message = guard.check_repo_location()
                assert not success
                assert "Repository root equals HOME" in message

    def test_check_secrets_ignored_safe(self):
        """Test that sensitive files are properly ignored"""
        guard = GitGuard()

        # Mock git check-ignore returning 0 (file is ignored)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0

            success, message = guard.check_secrets_ignored()
            assert success
            assert "properly handled" in message

    def test_check_secrets_ignored_dangerous(self):
        """Test detection of unignored sensitive files"""
        guard = GitGuard()

        # Mock git check-ignore returning 1 (file not ignored) and file exists
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1

            with patch.object(Path, "exists", return_value=True):
                success, message = guard.check_secrets_ignored()
                assert not success
                assert "security issues" in message.lower()

    def test_run_guard_script_success(self):
        """Test successful guard script execution"""
        guard = GitGuard()

        # Create a mock guard script
        script_path = Path("test_guard.ps1")

        with patch.object(guard, "get_guard_script", return_value=script_path):
            with patch.object(script_path, "exists", return_value=True):
                with patch.object(
                    guard, "run_script", return_value=(True, "Repo root OK")
                ):
                    success = guard.run_guard_check()
                    assert success

    def test_run_guard_script_failure(self):
        """Test guard script execution failure"""
        guard = GitGuard()

        script_path = Path("test_guard.ps1")

        with patch.object(guard, "get_guard_script", return_value=script_path):
            with patch.object(script_path, "exists", return_value=True):
                with patch.object(
                    guard, "run_script", return_value=(False, "Guard check failed")
                ):
                    success = guard.run_guard_check()
                    assert not success

    def test_full_check_all_pass(self):
        """Test full check when all validations pass"""
        guard = GitGuard()

        with patch.object(guard, "run_guard_check", return_value=True):
            with patch.object(guard, "run_validation_check", return_value=True):
                success = guard.full_check()
                assert success

    def test_full_check_guard_fails(self):
        """Test full check when guard check fails"""
        guard = GitGuard()

        with patch.object(guard, "run_guard_check", return_value=False):
            with patch.object(guard, "run_validation_check", return_value=True):
                success = guard.full_check()
                assert not success

    def test_platform_specific_script_selection(self):
        """Test that correct scripts are selected for each platform"""
        guard = GitGuard()

        # Test Windows
        with patch("platform.system", return_value="Windows"):
            guard.platform = "Windows"
            script = guard.get_guard_script()
            assert script.name == "guard_cwd.ps1"

            validate_script = guard.get_validate_script()
            assert validate_script.name == "validate_env.ps1"

        # Test Linux/Unix
        with patch("platform.system", return_value="Linux"):
            guard.platform = "Linux"
            script = guard.get_guard_script()
            assert script.name == "guard_cwd.sh"

            validate_script = guard.get_validate_script()
            assert validate_script.name == "validate_env.sh"


class TestGuardScripts:
    """Test the actual guard scripts"""

    def test_guard_script_exists(self):
        """Test that guard scripts exist"""
        scripts_dir = Path(__file__).parent.parent / "scripts"

        # Check PowerShell script
        ps_script = scripts_dir / "guard_cwd.ps1"
        assert ps_script.exists(), "PowerShell guard script missing"

        # Check Bash script
        sh_script = scripts_dir / "guard_cwd.sh"
        assert sh_script.exists(), "Bash guard script missing"

    def test_validation_script_exists(self):
        """Test that validation scripts exist"""
        scripts_dir = Path(__file__).parent.parent / "scripts"

        # Check PowerShell script
        ps_script = scripts_dir / "validate_env.ps1"
        assert ps_script.exists(), "PowerShell validation script missing"

        # Check Bash script
        sh_script = scripts_dir / "validate_env.sh"
        assert sh_script.exists(), "Bash validation script missing"

    def test_rescue_script_exists(self):
        """Test that rescue script exists"""
        scripts_dir = Path(__file__).parent.parent / "scripts"

        rescue_script = scripts_dir / "rescue_repo.ps1"
        assert rescue_script.exists(), "Rescue script missing"


class TestMakefileTargets:
    """Test Makefile targets for guard and validation"""

    def test_makefile_exists(self):
        """Test that Makefile exists"""
        makefile = Path(__file__).parent.parent / "Makefile"
        assert makefile.exists(), "Makefile missing"

    def test_makefile_contains_guard_targets(self):
        """Test that Makefile contains required targets"""
        makefile = Path(__file__).parent.parent / "Makefile"
        content = makefile.read_text()

        # Check for guard target
        assert "guard:" in content, "Makefile missing guard target"

        # Check for validate target
        assert "validate:" in content, "Makefile missing validate target"

        # Check for precommit target
        assert "precommit:" in content, "Makefile missing precommit target"


class TestDocumentation:
    """Test that documentation exists and is complete"""

    def test_agent_playbook_exists(self):
        """Test that Agent Git Playbook exists"""
        playbook = Path(__file__).parent.parent / "docs" / "AGENT_GIT_PLAYBOOK.md"
        assert playbook.exists(), "Agent Git Playbook missing"

    def test_contributing_guide_exists(self):
        """Test that CONTRIBUTING.md exists"""
        contributing = Path(__file__).parent.parent / "CONTRIBUTING.md"
        assert contributing.exists(), "CONTRIBUTING.md missing"

    def test_security_policy_exists(self):
        """Test that SECURITY.md exists"""
        security = Path(__file__).parent.parent / "SECURITY.md"
        assert security.exists(), "SECURITY.md missing"

    def test_agent_playbook_contains_invariants(self):
        """Test that Agent Playbook contains required invariants"""
        playbook = Path(__file__).parent.parent / "docs" / "AGENT_GIT_PLAYBOOK.md"
        content = playbook.read_text()

        # Check for hard invariants
        assert "Hard Invariants" in content
        assert "ABORT IF ANY FAIL" in content
        assert "git rev-parse --show-toplevel" in content
        assert "scripts/guard_cwd" in content

    def test_contributing_contains_hygiene_section(self):
        """Test that CONTRIBUTING.md contains hygiene guidelines"""
        contributing = Path(__file__).parent.parent / "CONTRIBUTING.md"
        content = contributing.read_text()

        assert "Repository Hygiene & Guardrails" in content
        assert "Never run Git from HOME" in content
        assert "Run hooks BEFORE commit" in content

    def test_security_contains_push_protection(self):
        """Test that SECURITY.md contains push protection info"""
        security = Path(__file__).parent.parent / "SECURITY.md"
        content = security.read_text()

        assert "Push Protection & Secret Rotation" in content
        assert "GH013" in content
        assert "rotate" in content.lower()


class TestIntegration:
    """Integration tests for the complete system"""

    def test_can_import_git_guard(self):
        """Test that GitGuard can be imported"""
        from tools.git_guard import GitGuard

        guard = GitGuard()
        assert guard is not None

    def test_guard_system_components_exist(self):
        """Test that all guard system components exist"""
        # Scripts
        scripts_dir = Path(__file__).parent.parent / "scripts"
        assert (scripts_dir / "guard_cwd.ps1").exists()
        assert (scripts_dir / "guard_cwd.sh").exists()
        assert (scripts_dir / "validate_env.ps1").exists()
        assert (scripts_dir / "validate_env.sh").exists()
        assert (scripts_dir / "rescue_repo.ps1").exists()

        # Documentation
        docs_dir = Path(__file__).parent.parent / "docs"
        assert (docs_dir / "AGENT_GIT_PLAYBOOK.md").exists()

        # Root documentation
        root_dir = Path(__file__).parent.parent
        assert (root_dir / "CONTRIBUTING.md").exists()
        assert (root_dir / "SECURITY.md").exists()
        assert (root_dir / "Makefile").exists()

        # Python components
        tools_dir = Path(__file__).parent.parent / "tools"
        assert (tools_dir / "git_guard.py").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
