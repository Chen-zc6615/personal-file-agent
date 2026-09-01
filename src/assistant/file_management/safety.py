"""Safety checks shared by file-management operations."""

from pathlib import Path


PROJECT_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "requirements.txt",
}


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
