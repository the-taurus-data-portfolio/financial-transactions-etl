#!/usr/bin/env python3
"""
Main entry point for the Bank to Target System ETL pipeline.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.etl_pipeline import ETLPipeline
from core.cli import run_cli


if __name__ == '__main__':
    exit_code = run_cli(ETLPipeline)
    sys.exit(exit_code)
