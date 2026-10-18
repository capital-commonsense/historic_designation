PY := uv run python -m historic_preservation

.PHONY: all fetch build charts report test

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
