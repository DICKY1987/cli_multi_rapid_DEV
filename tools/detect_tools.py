import json
import os
import shutil

TOOLS = json.loads(os.environ.get("TOOLS_JSON", "[]"))


def resolve(name):
    p = shutil.which(name)
    if p:
        return os.path.abspath(p)
    guesses = [
        os.path.expanduser(f"~/.local/bin/{name}"),
        "/opt/homebrew/bin/" + name,
        "/usr/local/bin/" + name,
    ]
    for g in guesses:
        if g and os.path.exists(g):
            return os.path.abspath(g)
    return ""


paths = {t: (resolve(t) or "") for t in TOOLS}
print(json.dumps({"paths": paths}, indent=2))
