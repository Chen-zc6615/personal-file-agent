from pathlib import Path
from zipfile import ZipFile

import pytest

from assistant.file_management import (
    apply_file_organization,
    apply_file_renames,
    create_file_archive,
    find_duplicate_files,
    get_category,
    plan_file_archive,
    plan_file_organization,
    plan_file_renames,
)


def test_get_category():
    assert get_category(Path("report.pdf")) == "documents"
    assert get_category(Path("photo.PNG")) == "images"
    assert get_category(Path("data.xlsx")) == "spreadsheets"
    assert get_category(Path("unknown.xyz")) == "other"


def test_project_directory_is_blocked(tmp_path):
    project_directory = tmp_path / "project"
    project_directory.mkdir()

    (project_directory / ".git").mkdir()
    (project_directory / "pyproject.toml").touch()

    result = plan_file_organization(
        str(project_directory)
    )

    assert result["status"] == "blocked"
    assert result["suggested_moves"] == []
    assert ".git" in result["detected_project_markers"]
    assert "pyproject.toml" in result["detected_project_markers"]


def test_normal_directory_returns_plan(tmp_path):
    directory = tmp_path / "downloads"
    directory.mkdir()

    (directory / "report.pdf").touch()
    (directory / "photo.png").touch()
    (directory / "source.zip").touch()

    # Hidden files and subdirectories should be ignored.
    (directory / ".hidden.txt").touch()
    (directory / "existing-folder").mkdir()

    result = plan_file_organization(str(directory))

    moves = {
        item["source"]: item["destination"]
        for item in result["suggested_moves"]
    }

    assert result["status"] == "ready"
    assert result["total_files"] == 3

    assert moves == {
        "photo.png": "Images/photo.png",
        "report.pdf": "Documents/report.pdf",
        "source.zip": "Archives/source.zip",
    }


def test_apply_requires_confirmation(tmp_path):
    directory = tmp_path / "downloads"
    directory.mkdir()
    source = directory / "report.pdf"
    source.touch()

    result = apply_file_organization(str(directory))

    assert result["status"] == "confirmation_required"
    assert source.exists()
    assert not (directory / "Documents" / "report.pdf").exists()


def test_apply_moves_files_after_confirmation(tmp_path):
    directory = tmp_path / "downloads"
    directory.mkdir()
    (directory / "report.pdf").write_text("report")
    (directory / "photo.png").write_text("photo")
    (directory / ".hidden.txt").write_text("hidden")

    result = apply_file_organization(
        str(directory),
        confirmed=True,
    )

    assert result["status"] == "completed"
    assert (directory / "Documents" / "report.pdf").read_text() == "report"
    assert (directory / "Images" / "photo.png").read_text() == "photo"
    assert (directory / ".hidden.txt").read_text() == "hidden"
    assert not (directory / "report.pdf").exists()
    assert not (directory / "photo.png").exists()


def test_apply_never_overwrites_existing_file(tmp_path):
    directory = tmp_path / "downloads"
    documents = directory / "Documents"
    documents.mkdir(parents=True)

    source = directory / "report.pdf"
    destination = documents / "report.pdf"
    source.write_text("new report")
    destination.write_text("existing report")

    result = apply_file_organization(
        str(directory),
        confirmed=True,
    )

    assert result["status"] == "no_changes"
    assert source.read_text() == "new report"
    assert destination.read_text() == "existing report"
    assert result["skipped"][0]["reason"] == (
        "Destination already exists; no overwrite occurred."
    )


