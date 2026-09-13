from pathlib import Path
import re
from datetime import datetime

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from markupsafe import Markup as _Markup

from viewer.catalog import (
    list_files,
    search_files,
    get_file_parts,
    list_tapes,
    get_tape,
    list_files_for_tape,
    get_file,
    get_catalog_stats,
)

from viewer.sync import (
    get_sync_status,
    sync_catalog,
)

from viewer.settings import (
    api_key_configured,
    get_catalog_url,
    get_settings,
    save_api_key,
    save_settings,
)


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CATALOG_PATH = DATA_DIR / "catalog.db"


app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)



_VIDEO_EXTS = {
    "mp4", "avi", "mov", "mkv", "wmv",
    "flv", "webm", "m4v", "mpg", "mpeg",
}

_AUDIO_EXTS = {
    "mp3", "wav", "flac", "aac", "ogg",
    "m4a", "wma",
}

_IMAGE_EXTS = {
    "jpg", "jpeg", "png", "gif", "bmp",
    "svg", "webp", "tiff", "ico",
}

_ARCHIVE_EXTS = {
    "zip", "tar", "gz", "tgz", "rar",
    "7z", "bz2", "xz",
}

_TEXT_EXTS = {
    "txt", "log", "rst", "ini", "cfg",
    "conf",
}

_CODE_BADGES = {
    "py": ("PY", "#4fa8e0"),
    "c": ("C", "#8aa6c1"),
    "h": ("C", "#8aa6c1"),
    "cpp": ("C++", "#e37fa6"),
    "cc": ("C++", "#e37fa6"),
    "cxx": ("C++", "#e37fa6"),
    "hpp": ("C++", "#e37fa6"),
    "cs": ("C#", "#9d7bea"),
    "js": ("JS", "#e0c34f"),
    "jsx": ("JSX", "#e0c34f"),
    "ts": ("TS", "#4f8be0"),
    "tsx": ("TSX", "#4f8be0"),
    "java": ("JAVA", "#d99a4e"),
    "go": ("GO", "#4fc3e0"),
    "rs": ("RS", "#e0904f"),
    "rb": ("RB", "#e05a5a"),
    "php": ("PHP", "#8b93e0"),
    "sh": ("SH", "#6fd18a"),
    "bash": ("SH", "#6fd18a"),
    "sql": ("SQL", "#e0a24f"),
    "html": ("HTML", "#e0824f"),
    "css": ("CSS", "#8b93e0"),
    "json": ("JSON", "#9ca3af"),
    "yaml": ("YML", "#e07a7a"),
    "yml": ("YML", "#e07a7a"),
    "xml": ("XML", "#6fa8e0"),
    "swift": ("SW", "#e07a8f"),
    "kt": ("KT", "#b48bea"),
    "md": ("MD", "#9ca3af"),
}


def file_icon(filename):
    if not filename or "." not in filename:
        return _Markup("📄")

    ext = filename.rsplit(
        ".",
        1,
    )[-1].lower()

    if ext in _VIDEO_EXTS:
        return _Markup("🎬")

    if ext in _AUDIO_EXTS:
        return _Markup("🎵")

    if ext in _IMAGE_EXTS:
        return _Markup("🖼️")

    if ext in _ARCHIVE_EXTS:
        return _Markup("🗜️")

    if ext == "pdf":
        return _Markup("📕")

    if ext in ("xls", "xlsx"):
        return _Markup("📊")

    if ext in ("ppt", "pptx"):
        return _Markup("📽️")

    if ext in ("doc", "docx"):
        return _Markup("📃")

    if ext in _TEXT_EXTS:
        return _Markup("📝")

    if ext in _CODE_BADGES:
        label, color = _CODE_BADGES[ext]

        return _Markup(
            '<span class="file-type-badge" '
            f'style="border-color:{color};'
            f'color:{color}">'
            f"{label}</span>"
        )

    return _Markup("📄")


def archive_label(value):
    text = str(value or "")

    match = re.match(
        r"^Archive-(\d{4})(\d{2})(\d{2})-"
        r"(\d{2})(\d{2})(\d{2})-"
        r"([0-9a-fA-F]{6,})$",
        text,
    )

    if not match:
        return text

    year, month, day, hour, minute, second, suffix = (
        match.groups()
    )

    try:
        dt = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    except ValueError:
        return text

    label = dt.strftime(
        "%b %d, %Y · %I:%M %p"
    )

    label = label.replace(
        " 0",
        " ",
    )

    return f"{label} · #{suffix.lower()}"


