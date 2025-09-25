from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import jwt  # type: ignore
except Exception:  # pragma: no cover
    jwt = None  # type: ignore


DEFAULT_PRIVATE_KEY = Path("config/jwt_private.pem")
DEFAULT_PUBLIC_KEY = Path("config/jwt_public.pem")


class JWTIssuer:
    """Branch-scoped JWT token issuer (RS256).

    Loads keys from `config/jwt_private.pem` and `config/jwt_public.pem` by default.
    You may override via env vars: `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY`.
    """

    def __init__(
        self,
        private_key_path: Optional[Path] = None,
        public_key_path: Optional[Path] = None,
        algorithm: str = "RS256",
    ) -> None:
        self.algorithm = algorithm
        self.private_key = self._load_key(private_key_path or DEFAULT_PRIVATE_KEY, env="JWT_PRIVATE_KEY")
        self.public_key = self._load_key(public_key_path or DEFAULT_PUBLIC_KEY, env="JWT_PUBLIC_KEY")

    def _load_key(self, path: Path, env: str) -> Optional[str]:
        if os.getenv(env):
            return os.getenv(env)
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                return None
        return None

    def is_enabled(self) -> bool:
        return bool(jwt and self.private_key and self.public_key)

    def issue_token(
        self,
        subject: str,
        branch: str,
        task_id: str,
        ttl_seconds: int = 3600,
        extra_claims: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Issue a branch-scoped JWT with limited TTL.

        Claims include: sub, iat, exp, scope, branch, task_id, ver.
        """
        if not self.is_enabled():  # pragma: no cover - depends on external keys
            raise RuntimeError("JWTIssuer not enabled (missing keys or jwt library)")

        now = int(time.time())
        payload: Dict[str, Any] = {
            "sub": subject,
            "iat": now,
            "exp": now + max(60, ttl_seconds),
            "scope": "branch",
            "branch": branch,
            "task_id": task_id,
            "ver": 1,
        }
        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.private_key, algorithm=self.algorithm)
        # PyJWT >= 2 returns string; older returns bytes
        if isinstance(token, bytes):  # pragma: no cover
            token = token.decode("utf-8")
        return token

