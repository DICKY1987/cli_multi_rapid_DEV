from __future__ import annotations
import time
import json
import sys
from urllib.request import urlopen


def check(url: str, timeout_s: int = 30) -> int:
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=3) as resp:
                if resp.status == 200:
                    body = resp.read().decode("utf-8", errors="ignore")
                    try:
                        data = json.loads(body)
                        if data.get("ok"):
                            print("health: ok")
                            return 0
                    except Exception:
                        pass
        except Exception as e:
            last_err = e
        time.sleep(1.0)
    print(f"health: failed after {timeout_s}s: {last_err}")
    return 1


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5055/health"
    raise SystemExit(check(url))

