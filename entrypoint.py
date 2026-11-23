# SPDX-License-Identifier: AGPL-3.0-or-later
"""Container entrypoint: make the data folder writable, then drop root.

Docker creates a bind-mounted folder (e.g. ./data) owned by root on the host,
so a non-root app can't write its database there. When started as root, this
script gives the data folder to PUID:PGID (default 10001:10001), then runs the
server as that user. When started as another user (docker run --user ...), it
only checks the folder is writable and says how to fix it if not.
"""
import os
import sys
from pathlib import Path

DATA = Path(os.environ.get("EDGEMARK_DB", "/data/edgemark.db")).parent


def fail(msg: str) -> None:
    print(f"edgemark: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def main() -> None:
    cmd = sys.argv[1:] or ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
    if os.getuid() == 0:
        uid = int(os.environ.get("PUID", "10001"))
        gid = int(os.environ.get("PGID", str(uid)))
        DATA.mkdir(parents=True, exist_ok=True)
        for root, dirs, files in os.walk(DATA):
            for p in [root, *(os.path.join(root, f) for f in files)]:
                st = os.lstat(p)
                if (st.st_uid, st.st_gid) != (uid, gid):
                    os.lchown(p, uid, gid)
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        os.environ["HOME"] = str(DATA)
    elif not os.access(DATA, os.W_OK | os.X_OK):
        fail(f"{DATA} is not writable by uid {os.getuid()}. Either run without --user "
             f"(the container fixes ownership itself), or on the host run: "
             f"sudo chown -R {os.getuid()}:{os.getgid()} <your data folder>")
    os.execvp(cmd[0], cmd)


if __name__ == "__main__":
    main()