def test_apply_blocks_project_directory(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    (directory / "pyproject.toml").touch()
    (directory / "notes.txt").touch()

    result = apply_file_organization(
        str(directory),
        confirmed=True,
    )

    assert result["status"] == "blocked"
    assert (directory / "notes.txt").exists()
    assert not (directory / "Documents").exists()


def test_find_duplicate_files(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()

    (directory / "first.txt").write_bytes(b"same")
    (directory / "second.txt").write_bytes(b"same")

    # This file has the same size but different content.
    (directory / "different.txt").write_bytes(b"diff")

    result = find_duplicate_files(str(directory))

    assert result["status"] == "completed"
    assert result["duplicate_group_count"] == 1

    duplicate_group = result["duplicate_groups"][0]

    assert set(duplicate_group["files"]) == {
        "first.txt",
        "second.txt",
    }
    assert duplicate_group["size_bytes"] == 4
    assert duplicate_group["reclaimable_bytes"] == 4


def test_duplicate_scan_is_not_recursive_by_default(tmp_path):
    directory = tmp_path / "files"
    nested_directory = directory / "nested"
    nested_directory.mkdir(parents=True)

    (directory / "first.txt").write_text("duplicate")
    (nested_directory / "second.txt").write_text("duplicate")

    non_recursive_result = find_duplicate_files(
        str(directory)
    )
    recursive_result = find_duplicate_files(
        str(directory),
        recursive=True,
    )

    assert non_recursive_result["duplicate_group_count"] == 0
    assert recursive_result["duplicate_group_count"] == 1


def test_duplicate_scan_ignores_hidden_files(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()

    (directory / "visible.txt").write_text("duplicate")
    (directory / ".hidden.txt").write_text("duplicate")

    result = find_duplicate_files(
        str(directory),
        recursive=True,
    )

    assert result["total_files"] == 1
    assert result["duplicate_group_count"] == 0


def test_plan_file_renames_applies_rules_without_modifying_files(tmp_path):
    directory = tmp_path / "photos"
    directory.mkdir()

    source = directory / "My Photo.JPG"
    source.write_text("photo")
    hidden_file = directory / ".hidden.JPG"
    hidden_file.write_text("hidden")

    result = plan_file_renames(
        str(directory),
        prefix="holiday_",
        replace_spaces=True,
        lowercase=True,
    )

    assert result["status"] == "ready"
    assert result["total_files"] == 1
    assert result["suggested_renames"] == [
        {
            "source": "My Photo.JPG",
            "destination": "holiday_my_photo.jpg",
        }
    ]

    # Planning must not rename either visible or hidden files.
    assert source.exists()
    assert hidden_file.exists()
    assert not (directory / "holiday_my_photo.jpg").exists()


def test_plan_file_renames_detects_existing_destination(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()

    source = directory / "report.txt"
    destination = directory / "new_report.txt"
    source.write_text("source")
    destination.write_text("existing")

    result = plan_file_renames(
        str(directory),
        prefix="new_",
        replace_spaces=False,
    )

    skipped = {
        item["source"]: item["reason"]
        for item in result["skipped"]
    }

    assert skipped["report.txt"] == (
        "Destination already exists: new_report.txt"
    )
    assert source.read_text() == "source"
    assert destination.read_text() == "existing"


def test_plan_file_renames_blocks_project_directory(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    (directory / "pyproject.toml").touch()
    source = directory / "My Notes.txt"
    source.write_text("notes")

    result = plan_file_renames(
        str(directory),
        lowercase=True,
    )

    assert result["status"] == "blocked"
    assert result["suggested_renames"] == []
    assert source.exists()


def test_plan_file_renames_rejects_path_characters(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    (directory / "report.txt").touch()

    with pytest.raises(
        ValueError,
        match="prefix contains an invalid path character",
    ):
        plan_file_renames(
            str(directory),
            prefix="../unsafe/",
        )


def test_apply_file_renames_requires_confirmation(tmp_path):
    directory = tmp_path / "photos"
    directory.mkdir()
    source = directory / "My Photo.JPG"
    source.write_text("photo")

    result = apply_file_renames(
        str(directory),
        prefix="holiday_",
        lowercase=True,
    )

    assert result["status"] == "confirmation_required"
    assert source.exists()
    assert not (directory / "holiday_my_photo.jpg").exists()


def test_apply_file_renames_after_confirmation(tmp_path):
    directory = tmp_path / "photos"
    directory.mkdir()
    first = directory / "My Photo.JPG"
    second = directory / "Family Picture.PNG"
    hidden = directory / ".hidden.JPG"
    first.write_text("first")
    second.write_text("second")
    hidden.write_text("hidden")

    result = apply_file_renames(
        str(directory),
        confirmed=True,
        prefix="holiday_",
        replace_spaces=True,
        lowercase=True,
    )

    assert result["status"] == "completed"
    assert (directory / "holiday_my_photo.jpg").read_text() == "first"
    assert (
        directory / "holiday_family_picture.png"
    ).read_text() == "second"
    assert hidden.read_text() == "hidden"
    assert not first.exists()
    assert not second.exists()


def test_apply_file_renames_never_overwrites_destination(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    source = directory / "report.txt"
    destination = directory / "new_report.txt"
    source.write_text("report")
    destination.mkdir()

    result = apply_file_renames(
        str(directory),
        confirmed=True,
        prefix="new_",
        replace_spaces=False,
    )

    assert result["status"] == "no_changes"
    assert source.read_text() == "report"
    assert destination.is_dir()
    assert result["skipped"][0]["reason"] == (
        "Destination already exists: new_report.txt"
    )


def test_apply_file_renames_blocks_project_directory(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    (directory / "pyproject.toml").touch()
    source = directory / "My Notes.txt"
    source.write_text("notes")

    result = apply_file_renames(
        str(directory),
        confirmed=True,
        lowercase=True,
    )

    assert result["status"] == "blocked"
    assert source.exists()
    assert not (directory / "my_notes.txt").exists()


def test_plan_file_archive_is_read_only(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    first = directory / "report.txt"
    second = directory / "photo.png"
    hidden = directory / ".secret.txt"
    nested = directory / "nested"
    first.write_bytes(b"report")
    second.write_bytes(b"photo")
    hidden.write_bytes(b"secret")
    nested.mkdir()
    (nested / "nested.txt").write_bytes(b"nested")

    result = plan_file_archive(
        str(directory),
        archive_name="backup.zip",
    )

    assert result["status"] == "ready"
    assert result["destination"] == "Archives/backup.zip"
    assert result["files"] == ["photo.png", "report.txt"]
    assert result["total_bytes"] == 11

    # Planning must not create an archive or modify source files.
    assert first.read_bytes() == b"report"
    assert second.read_bytes() == b"photo"
    assert hidden.exists()
    assert not (directory / "Archives").exists()


def test_plan_file_archive_rejects_unsafe_name(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    (directory / "report.txt").touch()

    with pytest.raises(
        ValueError,
        match="archive_name contains an invalid path character",
    ):
        plan_file_archive(
            str(directory),
            archive_name="../backup.zip",
        )


def test_plan_file_archive_blocks_project_directory(tmp_path):
    directory = tmp_path / "project"
    directory.mkdir()
    (directory / "pyproject.toml").touch()
    source = directory / "notes.txt"
    source.write_text("notes")

    result = plan_file_archive(
        str(directory),
        archive_name="backup",
    )

    assert result["status"] == "blocked"
    assert result["files"] == []
    assert source.exists()
    assert not (directory / "Archives").exists()


def test_plan_file_archive_never_overwrites_existing_archive(tmp_path):
    directory = tmp_path / "files"
    archives = directory / "Archives"
    archives.mkdir(parents=True)
    destination = archives / "backup.zip"
    destination.write_bytes(b"existing archive")
    (directory / "report.txt").write_text("report")

    result = plan_file_archive(
        str(directory),
        archive_name="backup",
    )

    assert result["status"] == "blocked"
    assert destination.read_bytes() == b"existing archive"


def test_create_file_archive_requires_confirmation(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    source = directory / "report.txt"
    source.write_text("report")

    result = create_file_archive(
        str(directory),
        archive_name="backup",
    )

    assert result["status"] == "confirmation_required"
    assert source.read_text() == "report"
    assert not (directory / "Archives").exists()


def test_create_file_archive_preserves_sources(tmp_path):
    directory = tmp_path / "files"
    directory.mkdir()
    report = directory / "report.txt"
    photo = directory / "photo.png"
    hidden = directory / ".secret.txt"
    nested = directory / "nested"
    report.write_bytes(b"report")
    photo.write_bytes(b"photo")
    hidden.write_bytes(b"secret")
    nested.mkdir()
    (nested / "nested.txt").write_bytes(b"nested")

    result = create_file_archive(
        str(directory),
        archive_name="backup.zip",
        confirmed=True,
    )

    archive_path = directory / "Archives" / "backup.zip"

    assert result["status"] == "completed"
    assert result["source_files_deleted"] is False
    assert archive_path.exists()

    with ZipFile(archive_path) as archive:
        assert set(archive.namelist()) == {
            "photo.png",
            "report.txt",
        }
        assert archive.read("report.txt") == b"report"
        assert archive.read("photo.png") == b"photo"

    assert report.read_bytes() == b"report"
    assert photo.read_bytes() == b"photo"
    assert hidden.read_bytes() == b"secret"
    assert (nested / "nested.txt").read_bytes() == b"nested"


def test_create_file_archive_never_overwrites_existing_archive(tmp_path):
    directory = tmp_path / "files"
    archives = directory / "Archives"
    archives.mkdir(parents=True)
    destination = archives / "backup.zip"
    destination.write_bytes(b"existing archive")
    source = directory / "report.txt"
    source.write_text("report")

    result = create_file_archive(
        str(directory),
        archive_name="backup",
        confirmed=True,
    )

    assert result["status"] == "blocked"
    assert destination.read_bytes() == b"existing archive"
    assert source.read_text() == "report"
