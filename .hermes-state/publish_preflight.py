import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path.cwd()
BRANCH = "codex/publish-snapshot-mt5-fix-20260910"

def git(*args, data=None, env=None):
    return subprocess.check_output(["git", *args], input=data, env=env).decode().strip()

source = git("rev-parse", "HEAD")
base = git("rev-parse", "@{u}")
assert source == "0cb7af577dc1f430b6ba67ffae406f984ea7d127", "Source branch changed; review again"
assert not git("ls-remote", "--heads", "origin", BRANCH), "Publication branch already exists remotely"
assert subprocess.run(["git", "show-ref", "--verify", "--quiet", "refs/heads/" + BRANCH]).returncode != 0
raw = subprocess.check_output(["git", "ls-tree", "-rlz", source])
excluded = []
for item in raw.split(b"\0"):
    if not item:
        continue
    fields, path = item.split(b"\t", 1)
    mode, kind, sha, size = fields.decode().split()
    path = path.decode()
    reason = None
    if path.startswith(".hermes-state/"):
        reason = "local operational state or audit scratch data"
    elif path == "runtime/mechanical_bot/latest_snapshot.json":
        reason = "runtime signal is not distributable source code"
    elif path.endswith(".pid"):
        reason = "machine-specific process identifier"
    elif path.startswith("reports/") and int(size) > 50 * 1024 * 1024:
        reason = "generated report above 50 MiB"
    if reason:
        excluded.append({"path": path, "bytes": int(size), "reason": reason})

manifest = {"source_commit": source, "upstream_base": base,
            "publication_branch": BRANCH, "source_commits_combined": int(git("rev-list", "--count", base + ".." + source)),
            "policy": "SOURCE_PUBLICATION_ONLY_NO_TRADING_PROMOTION",
            "local_history_preserved": True, "exclusions": excluded,
            "validation": "40 focused tests passed; native DEMO open/close transport reconciled; complete 137-commit suite not run",
            "activation": "Main local desktop service still needs restart; automatic policy rejected it",
            "audit_status": "PENDING_INDEPENDENT_REVIEW"}
with tempfile.TemporaryDirectory(prefix="publish-index-", dir=ROOT / ".hermes-state") as folder:
    env = {**os.environ, "GIT_INDEX_FILE": str(Path(folder) / "index")}
    git("read-tree", source, env=env)
    git("update-index", "--force-remove", "--stdin", data=("\n".join(x["path"] for x in excluded) + "\n").encode(), env=env)
    blob = git("hash-object", "-w", "--stdin", data=(json.dumps(manifest, indent=2) + "\n").encode())
    git("update-index", "--add", "--cacheinfo", "100644", blob, "docs/delivery/publication_20260910.json", env=env)
    tree = git("write-tree", env=env)
    message = ("publish: consolidate local ICT updates with verified MT5 transport fix\n\n"
               f"Source {source}; upstream base {base}. Preserve source branch history.\n"
               "Exclude operational state, live signal, PID files and generated reports above 50 MiB.\n"
               "Code publication only; no trading promotion. Independent review pending before push.\n")
    commit = git("commit-tree", tree, "-p", base, data=message.encode())
    git("update-ref", "refs/heads/" + BRANCH, commit, "0" * 40)
    result = {"branch": BRANCH, "commit": commit, "tree": tree,
              "source": source, "base": base, "exclusions": excluded}
    (ROOT / ".hermes-state/publish_candidate.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "exclusions"}, indent=2))
    print("excluded", len(excluded), "files,", round(sum(x["bytes"] for x in excluded) / 1024**2, 1), "MiB")
