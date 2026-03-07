# src/main.py
"""
Entry point for the Bank to Tiller ETL pipeline.
"""

import sys
from core.etl_pipeline import ETLPipeline
from core.cli import run_cli


def main():
    """Main entry point."""
    exit_code = run_cli(ETLPipeline)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
