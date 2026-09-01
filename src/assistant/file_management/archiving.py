"""Read-only ZIP archive planning."""

from pathlib import Path
from typing import cast
from zipfile import ZIP_DEFLATED, LargeZipFile, ZipFile

from assistant.file_management.safety import (
    get_protected_directory_reason,
)


def normalize_archive_name(archive_name: str) -> str:
    """Validate and normalize a ZIP archive filename."""

    normalized_name = archive_name.strip()

    if normalized_name.lower().endswith(".zip"):
        normalized_name = normalized_name[:-4]

    if not normalized_name or normalized_name in {".", ".."}:
        raise ValueError("archive_name must contain a valid filename")

    if any(character in normalized_name for character in ("/", "\\", "\0")):
        raise ValueError(
            "archive_name contains an invalid path character"
        )

    if len(f"{normalized_name}.zip".encode("utf-8")) > 255:
        raise ValueError("archive_name is too long")

    return normalized_name


def plan_file_archive(
    directory: str,
    archive_name: str,
    max_files: int = 200,
) -> dict[str, object]:
    """Create a safe, read-only plan for a ZIP archive.

    The plan includes only non-hidden regular files in the directory's
    top level. It never creates an archive, modifies files, or deletes
    original files.

    Args:
        directory: Directory containing files to archive.
        archive_name: Name of the ZIP archive, with or without .zip.
        max_files: Maximum number of files to include in the plan.
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

    if max_files < 1 or max_files > 1_000:
        raise ValueError(
            "max_files must be between 1 and 1000"
        )

    protected_reason = get_protected_directory_reason(directory_path)

    if protected_reason:
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": protected_reason,
            "files": [],
        }

    normalized_name = normalize_archive_name(archive_name)
    destination = directory_path / "Archives" / f"{normalized_name}.zip"

    if destination.exists():
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": (
                "Archive destination already exists; no overwrite is allowed."
            ),
            "destination": str(destination.relative_to(directory_path)),
            "files": [],
        }

    files = sorted(
        (
            path
            for path in directory_path.iterdir()
            if (
                path.is_file()
                and not path.is_symlink()
                and not path.name.startswith(".")
            )
        ),
        key=lambda path: path.name.lower(),
    )

    selected_files: list[str] = []
    total_bytes = 0
    errors: list[dict[str, str]] = []

    for file_path in files[:max_files]:
        try:
            file_size = file_path.stat().st_size
        except OSError as error:
            errors.append(
                {
                    "file": file_path.name,
                    "error": str(error),
                }
            )
            continue

        selected_files.append(file_path.name)
        total_bytes += file_size

    status = "ready" if selected_files else "no_files"

    return {
        "status": status,
        "directory": str(directory_path),
        "destination": str(destination.relative_to(directory_path)),
        "total_files": len(files),
        "planned_files": len(selected_files),
        "total_bytes": total_bytes,
        "truncated": len(files) > max_files,
        "files": selected_files,
        "errors": errors,
    }


def create_file_archive(
    directory: str,
    archive_name: str,
    confirmed: bool = False,
    max_files: int = 200,
) -> dict[str, object]:
    """Create a ZIP from a previously displayed archive plan.

    Call this tool only after the user explicitly confirms the plan in
    a later message. It recomputes the plan, never overwrites an existing
    archive, and always preserves the original files.

    Args:
        directory: Directory containing the source files.
        archive_name: Name of the ZIP archive, with or without .zip.
        confirmed: Whether the user explicitly confirmed the displayed plan.
        max_files: Maximum number of files to include in the archive.
    """

    if not confirmed:
        return {
            "status": "confirmation_required",
            "directory": directory,
            "reason": (
                "The user must explicitly confirm the displayed archive "
                "plan before a ZIP file can be created."
            ),
            "archived_files": [],
        }

    directory_path = Path(directory).expanduser().resolve()
    plan = plan_file_archive(
        str(directory_path),
        archive_name=archive_name,
        max_files=max_files,
    )

    if plan["status"] == "blocked":
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": plan.get("reason", "The plan cannot be applied."),
            "archived_files": [],
        }

    if plan["status"] == "no_files":
        return {
            "status": "no_files",
            "directory": str(directory_path),
            "reason": "No eligible files were found to archive.",
            "archived_files": [],
        }

    destination_relative = cast(str, plan["destination"])
    destination = directory_path / destination_relative
    planned_files = cast(list[str], plan["files"])
    source_files: list[Path] = []

    for file_name in planned_files:
        source = directory_path / file_name

        if not source.is_file() or source.is_symlink():
            return {
                "status": "blocked",
                "directory": str(directory_path),
                "reason": (
                    "A planned source file changed before archiving: "
                    f"{file_name}"
                ),
                "archived_files": [],
            }

        source_files.append(source)

    archive_created = False

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("xb") as archive_stream:
            archive_created = True

            with ZipFile(
                archive_stream,
                mode="w",
                compression=ZIP_DEFLATED,
            ) as archive:
                for source in source_files:
                    archive.write(
                        source,
                        arcname=source.name,
                    )
    except FileExistsError:
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": (
                "Archive destination already exists; no overwrite occurred."
            ),
            "archive": destination_relative,
            "archived_files": [],
        }
    except (OSError, LargeZipFile) as error:
        if archive_created:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass

        return {
            "status": "failed",
            "directory": str(directory_path),
            "reason": f"Archive creation failed: {error}",
            "archive": destination_relative,
            "archived_files": [],
        }

    return {
        "status": "completed",
        "directory": str(directory_path),
        "archive": destination_relative,
        "archived_files": planned_files,
        "archived_file_count": len(planned_files),
        "source_files_deleted": False,
        "truncated": plan["truncated"],
    }
