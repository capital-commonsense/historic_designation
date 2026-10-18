PY := uv run python -m historic_preservation

.PHONY: all fetch build charts test

# From the newest complete raw snapshot (or $HP_SNAPSHOT) to every output.
all: build charts test

fetch:
	$(PY) fetch

build:
	$(PY) build

charts:
	$(PY) charts

test:
	uv run pytest -q
