Branch-Scoped JWT Tokens

Purpose
- Limit tool permissions to a specific task/branch and time window; improve auditability and safety.

Artifacts
- `config/jwt_private.pem` (placeholder; generate locally)
- `config/jwt_public.pem` (placeholder; generate locally)
- `services/security_gateway/jwt_issuer.py` (issuer utility)

Key generation (local)
```
openssl genrsa -out config/jwt_private.pem 2048
openssl rsa -in config/jwt_private.pem -pubout -out config/jwt_public.pem
```

Usage (Python)
```
from services.security_gateway.jwt_issuer import JWTIssuer
issuer = JWTIssuer()
token = issuer.issue_token(subject="user:alice", branch="feature/x", task_id="T-123", ttl_seconds=1800)
```

Notes
- Do not commit real keys; placeholders are provided for structure only.
- Keys can also be supplied via env vars `JWT_PRIVATE_KEY` and `JWT_PUBLIC_KEY`.

