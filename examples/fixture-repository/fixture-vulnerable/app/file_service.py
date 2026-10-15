from pathlib import Path

def _normalize_attachment_path(base_dir: str, user_path: str) -> Path:
    return Path(base_dir) / user_path


def read_attachment(user_path: str, base_dir: str) -> str:
    candidate = _normalize_attachment_path(base_dir, user_path)
    return candidate.read_text(encoding="utf-8")


def download_attachment(user_path: str, base_dir: str) -> str:
    return read_attachment(user_path, base_dir)


def attachment_endpoint(request: dict, base_dir: str) -> str:
    return download_attachment(request["path"], base_dir)
