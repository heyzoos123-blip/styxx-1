"""Temporary directories and the disk guard, shared by the v5f exam's artifacts.

Every artifact that makes a temporary directory makes it here, so none outlives its run:

workdir(prefix)      tempfile.mkdtemp(prefix=prefix), removed when the creating process exits (atexit) or
                     earlier through release() / cleanup(). The atexit handler removes only directories
                     made by the exiting process, so a forked child's exit leaves its parent's alone. A
                     process that ends with os._exit (atexit does not run) calls cleanup() first; main()s
                     wrap their body in try/finally for the same reason.
scratch(prefix)      workdir() as a context manager: removed when the block exits, normally or by an error.
child_run(cmd, ...)  subprocess.run(cmd, ...) with TMPDIR set, for that child, to a fresh directory made
                     here; whatever the child and its own children leave in their temp dir is removed when
                     subprocess.run returns or raises (an os._exit, a crash, a kill by the timeout).
disk_guard(min_gb)   raises DiskLow when the file system holding the temp dir has under min_gb GB free
                     (default 2, or $V5F_MIN_FREE_GB). The long drivers call it before each unit of work,
                     write what they have (their journal stays as it is) and stop with status 75.

The paths a child sees change only in the directory they sit in (its TMPDIR is a fresh directory instead
of /tmp); every case builds its fixtures and repos below tempfile's directory and judges nothing by it.
"""
import atexit, contextlib, os, shutil, subprocess, sys, tempfile

DISK_LOW_STATUS = 75                      # EX_TEMPFAIL: stopped cleanly; rerun with the same journal
_OWNED = []                               # [(pid, path)], in creation order


def workdir(prefix):
    d = tempfile.mkdtemp(prefix=prefix)
    _OWNED.append((os.getpid(), d))
    return d


def release(d):
    """Remove d now (a directory made by workdir() or not) and forget it."""
    shutil.rmtree(d, ignore_errors=True)
    _OWNED[:] = [x for x in _OWNED if x[1] != d]


def cleanup():
    pid = os.getpid()
    for p, d in list(_OWNED):
        if p == pid:
            shutil.rmtree(d, ignore_errors=True)
    _OWNED[:] = [x for x in _OWNED if x[0] != pid]


atexit.register(cleanup)


@contextlib.contextmanager
def scratch(prefix):
    d = workdir(prefix)
    try:
        yield d
    finally:
        release(d)


def child_env(d, env=None):
    e = dict(os.environ if env is None else env)
    e["TMPDIR"] = d
    return e


def child_run(cmd, env=None, **kw):
    d = tempfile.mkdtemp(prefix="v5f_child_")
    try:
        return subprocess.run(cmd, env=child_env(d, env), **kw)
    finally:
        shutil.rmtree(d, ignore_errors=True)


class DiskLow(RuntimeError):
    pass


def free_gb(path=None):
    return shutil.disk_usage(path or tempfile.gettempdir()).free / 2 ** 30


def disk_guard(min_gb=None, what=""):
    min_gb = float(os.environ.get("V5F_MIN_FREE_GB", "2")) if min_gb is None else min_gb
    f = free_gb()
    if f < min_gb:
        raise DiskLow(f"{f:.2f} GB free under {tempfile.gettempdir()} (< {min_gb:g} GB)"
                      + (f" before {what}" if what else ""))
    return f


_DISK_ERRORS = ("No space left on device", "No usable temporary directory", "Errno 28", "ENOSPC")


def check_child(text, what=""):
    """After a child ran: raise DiskLow if the disk is now low or the child's output names a full disk, so a
    driver never journals a verdict a full disk made."""
    if any(m in (text or "") for m in _DISK_ERRORS):
        raise DiskLow(f"a child reported a full disk{f' ({what})' if what else ''}: {free_gb():.2f} GB free now")
    disk_guard(what=what)


def stop_disk_low(e, keep=""):
    """The drivers' handler: say why, say what was kept, and the status to exit with."""
    print(f"DISK_LOW: stopped cleanly: {e}" + (f"; kept {keep}" if keep else ""), file=sys.stderr, flush=True)
    return DISK_LOW_STATUS
