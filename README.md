# DC historic preservation data

A reproducible pipeline that collects public data on Washington, DC's historic preservation system, tests a set of hypotheses about how it works, and regenerates every number and chart from one command.

- **Findings:** [`findings.md`](findings.md), generated on every build
- **Charts:** [`charts/out/`](charts/out/). Each chart is saved as SVG, PNG and `.data.csv`, the exact data it plots.
- **Charts for phones and newsletters:** [`charts/out/mobile_optimized/`](charts/out/mobile_optimized/). The same charts as PNGs, narrower and taller with larger type, with side-by-side panels stacked and legends beneath the plot. The animation is there too, in portrait as mp4 and GIF.
- **Sources:** [`SOURCES.md`](SOURCES.md)
- **Methods notes:** [`methods/`](methods/)
- **What each year's records cover:** [`coverage.md`](coverage.md)

## Running it

You need [uv](https://docs.astral.sh/uv/) (Python 3.14) and Poppler's `pdftotext`.

```sh
make fetch   # download raw data into a new dated snapshot under data/raw/
make all     # normalize, join, analyze, chart, write findings.md, run tests
```

`make all` reads the newest complete snapshot, or the one named in `$HP_SNAPSHOT`.

Optional extras:
- `make video` builds the animated city comparison. It needs `ffmpeg`.
- `make osm` builds the OpenStreetMap building counts. It needs `osmium` and the Geofabrik extracts.
- `ocrmypdf` reads scanned PDFs.
- macOS `textutil` or LibreOffice reads HPO's case log, a Word file released under FOIA.
- `make video` adds a wordmark if `HP_BRAND_DIR` names a local checkout of the Capital Commonsense brand kit.

### Raw data

Raw downloads aren't in the repository because they're large. Derived tables under `data/analysis/` and the charts are committed.

The raw material behind the committed outputs is archived on S3: the 2026-10-17 snapshot, the hand-downloaded sources under `data/raw/manual/`, and `records_request/georgetown/`. To rebuild from exactly what we used, without re-fetching:

```sh
scripts/fetch_source_archive.sh   # or: make source
make all
```

The script downloads the archive (about 1.5 GB, 2.3 GB unpacked), checks its SHA-256 and unpacks it into the checkout. It doesn't overwrite files you already have. Pass `--keep` to keep the downloaded `.tar.gz` in `tmp/`. To get it by hand:

- https://sbma44.s3.amazonaws.com/capital-commonsense/historic_designation_source.tar.gz
- https://sbma44.s3.amazonaws.com/capital-commonsense/historic_designation_source.tar.gz.sha256

Unpack it from the repository root with `tar -xzf historic_designation_source.tar.gz`.

`make fetch` gets the sources the code can reach directly:
- DC GIS
- planning.dc.gov
- the comparison cities' open data portals
- ProPublica
- CourtListener

Some sources were downloaded by hand and go under `data/raw/manual/`; see [`records_request/manual_fetch.md`](records_request/manual_fetch.md):
- the Georgetown Law collection of Mayor's Agent decisions
- the Historic Preservation Office's archive of HPRB meeting records
- some DC Preservation League Form 990s

CourtListener's opinion text needs a free API token. Set `COURTLISTENER_TOKEN` in the environment or in a `.env` file, which is ignored by git.

Chart fonts (Newsreader and IBM Plex Sans, under the SIL Open Font License) are in `fonts/`, so rebuilt charts match the committed ones.

## How it's organized

```
src/historic_preservation/
  fetch/      raw downloads, polite (at least 1 s between requests) and cached; snapshots are never overwritten
  normalize/  typed tables from the raw files
  join/       designations, nominations, lots and cases linked together
  analysis/   one module per question; writes data/analysis/
  charts/     one function per chart; writes charts/out/
  report.py   findings.md and coverage.md
inputs/       hand-curated CSVs: each row has a source and, usually, a quote checked against the source on every build
tests/        validation targets and consistency checks
```

**Hand-curated inputs.** Any figure read by hand lives in `inputs/`, not in code. Examples are designation dates, Mayor's Agent outcomes, Form 990 lines, and HPO annual report tables. Each row names its source document. Where there's a quote, the build fails if the quote can't be found in that document.

**Chart headlines.** Chart headlines are computed from the data. To set one by hand, put it in `inputs/chart_titles.json`. Each build prints the computed headline and any override, so a figure that has moved shows up.

## Privacy

Property owners' names appear only in the raw downloads. They're dropped at normalization and never appear in inputs, outputs or charts. Philadelphia owner fields aren't fetched. Court cases brought by private individuals are labelled `[individual]`.
