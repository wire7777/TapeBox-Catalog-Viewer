# TapeBox Catalog Viewer

TapeBox Catalog Viewer is a standalone, read-only web interface for browsing a mirrored TapeBox catalog.

It runs in Docker on a separate Linux machine and does **not** require an LTO drive, LTFS, or tape hardware.

The viewer periodically downloads a consistent SQLite catalog snapshot from a TapeBox server and keeps its own local copy.

## Features

- Read-only catalog browsing
- Virtual folder browsing
- Browse files by tape
- Search files
- Tape details
- File details
- Spanned-file information
- Manual Sync Now
- Automatic background sync
- Keeps the last good catalog if TapeBox is offline
- No LTO or LTFS software required
- No archive, restore, erase, eject, or tape-control functions

## Architecture

```text
TapeBox Server
      |
      | authenticated catalog snapshot
      v
TapeBox Catalog Viewer
      |
      +-- catalog-viewer   Web UI :8081
      |
      +-- catalog-sync     Automatic sync worker
      |
      +-- ./data/catalog.db
```

## Requirements

The viewer machine needs:

- Linux
- Docker Engine
- Docker Compose plugin
- Git
- Network access to the TapeBox server

Check Docker:

```bash
docker --version
docker compose version
```

## Install

Clone the repository:

```bash
cd /opt

sudo git clone https://github.com/wire7777/TapeBox-Catalog-Viewer.git tapebox-catalog-viewer

sudo chown -R "$USER":"$USER" /opt/tapebox-catalog-viewer

cd /opt/tapebox-catalog-viewer
```

## Docker User Permissions

The containers use configurable `PUID` and `PGID` values so they can run as a normal Linux user without hard-coded host IDs.

Check your UID and GID:

```bash
id
```

Create a local environment file using your current UID and GID:

```bash
printf 'PUID=%s\nPGID=%s\n' "$(id -u)" "$(id -g)" > .env
```

Check it:

```bash
cat .env
```

Example:

```text
PUID=1000
PGID=126
```

Create the persistent data directory:

```bash
mkdir -p data
```

Set ownership to the same UID and GID configured in `.env`.

Example:

```bash
sudo chown -R 1000:126 data
```

The real `.env` file is ignored by Git. Only `.env.example` is tracked.

## Build and Start

Build and start both Docker services:

```bash
cd /opt/tapebox-catalog-viewer

docker compose up -d --build
```

Check container status:

```bash
docker compose ps
```

You should see:

```text
tapebox-catalog-viewer
tapebox-catalog-sync
```

## Open the Viewer

Open the viewer in a browser:

```text
http://VIEWER-IP:8081
```

Example:

```text
http://192.168.2.170:8081
```

## First-Time Setup

Open the **Settings** page.

Configure:

```text
Protocol: http
Host:     TapeBox server IP
Port:     8080
API Key:  TapeBox catalog mirror API key
```

Example:

```text
Protocol: http
Host:     TAPEBOX-SERVER-IP
Port:     8080
```

The API key must match the catalog mirror API key configured on the TapeBox server.

The viewer stores the API key separately at:

```text
./data/mirror-api-key
```

The API key is not stored in the mirrored TapeBox SQLite database.

## Catalog Sync

Use **Sync Now** on the Viewer home page for a manual catalog sync.

The `catalog-sync` container also checks automatically.

The default sync interval is:

```text
300 seconds
```

The sync process is:

```text
download snapshot
      |
      v
catalog.new.db
      |
      v
validate SQLite
      |
      v
atomic replace
      |
      v
catalog.db
```

If synchronization fails, the last good `catalog.db` is preserved.

This allows the Viewer to continue browsing the last successful catalog even if the TapeBox server is temporarily offline.

## Persistent Data

Runtime files are stored under:

```text
./data/
```

Typical files include:

```text
catalog.db
catalog.db-shm
catalog.db-wal
mirror-api-key
settings.json
sync-status.json
sync.lock
```

These runtime files are excluded from Git.

## Logs

Viewer logs:

```bash
docker compose logs --tail=100 catalog-viewer
```

Sync worker logs:

```bash
docker compose logs --tail=100 catalog-sync
```

Follow all logs:

```bash
docker compose logs -f
```

## Health Check

```bash
curl http://127.0.0.1:8081/health
```

## Restart

```bash
docker compose restart
```

## Stop

```bash
docker compose down
```

The persistent `data` directory is not removed.

## Start Again

```bash
docker compose up -d
```

## Update

```bash
cd /opt/tapebox-catalog-viewer

git pull

docker compose up -d --build
```

Your catalog, settings, and API key remain in `./data/`.

## Troubleshooting

Check container status:

```bash
docker compose ps
```

Check data directory ownership:

```bash
ls -ln data
```

Check your UID and GID:

```bash
id
```

If catalog sync fails, verify:

- TapeBox server IP
- TapeBox port
- API key
- LAN connectivity
- Firewall rules
- `data` directory permissions

## Read-Only Design

TapeBox Catalog Viewer is intentionally read-only.

It cannot:

- Archive files
- Restore files
- Delete files from TapeBox
- Remove tapes from the TapeBox catalog
- Format tapes
- Erase tapes
- Mount LTFS
- Eject tapes
- Control an LTO drive
- Write to the TapeBox live catalog

The Viewer only downloads a catalog snapshot and reads its own local copy.

## Security

Recommended:

- Keep TapeBox and the Viewer on a trusted LAN
- Do not expose the catalog mirror endpoint directly to the Internet
- Use a strong random API key
- Protect `data/mirror-api-key`
- Never commit runtime files or credentials to Git

## Repositories

TapeBox Catalog Viewer:

https://github.com/wire7777/TapeBox-Catalog-Viewer

Main TapeBox project:

https://github.com/wire7777/TapeBox
