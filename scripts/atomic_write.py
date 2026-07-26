#!/usr/bin/env python3
"""Atomic Write Utility for Hermes Memory (L4).

write -> fsync -> rename pattern, same as Mem0/SQLite/LevelDB.
"""

import os, tempfile, glob, logging
logger = logging.getLogger("atomic_write")


def atomic_write(path, content):
    """Write content to path atomically."""
    d = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp", prefix=os.path.basename(path)+".")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return True
    except (IOError, OSError) as e:
        logger.error("write failed: " + str(e))
        if "tmp" in locals() and os.path.exists(tmp):
            try: os.unlink(tmp)
            except OSError: pass
        return False


def cleanup_orphaned_tmp(target_dir):
    """Remove orphaned .tmp files."""
    n = 0
    for f in glob.glob(os.path.join(target_dir, "*.tmp")):
        try: os.unlink(f); n += 1
        except OSError: pass
    return n


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "cleanup":
        d = sys.argv[2] if len(sys.argv) >= 3 else "/opt/data"
        print("cleaned " + str(cleanup_orphaned_tmp(d)) + " tmp files")
    elif len(sys.argv) >= 3 and sys.argv[1] == "write":
        print("write: " + str(atomic_write(sys.argv[2], sys.argv[3])))
    else:
        print("usage: python3 atomic_write.py {write|cleanup} [path]")
