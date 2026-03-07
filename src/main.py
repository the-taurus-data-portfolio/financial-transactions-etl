# src/main.py
"""
Entry point for the Bank to Tiller ETL pipeline.
"""

import sys
import argparse
from pathlib import Path

from core.etl_pipeline import ETLPipeline


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Convert bank transaction CSVs to Tiller format.'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        help='Directory containing bank CSV files (local only)'
    )
    parser.add_argument(
        '--config',
        type=str,
        default='config/config.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--bank',
        type=str,
        help='Bank type override (swedbank, seb, lhv, lhv_legacy)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate files without actual processing (not implemented yet)'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    if not Path(args.config).exists():
        print(f"FATAL ERROR: Configuration file not found: {args.config}")
        sys.exit(1)

    try:
        pipeline = ETLPipeline(args.config)
        
        # Verbose logging override if requested
        if args.verbose:
            import logging
            logging.getLogger().setLevel(logging.DEBUG)

        success = pipeline.run(
            input_dir=args.input_dir,
            override_bank_type=args.bank
        )

        if not success:
            sys.exit(1)

    except Exception as e:
        print(f"FATAL ERROR: {e}")
        # In verbose mode, print the full traceback
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
