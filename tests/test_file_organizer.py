from pathlib import Path

from assistant.mcp_servers.file_organizer import (
    apply_file_organization,
    get_category,
    plan_file_organization,
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
