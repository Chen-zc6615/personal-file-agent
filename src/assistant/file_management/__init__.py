"""File-management business logic used by the assistant."""

from assistant.file_management.archiving import (
    create_file_archive,
    normalize_archive_name,
    plan_file_archive,
)
from assistant.file_management.duplicates import (
    calculate_sha256,
    find_duplicate_files,
)
from assistant.file_management.organization import (
    apply_file_organization,
    get_category,
    plan_file_organization,
)
from assistant.file_management.renaming import (
    apply_file_renames,
    plan_file_renames,
    validate_filename_component,
)

__all__ = [
    "apply_file_organization",
    "apply_file_renames",
    "calculate_sha256",
    "create_file_archive",
    "find_duplicate_files",
    "get_category",
    "normalize_archive_name",
    "plan_file_archive",
    "plan_file_organization",
    "plan_file_renames",
    "validate_filename_component",
]