def format_bytes(value):
    if value is None:
        return "-"

    value = int(value)

    if value >= 1_000_000_000_000:
        return (
            f"{value / 1_000_000_000_000:.2f} TB"
        )

    if value >= 1_000_000_000:
        return (
            f"{value / 1_000_000_000:.2f} GB"
        )

    if value >= 1_000_000:
        return (
            f"{value / 1_000_000:.2f} MB"
        )

    if value >= 1_000:
        return (
            f"{value / 1_000:.2f} KB"
        )

    return f"{value} B"


app.jinja_env.filters[
    "file_icon"
] = file_icon

app.jinja_env.filters[
    "format_bytes"
] = format_bytes

app.jinja_env.filters[
    "archive_label"
] = archive_label



@app.route("/")
def index():
    return render_template(
        "index.html",
        catalog_exists=CATALOG_PATH.is_file(),
        sync_status=get_sync_status(),
    )


@app.route("/stats")
def stats_page():
    error = None
    stats = None

    try:
        stats = get_catalog_stats()

    except Exception as exc:
        error = str(exc)

    return render_template(
        "stats.html",
        stats=stats,
        error=error,
    )


@app.route("/files")
def files_page():
    query = request.args.get(
        "q",
        "",
    ).strip()

    requested_path = request.args.get(
        "path",
        "",
    ).strip().strip("/")

    error = None
    rows = []
    current_path = ""
    parent_path = None
    folder_count = 0
    file_count = 0

    try:
        if query:
            files = search_files(
                query
            )

            spanned_ids = [
                row["id"]
                for row in files
                if row.get(
                    "is_spanned"
                )
            ]

            parts_by_file = get_file_parts(
                spanned_ids
            )

            for file_row in files:
                rows.append(
                    {
                        "type": "file",
                        "file": file_row,
                        "parts": parts_by_file.get(
                            file_row["id"],
                            [],
                        ),
                    }
                )

            file_count = len(rows)

        else:
            files = list_files()

            current_parts = tuple(
                part
                for part
                in requested_path.split("/")
                if part
            )

            current_path = "/".join(
                current_parts
            )

            if current_parts:
                parent_path = "/".join(
                    current_parts[:-1]
                )

            folders = {}
            visible_files = []

            prefix_length = len(
                current_parts
            )

            for file_row in files:
                relative_path = str(
                    file_row.get(
                        "relative_path"
                    )
                    or ""
                ).strip("/")

                parts = tuple(
                    part
                    for part
                    in relative_path.split("/")
                    if part
                )

                if not parts:
                    continue

                if (
                    len(parts)
                    <= prefix_length
                    or parts[
                        :prefix_length
                    ]
                    != current_parts
                ):
                    continue

                remainder = parts[
                    prefix_length:
                ]

                if len(remainder) > 1:
                    folder_name = (
                        remainder[0]
                    )

                    folder_path = "/".join(
                        current_parts
                        + (folder_name,)
                    )

                    folder = (
                        folders.setdefault(
                            folder_name,
                            {
                                "type":
                                    "directory",
                                "name":
                                    folder_name,
                                "path":
                                    folder_path,
                                "size_bytes":
                                    0,
                                "file_count":
                                    0,
                            },
                        )
                    )

                    folder[
                        "size_bytes"
                    ] += int(
                        file_row.get(
                            "size_bytes"
                        )
                        or 0
                    )

                    folder[
                        "file_count"
                    ] += 1

                    continue

                visible_files.append(
                    file_row
                )

            for folder in sorted(
                folders.values(),
                key=lambda item: (
                    item["name"]
                    .casefold()
                ),
            ):
                rows.append(
                    folder
                )

            spanned_ids = [
                row["id"]
                for row
                in visible_files
                if row.get(
                    "is_spanned"
                )
            ]

            parts_by_file = get_file_parts(
                spanned_ids
            )

            for file_row in sorted(
                visible_files,
                key=lambda item: (
                    str(
                        item.get(
                            "filename"
                        )
                        or ""
                    ).casefold(),
                    int(
                        item["id"]
                    ),
                ),
            ):
                rows.append(
                    {
                        "type": "file",
                        "file": file_row,
                        "parts":
                            parts_by_file.get(
                                file_row[
                                    "id"
                                ],
                                [],
                            ),
                    }
                )

            folder_count = len(
                folders
            )

            file_count = len(
                visible_files
            )

    except Exception as exc:
        error = str(exc)

    return render_template(
        "files.html",
        rows=rows,
        query=query,
        current_path=current_path,
        parent_path=parent_path,
        folder_count=folder_count,
        file_count=file_count,
        error=error,
    )


