import hashlib
from pathlib import Path


def compute_report_id(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]
