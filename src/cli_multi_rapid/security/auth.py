"""
Authentication management for CLI Orchestrator.

Handles JWT token generation/validation and API key management
for secure access to CLI Orchestrator services.
"""

import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional, List

try:
    import jwt

    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False


class JWTManager:
    """Manages JWT token creation and validation."""

    def __init__(self, secret_key: str, expiry_hours: int = 24):
        if not JWT_AVAILABLE:
            raise ImportError("PyJWT is required for JWT authentication")

        self.secret_key = secret_key
        self.expiry_hours = expiry_hours
        self.algorithm = "HS256"

    def create_token(self, user) -> str:
        """Create JWT token for user."""
        payload = {
            "user_id": user.id,
            "username": user.username,
            "roles": [role.value for role in user.roles],
            "permissions": [perm.value for perm in user.permissions],
            "exp": time.time() + (self.expiry_hours * 3600),
            "iat": time.time(),
            "iss": "cli-orchestrator",
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def decode_token_without_verification(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode token without verification (for debugging)."""
        try:
            return jwt.decode(
                token, options={"verify_signature": False, "verify_exp": False}
            )
        except:
            return None


class APIKeyManager:
    """Manages API keys for programmatic access."""

    def __init__(self, storage_file: Path):
        self.storage_file = storage_file
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._load_keys()

    def create_key(
        self, user_id: str, description: str = "", expiry_days: Optional[int] = None
    ) -> str:
        """Create new API key."""
        api_key = f"clio_{secrets.token_urlsafe(32)}"

        key_data = {
            "user_id": user_id,
            "description": description,
            "created_at": time.time(),
            "expires_at": time.time() + (expiry_days * 86400) if expiry_days else None,
            "last_used": None,
            "is_active": True,
        }

        self._keys[api_key] = key_data
        self._save_keys()

        return api_key

    def verify_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        """Verify API key and return key information."""
        key_data = self._keys.get(api_key)
        if not key_data:
            return None

        # Check if key is active
        if not key_data.get("is_active", False):
            return None

        # Check expiration
        expires_at = key_data.get("expires_at")
        if expires_at and time.time() > expires_at:
            return None

        # Update last used timestamp
        key_data["last_used"] = time.time()
        self._save_keys()

        return key_data

    def revoke_key(self, api_key: str) -> bool:
        """Revoke API key."""
        if api_key in self._keys:
            self._keys[api_key]["is_active"] = False
            self._save_keys()
            return True
        return False

    def list_keys_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """List API keys for user."""
        user_keys = []
        for api_key, key_data in self._keys.items():
            if key_data["user_id"] == user_id:
                # Don't include the actual key in the response
                safe_key_data = key_data.copy()
                safe_key_data["key_prefix"] = api_key[:12] + "..."
                user_keys.append(safe_key_data)
        return user_keys

    def cleanup_expired_keys(self) -> int:
        """Remove expired keys and return count."""
        current_time = time.time()
        expired_keys = []

        for api_key, key_data in self._keys.items():
            expires_at = key_data.get("expires_at")
            if expires_at and current_time > expires_at:
                expired_keys.append(api_key)

        for api_key in expired_keys:
            del self._keys[api_key]

        if expired_keys:
            self._save_keys()

        return len(expired_keys)

    def _load_keys(self) -> None:
        """Load API keys from storage."""
        if not self.storage_file.exists():
            return

        try:
            with open(self.storage_file) as f:
                self._keys = json.load(f)
        except Exception as e:
            import logging

            logging.error(f"Failed to load API keys: {e}")

    def _save_keys(self) -> None:
        """Save API keys to storage."""
        self.storage_file.parent.mkdir(exist_ok=True)

        try:
            with open(self.storage_file, "w") as f:
                json.dump(self._keys, f, indent=2)
        except Exception as e:
            import logging

            logging.error(f"Failed to save API keys: {e}")

    def get_key_stats(self) -> Dict[str, Any]:
        """Get API key statistics."""
        total_keys = len(self._keys)
        active_keys = len([k for k in self._keys.values() if k.get("is_active", False)])

        # Count expired keys
        current_time = time.time()
        expired_keys = 0
        for key_data in self._keys.values():
            expires_at = key_data.get("expires_at")
            if expires_at and current_time > expires_at:
                expired_keys += 1

        return {
            "total_keys": total_keys,
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "revoked_keys": total_keys - active_keys - expired_keys,
        }
