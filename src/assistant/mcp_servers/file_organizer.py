from pathlib import Path
from typing import cast

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("File Organizer")


FILE_CATEGORIES = {
    "documents": {
        ".pdf", ".doc", ".docx", ".txt", ".md", ".rtf",
    },
    "spreadsheets": {
        ".csv", ".xls", ".xlsx",
    },
    "images": {
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    },
    "videos": {
        ".mp4", ".mov", ".avi", ".mkv",
    },
    "audio": {
        ".mp3", ".wav", ".flac", ".m4a",
    },
    "archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz",
    },
    "code": {
        ".py", ".js", ".ts", ".java", ".html", ".css",
        ".json", ".toml", ".yaml", ".yml",
    },
}


CATEGORY_FOLDERS = {
    "documents": "Documents",
    "spreadsheets": "Spreadsheets",
    "images": "Images",
    "videos": "Videos",
    "audio": "Audio",
    "archives": "Archives",
    "code": "Code",
    "other": "Other",
}


PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "requirements.txt",
}


def get_category(file_path: Path) -> str:
    """Determine a file category from its extension."""

    extension = file_path.suffix.lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return "other"


def find_project_markers(directory: Path) -> list[str]:
    """Find files or directories that identify a software project."""

    return sorted(
        marker
        for marker in PROJECT_MARKERS
        if (directory / marker).exists()
    )


def get_protected_directory_reason(directory: Path) -> str | None:
    """Return a reason when file changes must be blocked."""

    if directory == Path(directory.anchor):
        return "The filesystem root cannot be reorganized."

    if directory == Path.home().resolve():
        return "The user home directory cannot be reorganized."

    project_markers = find_project_markers(directory)

    if project_markers:
        markers = ", ".join(project_markers)
        return (
            "This directory looks like a software project. "
            f"Detected project markers: {markers}."
        )

    return None


@mcp.tool()
def plan_file_organization(
    directory: str,
    max_files: int = 200,
) -> dict[str, object]:
    """Create a safe, read-only file organization plan.

    The tool never moves, renames, overwrites, or deletes files.
    If the directory looks like a software project, it returns a
    blocked result and does not suggest moving project files.
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

    project_markers = find_project_markers(directory_path)

    if project_markers:
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": (
                "This directory looks like a software project. "
                "Moving its top-level files may break the project."
            ),
            "detected_project_markers": project_markers,
            "suggested_moves": [],
        }

    files = sorted(
        (
            path
            for path in directory_path.iterdir()
            if path.is_file() and not path.name.startswith(".")
        ),
        key=lambda path: path.name.lower(),
    )

    suggested_moves: list[dict[str, str]] = []

    for file_path in files[:max_files]:
        category = get_category(file_path)
        target_folder = CATEGORY_FOLDERS[category]

        suggested_moves.append(
            {
                "source": file_path.name,
                "destination": (
                    f"{target_folder}/{file_path.name}"
                ),
                "category": category,
            }
        )

    return {
        "status": "ready",
        "directory": str(directory_path),
        "total_files": len(files),
        "analyzed_files": min(len(files), max_files),
        "truncated": len(files) > max_files,
        "suggested_moves": suggested_moves,
    }


@mcp.tool()
def apply_file_organization(
    directory: str,
    confirmed: bool = False,
    max_files: int = 200,
) -> dict[str, object]:
    """Apply a previously displayed file organization plan.

    Call this tool only after the user explicitly confirms the plan in
    a later message. It moves only non-hidden files in the directory's
    top level, never overwrites existing files, and refuses to modify
    the filesystem root, the user home directory, or software projects.

    Args:
        directory: Directory whose previously displayed plan is applied.
        confirmed: Whether the user explicitly confirmed that plan.
        max_files: Maximum number of top-level files to move.
    """

    if not confirmed:
        return {
            "status": "confirmation_required",
            "directory": directory,
            "reason": (
                "The user must explicitly confirm the displayed plan "
                "before files can be moved."
            ),
            "moved": [],
            "skipped": [],
        }

    directory_path = Path(directory).expanduser().resolve()

    if not directory_path.exists():
        raise FileNotFoundError(
            f"Directory does not exist: {directory_path}"
        )

    if not directory_path.is_dir():
        raise NotADirectoryError(
            f"Path is not a directory: {directory_path}"
        )

    protected_reason = get_protected_directory_reason(directory_path)

    if protected_reason:
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": protected_reason,
            "moved": [],
            "skipped": [],
        }

    plan = plan_file_organization(
        str(directory_path),
        max_files=max_files,
    )

    if plan["status"] != "ready":
        return {
            "status": "blocked",
            "directory": str(directory_path),
            "reason": plan.get("reason", "The plan cannot be applied."),
            "moved": [],
            "skipped": [],
        }

    suggested_moves = cast(
        list[dict[str, str]],
        plan["suggested_moves"],
    )
    moved: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []

    for move in suggested_moves:
        source = directory_path / move["source"]
        destination = directory_path / move["destination"]

        if not source.is_file() or source.is_symlink():
            skipped.append(
                {
                    "source": move["source"],
                    "destination": move["destination"],
                    "reason": "Source is missing or is not a regular file.",
                }
            )
            continue

        if destination.exists():
            skipped.append(
                {
                    "source": move["source"],
                    "destination": move["destination"],
                    "reason": "Destination already exists; no overwrite occurred.",
                }
            )
            continue

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        except OSError as error:
            skipped.append(
                {
                    "source": move["source"],
                    "destination": move["destination"],
                    "reason": f"Move failed: {error}",
                }
            )
            continue

        moved.append(
            {
                "source": move["source"],
                "destination": move["destination"],
            }
        )

    if moved and skipped:
        status = "partial"
    elif moved:
        status = "completed"
    else:
        status = "no_changes"

    return {
        "status": status,
        "directory": str(directory_path),
        "moved": moved,
        "skipped": skipped,
        "truncated": plan["truncated"],
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
