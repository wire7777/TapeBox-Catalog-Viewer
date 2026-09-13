import os
import time

from viewer.sync import sync_catalog


DEFAULT_INTERVAL = 300

try:
    interval = int(
        os.environ.get(
            "TAPEBOX_SYNC_INTERVAL_SECONDS",
            str(DEFAULT_INTERVAL),
        )
    )

except ValueError:
    interval = DEFAULT_INTERVAL

if interval < 60:
    interval = 60


def main():
    print(
        "TapeBox catalog auto-sync started.",
        flush=True,
    )

    print(
        f"Sync interval: {interval} seconds.",
        flush=True,
    )

    while True:
        result = sync_catalog()

        if result.get("success"):
            print(
                "Catalog sync successful:",
                result.get("last_success"),
                "| tapes:",
                result.get("tape_count"),
                "| files:",
                result.get("file_count"),
                flush=True,
            )

        else:
            print(
                "Catalog sync failed:",
                result.get("error"),
                flush=True,
            )

        time.sleep(
            interval
        )


if __name__ == "__main__":
    main()
