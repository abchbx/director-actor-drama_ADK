"""Lock file management for CLI/API mutual exclusion (D-07/STATE-03).

Ensures only one instance (CLI or API) can run at a time.
Lock file contains the PID of the running process.
"""

import os
import logging

logger = logging.getLogger(__name__)

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".api.lock")


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is alive (Unix).

    Uses os.kill(pid, 0) which doesn't send a signal, just checks existence.
    """
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but we can't signal it — treat as alive
        return True


def acquire_lock():
    """Create lock file with current PID. Raise if another instance is running.

    Performs stale lock detection: if lock file exists but the owning PID
    is no longer alive, the stale lock is removed and acquisition proceeds.
    """
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE) as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                # Corrupted lock file — remove it
                logger.warning("Corrupted lock file %s — removing", LOCK_FILE)
                os.remove(LOCK_FILE)
            else:
                if _is_pid_alive(pid):
                    raise RuntimeError(
                        f"Another instance is already running (PID: {pid}). "
                        f"Delete {LOCK_FILE} if this is incorrect."
                    )
                # Stale lock — owning process is dead
                logger.info("Stale lock file found (PID %d no longer alive) — removing", pid)
                os.remove(LOCK_FILE)

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))
    logger.info("Lock file acquired: %s (PID: %d)", LOCK_FILE, os.getpid())


def release_lock():
    """Remove lock file on shutdown."""
    try:
        os.remove(LOCK_FILE)
        logger.info("Lock file released: %s", LOCK_FILE)
    except FileNotFoundError:
        pass
