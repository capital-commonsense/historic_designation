"""CLI: python -m historic_preservation {fetch,build,charts,report,all}."""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="historic_preservation")
    parser.add_argument("stage", choices=["fetch", "build", "charts", "report", "all"])
    args = parser.parse_args()

    if args.stage == "fetch":
        from historic_preservation import fetch

        fetch.run()
    if args.stage in ("build", "all"):
        from historic_preservation import analysis, join, normalize

        normalize.run()
        join.run()
        analysis.run()
    if args.stage in ("charts", "all"):
        from historic_preservation import charts

        charts.run()
    if args.stage in ("report", "all"):
        from historic_preservation import report

        report.run()


if __name__ == "__main__":
    main()
