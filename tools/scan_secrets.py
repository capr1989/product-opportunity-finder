"""Conservative local heuristic scan of tracked/candidate text, never print matched secrets."""
from pathlib import Path
import re
import subprocess
import sys


def main():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                            check=True, capture_output=True, text=True)
    patterns = [r"gh[pousr]_" + r"[A-Za-z0-9]{30,}", r"AIza" + r"[A-Za-z0-9_-]{30,}",
                r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----", r"1//" + r"[A-Za-z0-9_-]{40,}"]
    bad = []
    for name in result.stdout.splitlines():
        path = Path(name)
        if not path.is_file() or path.suffix in {".png", ".zip", ".xlsx"}:
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        if any(re.search(pattern, content) for pattern in patterns):
            bad.append(name)
        if path.name == ".env" or path.suffix in {".sqlite", ".db"}:
            bad.append(name)
    if bad:
        print("Potential secret/sensitive file found; review these paths only:", sorted(set(bad)))
        return 1
    print("Heuristic secret scan passed; manual review is still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
