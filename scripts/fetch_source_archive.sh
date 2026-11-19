#!/usr/bin/env bash
# Download the archived raw source material (data/raw/ and records_request/georgetown/)
# and unpack it into this checkout. Files that already exist locally are left alone.
#
# Usage: scripts/fetch_source_archive.sh [--keep]   (--keep saves the downloaded .tar.gz in tmp/)
set -euo pipefail

BASE_URL="https://sbma44.s3.amazonaws.com/capital-commonsense"
ARCHIVE="historic_designation_source.tar.gz"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$REPO_ROOT/tmp"
mkdir -p "$DEST"

keep=false
[[ "${1:-}" == "--keep" ]] && keep=true

echo "Downloading $ARCHIVE (about 1.5 GB)..."
curl -fL --retry 3 -C - -o "$DEST/$ARCHIVE" "$BASE_URL/$ARCHIVE"
curl -fsSL -o "$DEST/$ARCHIVE.sha256" "$BASE_URL/$ARCHIVE.sha256"

echo "Verifying checksum..."
if command -v sha256sum >/dev/null; then
  (cd "$DEST" && sha256sum -c "$ARCHIVE.sha256")
else
  (cd "$DEST" && shasum -a 256 -c "$ARCHIVE.sha256")
fi

echo "Unpacking into $REPO_ROOT (existing files are kept)..."
tar -xzkf "$DEST/$ARCHIVE" -C "$REPO_ROOT" 2>&1 | grep -v 'Cannot open: File exists\|already exists' || true

rm -f "$DEST/$ARCHIVE.sha256"
$keep || rm -f "$DEST/$ARCHIVE"

echo "Done. Raw snapshots are in data/raw/; run 'make all' to rebuild."
