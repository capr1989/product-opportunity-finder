"""Generate a hash lock from a reviewed, installed Windows Python 3.12 environment.

Run only after deliberately installing reviewed direct pins. Does not install or upgrade anything.
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import urllib.request


def release(line):
    name, version = line.split("==", 1)
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        metadata = json.load(response)
    hashes = sorted({f["digests"]["sha256"] for f in metadata["urls"] if not f.get("yanked")})
    if not hashes:
        raise ValueError(f"No trusted release hashes for {name}")
    return line + " \\\n" + " \\\n".join("    --hash=sha256:" + value for value in hashes)


def main():
    resolved = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"],
                              check=True, text=True, capture_output=True).stdout.splitlines()
    if any("==" not in line for line in resolved):
        raise ValueError("Only exact PyPI release pins may enter the lock")
    with ThreadPoolExecutor(max_workers=6) as executor:
        entries = list(executor.map(release, sorted(resolved, key=str.lower)))
    header = "# Resolved on Windows / Python 3.12; reviewed installed graph, all release hashes.\n"
    Path("requirements.lock").write_text(header + "--index-url https://pypi.org/simple\n\n" + "\n".join(entries) + "\n")
    print(f"Locked {len(entries)} packages with PyPI release SHA256 hashes")


if __name__ == "__main__":
    main()