@app.route("/files/<int:file_id>")
def file_detail_page(file_id):
    error = None
    file = None

    try:
        file = get_file(
            file_id
        )

        if file is None:
            error = "File was not found."

    except Exception as exc:
        error = str(exc)

    return render_template(
        "file_detail.html",
        file=file,
        error=error,
    )


@app.route("/tapes")
def tapes_page():
    error = None
    tapes = []

    try:
        tapes = list_tapes()

    except Exception as exc:
        error = str(exc)

    return render_template(
        "tapes.html",
        tapes=tapes,
        error=error,
    )


@app.route("/tapes/<int:tape_id>")
def tape_detail_page(tape_id):
    requested_path = request.args.get(
        "path",
        "",
    ).strip().strip("/")

    error = None
    tape = None
    rows = []
    current_path = ""
    parent_path = None
    folder_count = 0
    file_count = 0

    try:
        tape = get_tape(
            tape_id
        )

        if tape is None:
            error = "Tape was not found."

        else:
            files = list_files_for_tape(
                tape_id
            )

            current_parts = tuple(
                part
                for part in requested_path.split("/")
                if part
            )

            current_path = "/".join(
                current_parts
            )

            if current_parts:
                parent_path = "/".join(
                    current_parts[:-1]
                )

            folders = {}
            visible_files = []

            prefix_length = len(
                current_parts
            )

            for file_row in files:
                relative_path = str(
                    file_row.get(
                        "relative_path"
                    )
                    or ""
                ).strip("/")

                parts = tuple(
                    part
                    for part in relative_path.split("/")
                    if part
                )

                if not parts:
                    continue

                if (
                    len(parts) <= prefix_length
                    or parts[:prefix_length]
                    != current_parts
                ):
                    continue

                remainder = parts[
                    prefix_length:
                ]

                if len(remainder) > 1:
                    folder_name = remainder[0]

                    folder_path = "/".join(
                        current_parts
                        + (folder_name,)
                    )

                    folder = folders.setdefault(
                        folder_name,
                        {
                            "type": "directory",
                            "name": folder_name,
                            "path": folder_path,
                            "size_bytes": 0,
                            "file_count": 0,
                        },
                    )

                    folder["size_bytes"] += int(
                        file_row.get(
                            "size_bytes"
                        )
                        or 0
                    )

                    folder["file_count"] += 1

                    continue

                visible_files.append(
                    file_row
                )

            for folder in sorted(
                folders.values(),
                key=lambda row: (
                    row["name"].lower()
                ),
            ):
                rows.append(
                    folder
                )

            for file_row in sorted(
                visible_files,
                key=lambda row: (
                    str(
                        row.get("filename")
                        or ""
                    ).lower(),
                    row.get("id") or 0,
                ),
            ):
                rows.append(
                    {
                        "type": "file",
                        "file": file_row,
                    }
                )

            folder_count = len(
                folders
            )

            file_count = len(
                visible_files
            )

    except Exception as exc:
        error = str(exc)

    return render_template(
        "tape_detail.html",
        tape=tape,
        rows=rows,
        current_path=current_path,
        parent_path=parent_path,
        folder_count=folder_count,
        file_count=file_count,
        error=error,
    )


@app.route(
    "/settings",
    methods=["GET", "POST"],
)
def settings_page():
    error = None
    saved = (
        request.args.get("saved")
        == "1"
    )

    if request.method == "POST":
        try:
            save_settings(
                request.form.get(
                    "scheme",
                    "http",
                ),
                request.form.get(
                    "host",
                    "",
                ),
                request.form.get(
                    "port",
                    "8080",
                ),
            )

            save_api_key(
                request.form.get(
                    "catalog_mirror_api_key",
                    "",
                )
            )

            return redirect(
                url_for(
                    "settings_page",
                    saved=1,
                )
            )

        except Exception as exc:
            error = str(exc)

    settings = get_settings()

    return render_template(
        "settings.html",
        settings=settings,
        catalog_url=get_catalog_url(),
        api_key_configured=api_key_configured(),
        error=error,
        saved=saved,
    )


@app.route(
    "/sync",
    methods=["POST"],
)
def sync_now():
    sync_catalog()

    return redirect(
        url_for("index")
    )


@app.route("/health")
def health():
    status = get_sync_status()

    return jsonify(
        {
            "success": True,
            "service": (
                "TapeBox Catalog Viewer"
            ),
            "catalog_present": (
                CATALOG_PATH.is_file()
            ),
            "last_sync_success": (
                status.get(
                    "last_success"
                )
            ),
            "last_sync_result": (
                status.get(
                    "success"
                )
            ),
        }
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8081,
        debug=False,
    )
