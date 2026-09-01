"""Read-only filename normalization planning."""

import re
from datetime import datetime
from pathlib import Path
from typing import cast

from assistant.file_management.safety import (
    get_protected_directory_reason,
)


def validate_filename_component(
    value: str,
    parameter_name: str,
) -> None:
    """Validate a user-provided filename component."""

    invalid_characters = ("/", "\\", "\0")

    if any(character in value for character in invalid_characters):
        raise ValueError(
            f"{parameter_name} contains an invalid path character"
        )


def plan_file_renames(
    directory: str,
    prefix: str = "",
    name_suffix: str = "",
    replace_spaces: bool = True,
    lowercase: bool = False,
    include_modified_date: bool = False,
    max_files: int = 200,
) -> dict[str, object]:
    """Create a safe, read-only filename normalization plan.

    This tool never renames or modifies files. It only examines
    non-hidden regular files in the directory's top level.

    Args:
        directory: Directory containing files to examine.
        prefix: Text added before each filename.
        name_suffix: Text added after the filename stem.
        replace_spaces: Replace groups of spaces with underscores.
        lowercase: Convert filename stems and extensions to lowercase.
        include_modified_date: Add YYYY-MM-DD from file modification time.
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

    if max_files < 1 or max_files > 1_000:
        raise ValueError(
            "max_files must be between 1 and 1000"
        )

    protected_reason = get_protected_directory_reason(
        directory_path
    )

    if protected_reason:
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": protected_reason,
            "suggested_renames": [],
            "skipped": [],
        }

    validate_filename_component(prefix, "prefix")
    validate_filename_component(
        name_suffix,
        "name_suffix",
    )

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

    existing_names = {
        path.name.casefold(): path.name
        for path in directory_path.iterdir()
    }
    planned_names: set[str] = set()

    suggested_renames: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for file_path in files[:max_files]:
        stem = file_path.stem.strip()
        extension = file_path.suffix

        if replace_spaces:
            stem = re.sub(r"\s+", "_", stem)

        if lowercase:
            stem = stem.lower()
            extension = extension.lower()

        date_prefix = ""

        if include_modified_date:
            try:
                modified_time = datetime.fromtimestamp(
                    file_path.stat().st_mtime
                )
            except OSError as error:
                skipped.append(
                    {
                        "source": file_path.name,
                        "reason": (
                            f"Could not read modification time: {error}"
                        ),
                    }
                )
                continue

            date_prefix = modified_time.strftime(
                "%Y-%m-%d_"
            )

        new_name = (
            f"{date_prefix}"
            f"{prefix}"
            f"{stem}"
            f"{name_suffix}"
            f"{extension}"
        )

        if new_name == file_path.name:
            skipped.append(
                {
                    "source": file_path.name,
                    "reason": "The filename would not change.",
                }
            )
            continue

        if len(new_name.encode("utf-8")) > 255:
            skipped.append(
                {
                    "source": file_path.name,
                    "reason": "The suggested filename is too long.",
                }
            )
            continue

        normalized_name = new_name.casefold()
        existing_name = existing_names.get(normalized_name)

        if (
            existing_name is not None
            and existing_name != file_path.name
        ):
            skipped.append(
                {
                    "source": file_path.name,
                    "reason": (
                        f"Destination already exists: {existing_name}"
                    ),
                }
            )
            continue

        if normalized_name in planned_names:
            skipped.append(
                {
                    "source": file_path.name,
                    "reason": (
                        "Another file would receive the same name: "
                        f"{new_name}"
                    ),
                }
            )
            continue

        planned_names.add(normalized_name)

        suggested_renames.append(
            {
                "source": file_path.name,
                "destination": new_name,
            }
        )

    status = (
        "ready"
        if suggested_renames
        else "no_changes"
    )

    return {
        "status": status,
        "directory": str(directory_path),
        "total_files": len(files),
        "analyzed_files": min(len(files), max_files),
        "truncated": len(files) > max_files,
        "suggested_renames": suggested_renames,
        "skipped": skipped,
    }


def apply_file_renames(
    directory: str,
    confirmed: bool = False,
    prefix: str = "",
    name_suffix: str = "",
    replace_spaces: bool = True,
    lowercase: bool = False,
    include_modified_date: bool = False,
    max_files: int = 200,
) -> dict[str, object]:
    """Apply a previously displayed filename normalization plan.

    Call this tool only after the user explicitly confirms the plan in
    a later message. The plan is recomputed immediately before execution,
    existing destinations are never overwritten, and protected directories
    remain blocked.

    Args:
        directory: Directory whose rename plan is applied.
        confirmed: Whether the user explicitly confirmed the displayed plan.
        prefix: Text added before each filename.
        name_suffix: Text added after the filename stem.
        replace_spaces: Replace groups of spaces with underscores.
        lowercase: Convert filename stems and extensions to lowercase.
        include_modified_date: Add YYYY-MM-DD from file modification time.
        max_files: Maximum number of files to rename.
    """

    if not confirmed:
        return {
            "status": "confirmation_required",
            "directory": directory,
            "reason": (
                "The user must explicitly confirm the displayed rename "
                "plan before files can be renamed."
            ),
            "renamed": [],
            "skipped": [],
        }

    directory_path = Path(directory).expanduser().resolve()
    plan = plan_file_renames(
        str(directory_path),
        prefix=prefix,
        name_suffix=name_suffix,
        replace_spaces=replace_spaces,
        lowercase=lowercase,
        include_modified_date=include_modified_date,
        max_files=max_files,
    )

    if plan["status"] == "blocked":
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": plan.get("reason", "The plan cannot be applied."),
            "renamed": [],
            "skipped": plan["skipped"],
        }

    suggested_renames = cast(
        list[dict[str, str]],
        plan["suggested_renames"],
    )
    skipped = [
        dict(item)
        for item in cast(
            list[dict[str, str]],
            plan["skipped"],
        )
    ]
    renamed: list[dict[str, str]] = []

    for rename in suggested_renames:
        source = directory_path / rename["source"]
        destination = directory_path / rename["destination"]

        if not source.is_file() or source.is_symlink():
            skipped.append(
                {
                    "source": rename["source"],
                    "destination": rename["destination"],
                    "reason": "Source is missing or is not a regular file.",
                }
            )
            continue

        destination_is_source = False

        if destination.exists():
            try:
                destination_is_source = source.samefile(destination)
            except OSError:
                destination_is_source = False

        if destination.exists() and not destination_is_source:
            skipped.append(
                {
                    "source": rename["source"],
                    "destination": rename["destination"],
                    "reason": "Destination already exists; no overwrite occurred.",
                }
            )
            continue

        try:
            source.rename(destination)
        except OSError as error:
            skipped.append(
                {
                    "source": rename["source"],
                    "destination": rename["destination"],
                    "reason": f"Rename failed: {error}",
                }
            )
            continue

        renamed.append(
            {
                "source": rename["source"],
                "destination": rename["destination"],
            }
        )

    if renamed and skipped:
        status = "partial"
    elif renamed:
        status = "completed"
    else:
        status = "no_changes"

    return {
        "status": status,
        "directory": str(directory_path),
        "renamed": renamed,
        "skipped": skipped,
        "truncated": plan["truncated"],
    }
