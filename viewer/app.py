from pathlib import Path

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

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

    error = None
    files = []
    parts_by_file = {}

    try:
        if query:
            files = search_files(
                query
            )
        else:
            files = list_files()

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

    except Exception as exc:
        error = str(exc)

    return render_template(
        "files.html",
        files=files,
        query=query,
        error=error,
        parts_by_file=parts_by_file,
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
    error = None
    tape = None
    files = []

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

    except Exception as exc:
        error = str(exc)

    return render_template(
        "tape_detail.html",
        tape=tape,
        files=files,
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
