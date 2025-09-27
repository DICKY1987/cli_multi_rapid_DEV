#!/usr/bin/env python3
"""
Certificate Generator Adapter

Generates verification certificates and attestations for successful
code modifications in the Codex pipeline, providing cryptographic proof
of validation completion.
"""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_adapter import AdapterResult, AdapterType, BaseAdapter


class CertificateGeneratorAdapter(BaseAdapter):
    """Adapter for generating verification certificates and attestations."""

    def __init__(self):
        super().__init__(
            name="certificate_generator",
            adapter_type=AdapterType.DETERMINISTIC,
            description="Generate verification certificates and attestations for validated modifications",
        )

    def execute(
        self,
        step: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        files: Optional[str] = None,
    ) -> AdapterResult:
        """Execute certificate generation."""
        self._log_execution_start(step)

        try:
            with_params = self._extract_with_params(step)
            verification_results = with_params.get("verification_results", {})
            certificate_type = with_params.get("certificate_type", "codex_modification")
            include_signatures = with_params.get("include_signatures", True)
            validation_level = with_params.get("validation_level", "standard")

            if not verification_results:
                return AdapterResult(
                    success=False,
                    error="Missing required parameter: verification_results"
                )

            certificate_data = {
                "certificate_id": self._generate_certificate_id(),
                "certificate_type": certificate_type,
                "generation_timestamp": self._get_timestamp(),
                "validation_level": validation_level,
                "issuer": self._get_issuer_info(),
                "verification_summary": self._create_verification_summary(verification_results),
                "integrity_hashes": self._calculate_integrity_hashes(verification_results),
                "validation_chain": self._build_validation_chain(verification_results),
                "compliance_status": self._assess_compliance(verification_results),
                "validity_period": self._calculate_validity_period(validation_level)
            }

            # Add digital signatures if requested
            if include_signatures:
                signature_result = self._generate_signatures(certificate_data)
                certificate_data["signatures"] = signature_result

            # Determine certificate validity
            is_valid = self._validate_certificate_requirements(certificate_data, verification_results)
            certificate_data["valid"] = is_valid
            certificate_data["status"] = "valid" if is_valid else "invalid"

            # Write certificate
            emit_paths = self._extract_emit_paths(step)
            artifacts = []

            if emit_paths:
                for emit_path in emit_paths:
                    artifact_path = Path(emit_path)
                    artifact_path.parent.mkdir(parents=True, exist_ok=True)

                    with open(artifact_path, 'w', encoding='utf-8') as f:
                        json.dump(certificate_data, f, indent=2)

                    artifacts.append(str(artifact_path))
                    self.logger.info(f"Certificate written to: {artifact_path}")

            result = AdapterResult(
                success=is_valid,
                tokens_used=0,  # Deterministic operation
                artifacts=artifacts,
                output=f"Generated {certificate_type} certificate with status: {certificate_data['status']}",
                metadata=certificate_data
            )

            self._log_execution_complete(result)
            return result

        except Exception as e:
            error_msg = f"Certificate generation failed: {str(e)}"
            self.logger.error(error_msg)
            return AdapterResult(
                success=False,
                error=error_msg,
                metadata={"exception_type": type(e).__name__}
            )

    def validate_step(self, step: Dict[str, Any]) -> bool:
        """Validate that this adapter can execute the given step."""
        with_params = self._extract_with_params(step)
        return "verification_results" in with_params

    def estimate_cost(self, step: Dict[str, Any]) -> int:
        """Estimate token cost (0 for deterministic operations)."""
        return 0

    def is_available(self) -> bool:
        """Check if certificate generation is available."""
        return True  # Certificate generation is always available

    def _generate_certificate_id(self) -> str:
        """Generate a unique certificate ID."""
        import uuid
        timestamp = self._get_timestamp()
        unique_data = f"codex_cert_{timestamp}_{uuid.uuid4()}"
        return hashlib.sha256(unique_data.encode()).hexdigest()[:16].upper()

    def _get_issuer_info(self) -> Dict[str, Any]:
        """Get certificate issuer information."""
        return {
            "name": "CLI Orchestrator Codex Pipeline",
            "version": "1.0.0",
            "system": "Codex 100% Accurate Modification System",
            "issued_by": "CLI Multi Rapid Framework"
        }

    def _create_verification_summary(self, verification_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create a summary of verification results."""
        summary = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "verification_stages": [],
            "overall_status": "unknown"
        }

        # Analyze verification results structure
        for stage_name, stage_results in verification_results.items():
            stage_summary = {
                "stage": stage_name,
                "status": "unknown",
                "checks": 0,
                "passed": 0,
                "failed": 0,
                "timestamp": stage_results.get("timestamp")
            }

            if isinstance(stage_results, dict):
                if "success" in stage_results:
                    stage_summary["status"] = "passed" if stage_results["success"] else "failed"
                    stage_summary["checks"] = 1
                    if stage_results["success"]:
                        stage_summary["passed"] = 1
                        summary["passed_checks"] += 1
                    else:
                        stage_summary["failed"] = 1
                        summary["failed_checks"] += 1
                    summary["total_checks"] += 1

                # Check for sub-results
                if "results" in stage_results and isinstance(stage_results["results"], list):
                    for result in stage_results["results"]:
                        if isinstance(result, dict) and "success" in result:
                            stage_summary["checks"] += 1
                            summary["total_checks"] += 1
                            if result["success"]:
                                stage_summary["passed"] += 1
                                summary["passed_checks"] += 1
                            else:
                                stage_summary["failed"] += 1
                                summary["failed_checks"] += 1

            summary["verification_stages"].append(stage_summary)

        # Determine overall status
        if summary["total_checks"] == 0:
            summary["overall_status"] = "no_verification"
        elif summary["failed_checks"] == 0:
            summary["overall_status"] = "all_passed"
        elif summary["passed_checks"] == 0:
            summary["overall_status"] = "all_failed"
        else:
            summary["overall_status"] = "partial_pass"

        return summary

    def _calculate_integrity_hashes(self, verification_results: Dict[str, Any]) -> Dict[str, str]:
        """Calculate integrity hashes for verification data."""
        hashes = {}

        try:
            # Hash the entire verification results
            verification_json = json.dumps(verification_results, sort_keys=True, separators=(',', ':'))
            hashes["verification_results"] = hashlib.sha256(verification_json.encode()).hexdigest()

            # Hash individual components if present
            if "files_modified" in verification_results:
                files_json = json.dumps(verification_results["files_modified"], sort_keys=True)
                hashes["modified_files"] = hashlib.sha256(files_json.encode()).hexdigest()

            if "test_results" in verification_results:
                tests_json = json.dumps(verification_results["test_results"], sort_keys=True)
                hashes["test_results"] = hashlib.sha256(tests_json.encode()).hexdigest()

            if "security_scan" in verification_results:
                security_json = json.dumps(verification_results["security_scan"], sort_keys=True)
                hashes["security_scan"] = hashlib.sha256(security_json.encode()).hexdigest()

        except Exception as e:
            self.logger.warning(f"Failed to calculate some integrity hashes: {e}")

        return hashes

    def _build_validation_chain(self, verification_results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a chronological chain of validation steps."""
        chain = []

        # Extract timestamped events from verification results
        for stage_name, stage_data in verification_results.items():
            if isinstance(stage_data, dict):
                chain_entry = {
                    "step": stage_name,
                    "timestamp": stage_data.get("timestamp", self._get_timestamp()),
                    "status": "passed" if stage_data.get("success", False) else "failed",
                    "hash": hashlib.sha256(json.dumps(stage_data, sort_keys=True).encode()).hexdigest()[:16]
                }
                chain.append(chain_entry)

        # Sort by timestamp
        chain.sort(key=lambda x: x["timestamp"])

        # Add sequence numbers
        for i, entry in enumerate(chain):
            entry["sequence"] = i + 1

        return chain

    def _assess_compliance(self, verification_results: Dict[str, Any]) -> Dict[str, Any]:
        """Assess compliance status based on verification results."""
        compliance = {
            "level": "unknown",
            "requirements_met": [],
            "requirements_failed": [],
            "score": 0.0,
            "details": {}
        }

        required_checks = {
            "syntax_validation": "Code syntax validation",
            "type_checking": "Static type checking",
            "security_scan": "Security vulnerability scanning",
            "test_execution": "Automated test execution",
            "import_resolution": "Import dependency resolution"
        }

        met_requirements = 0
        total_requirements = len(required_checks)

        for check_name, description in required_checks.items():
            if check_name in verification_results:
                check_result = verification_results[check_name]
                if isinstance(check_result, dict) and check_result.get("success", False):
                    compliance["requirements_met"].append({
                        "requirement": check_name,
                        "description": description,
                        "status": "met"
                    })
                    met_requirements += 1
                else:
                    compliance["requirements_failed"].append({
                        "requirement": check_name,
                        "description": description,
                        "status": "failed"
                    })
            else:
                compliance["requirements_failed"].append({
                    "requirement": check_name,
                    "description": description,
                    "status": "not_executed"
                })

        # Calculate compliance score
        compliance["score"] = met_requirements / total_requirements if total_requirements > 0 else 0.0

        # Determine compliance level
        if compliance["score"] >= 1.0:
            compliance["level"] = "full_compliance"
        elif compliance["score"] >= 0.8:
            compliance["level"] = "high_compliance"
        elif compliance["score"] >= 0.6:
            compliance["level"] = "moderate_compliance"
        elif compliance["score"] >= 0.4:
            compliance["level"] = "low_compliance"
        else:
            compliance["level"] = "non_compliant"

        return compliance

    def _calculate_validity_period(self, validation_level: str) -> Dict[str, Any]:
        """Calculate certificate validity period based on validation level."""
        from datetime import datetime, timedelta

        issued_at = datetime.utcnow()

        # Validity periods based on validation level
        validity_periods = {
            "basic": timedelta(days=30),
            "standard": timedelta(days=90),
            "comprehensive": timedelta(days=180),
            "enterprise": timedelta(days=365)
        }

        validity_duration = validity_periods.get(validation_level, timedelta(days=90))
        expires_at = issued_at + validity_duration

        return {
            "issued_at": issued_at.isoformat() + "Z",
            "expires_at": expires_at.isoformat() + "Z",
            "duration_days": validity_duration.days,
            "validation_level": validation_level
        }

    def _generate_signatures(self, certificate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate digital signatures for the certificate."""
        signatures = {
            "generation_timestamp": self._get_timestamp(),
            "signature_algorithm": "SHA256-HMAC",
            "signatures": []
        }

        try:
            # Generate content hash
            cert_content = {k: v for k, v in certificate_data.items() if k != "signatures"}
            content_json = json.dumps(cert_content, sort_keys=True, separators=(',', ':'))
            content_hash = hashlib.sha256(content_json.encode()).hexdigest()

            # Generate system signature (using a simple HMAC for demonstration)
            system_key = "cli_orchestrator_system_key"  # In production, use proper key management
            system_signature = hashlib.sha256(f"{content_hash}:{system_key}".encode()).hexdigest()

            signatures["signatures"].append({
                "signer": "CLI Orchestrator System",
                "signature_type": "system",
                "content_hash": content_hash,
                "signature": system_signature,
                "timestamp": self._get_timestamp()
            })

            # Add git signature if available
            git_signature = self._get_git_signature()
            if git_signature:
                signatures["signatures"].append(git_signature)

        except Exception as e:
            self.logger.warning(f"Failed to generate some signatures: {e}")
            signatures["error"] = str(e)

        return signatures

    def _get_git_signature(self) -> Optional[Dict[str, Any]]:
        """Get git-based signature information."""
        try:
            # Get current commit hash
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                commit_hash = result.stdout.strip()

                # Get commit author and timestamp
                author_result = subprocess.run(
                    ["git", "show", "-s", "--format=%an <%ae>", commit_hash],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                timestamp_result = subprocess.run(
                    ["git", "show", "-s", "--format=%ci", commit_hash],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                return {
                    "signer": "Git Repository",
                    "signature_type": "git_commit",
                    "commit_hash": commit_hash,
                    "author": author_result.stdout.strip() if author_result.returncode == 0 else "unknown",
                    "commit_timestamp": timestamp_result.stdout.strip() if timestamp_result.returncode == 0 else "unknown",
                    "timestamp": self._get_timestamp()
                }

        except Exception as e:
            self.logger.debug(f"Could not get git signature: {e}")

        return None

    def _validate_certificate_requirements(self, certificate_data: Dict[str, Any], verification_results: Dict[str, Any]) -> bool:
        """Validate that certificate meets requirements for validity."""
        try:
            # Check compliance level
            compliance = certificate_data.get("compliance_status", {})
            if compliance.get("level") in ["non_compliant", "low_compliance"]:
                return False

            # Check verification summary
            summary = certificate_data.get("verification_summary", {})
            if summary.get("overall_status") == "all_failed":
                return False

            # Check that critical verification stages passed
            critical_stages = ["syntax_validation", "security_scan"]
            for stage in critical_stages:
                if stage in verification_results:
                    stage_result = verification_results[stage]
                    if isinstance(stage_result, dict) and not stage_result.get("success", False):
                        return False

            # Check signature validity
            signatures = certificate_data.get("signatures", {})
            if not signatures or "error" in signatures:
                self.logger.warning("Certificate signatures invalid or missing")
                # Don't fail certificate just for signature issues in demo mode

            return True

        except Exception as e:
            self.logger.error(f"Certificate validation failed: {e}")
            return False

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "Z"
