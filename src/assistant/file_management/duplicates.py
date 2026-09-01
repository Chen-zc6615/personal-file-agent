"""Read-only duplicate-file detection."""

import hashlib
from collections import defaultdict
from pathlib import Path


def calculate_sha256(
    file_path: Path,
    chunk_size: int = 1024 * 1024,
) -> str:
    """Calculate a file's SHA-256 hash without loading it all into memory."""

    hasher = hashlib.sha256()

    with file_path.open("rb") as file:
        while chunk := file.read(chunk_size):
            hasher.update(chunk)

    return hasher.hexdigest()


def find_duplicate_files(
    directory: str,
    recursive: bool = False,
    max_files: int = 1_000,
) -> dict[str, object]:
    """Find files with identical content.

    This is a read-only tool. It never deletes, moves, renames,
    or modifies files.

    Args:
        directory: Directory to scan.
        recursive: Whether to include subdirectories.
        max_files: Maximum number of files to examine.
    """

    directory_path = Path(directory).expanduser().resolve()

    if not directory_path.exists():
        raise FileNotFoundError(
            f"Directory does not exist: {directory_path}"
        )

    if not directory_path.is_dir():
        raise NotADirectoryError(
            f"Path is not a directory: {directory_path}"
        )

    if max_files < 1 or max_files > 10_000:
        raise ValueError(
            "max_files must be between 1 and 10000"
        )

    paths = (
        directory_path.rglob("*")
        if recursive
        else directory_path.iterdir()
    )

    files = sorted(
        (
            path
            for path in paths
            if (
                path.is_file()
                and not path.is_symlink()
                and not any(
                    part.startswith(".")
                    for part in path.relative_to(
                        directory_path
                    ).parts
                )
            )
        ),
        key=lambda path: str(path).lower(),
    )

    scanned_files = files[:max_files]
    files_by_size: dict[int, list[Path]] = defaultdict(list)
    errors: list[dict[str, str]] = []

    for file_path in scanned_files:
        try:
            files_by_size[file_path.stat().st_size].append(
                file_path
            )
        except OSError as error:
            errors.append(
                {
                    "file": str(file_path),
                    "error": str(error),
                }
            )

    duplicate_groups: list[dict[str, object]] = []
    total_reclaimable_bytes = 0

    for file_size, same_size_files in files_by_size.items():
        if len(same_size_files) < 2:
            continue

        files_by_hash: dict[str, list[Path]] = defaultdict(list)

        for file_path in same_size_files:
            try:
                file_hash = calculate_sha256(file_path)
                files_by_hash[file_hash].append(file_path)
            except OSError as error:
                errors.append(
                    {
                        "file": str(file_path),
                        "error": str(error),
                    }
                )

        for file_hash, identical_files in files_by_hash.items():
            if len(identical_files) < 2:
                continue

            relative_files = [
                str(path.relative_to(directory_path))
                for path in identical_files
            ]

            reclaimable_bytes = (
                file_size * (len(relative_files) - 1)
            )
            total_reclaimable_bytes += reclaimable_bytes

            duplicate_groups.append(
                {
                    "sha256": file_hash,
                    "size_bytes": file_size,
                    "files": relative_files,
                    "reclaimable_bytes": reclaimable_bytes,
                }
            )

    return {
        "status": "completed",
        "directory": str(directory_path),
        "recursive": recursive,
        "total_files": len(files),
        "scanned_files": len(scanned_files),
        "truncated": len(files) > max_files,
        "duplicate_groups": duplicate_groups,
        "duplicate_group_count": len(duplicate_groups),
        "reclaimable_bytes": total_reclaimable_bytes,
        "errors": errors,
    }
