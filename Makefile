PY := uv run python -m historic_preservation

.PHONY: all fetch build charts report test video osm

# From the newest complete raw snapshot (or $HP_SNAPSHOT) to every output.
all: build charts report test

fetch:
	$(PY) fetch

build:
	$(PY) build

charts:
	$(PY) charts

report:
	$(PY) report

test:
	uv run pytest -q

# Not part of `all`: needs the Geofabrik extracts in tmp/osm/ (records_request/manual_fetch.md).
osm:
	uv run python -m historic_preservation.fetch.osm

# Animated comparison: about 450 frames to tmp/frames/, then charts/out/comps_designated_land.mp4, and the
# portrait phone version (tmp/frames_mobile/) to charts/out/mobile_optimized/ as mp4 and GIF.
video:
	uv run python -m historic_preservation.charts.comps_video
