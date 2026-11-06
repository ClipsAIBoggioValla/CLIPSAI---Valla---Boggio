import os

_PRIORITY = [
    "/usr/local/sbin",
    "/usr/local/bin",
    "/usr/sbin",
    "/usr/bin",
    "/sbin",
    "/bin",
]


def _fix_path() -> None:
    current = os.environ.get("PATH", "")
    partes = [p for p in current.split(os.pathsep) if p and p not in _PRIORITY]
    os.environ["PATH"] = os.pathsep.join(_PRIORITY + partes)


_fix_path()
