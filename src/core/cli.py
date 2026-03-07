"""
Command-line interface (CLI) argument parsing and handling.
"""

import argparse
import sys
import traceback
from typing import Optional, List

from utils.logging_config import set_verbose_logging
from core.source_providers import LocalSourceProvider
from utils.file_utils import LocalFileArchiver


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Bank to Target System ETL Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        epilog="""
Examples:
  python src/main.py --input-dir ./data
  python src/main.py --config config/config.yaml
  python src/main.py --bank swedbank
        """
    )

    parser.add_argument(
        '--input-dir',
        help='Directory containing bank CSV files (local only, overrides config)'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file'
    )

    parser.add_argument(
        '--bank',
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
        help='Validate configuration and list files without processing'
    )

    return parser


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Args:
        args: Optional list of arguments to parse. If None, uses sys.argv.

    Returns:
        Parsed arguments Namespace
    """
    parser = create_argument_parser()
    return parser.parse_args(args)


def run_cli(pipeline_class) -> int:
    """
    Run the CLI application with the given pipeline class.

    Args:
        pipeline_class: The ETLPipeline class to instantiate and run

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_arguments()

    if args.verbose:
        set_verbose_logging()

    try:
        # Initialize pipeline
        pipeline = pipeline_class(config_path=args.config)

        # Override providers if --input-dir is specified (force local mode)
        if args.input_dir:
            # Setup local provider
            extensions = pipeline.config.get_supported_extensions()
            pipeline.source_provider = LocalSourceProvider(
                input_dir=args.input_dir,
                supported_extensions=extensions,
                logger=pipeline.logger
            )
            
            # Setup local archiver if archiving is enabled
            archiving_config = pipeline.config.get('archiving', {})
            if archiving_config.get('enabled', False):
                pipeline.archiver = LocalFileArchiver(
                    archive_dir=archiving_config.get('local', {}).get('archive_dir', 'data/archive'),
                    add_timestamp=archiving_config.get('add_timestamp', False),
                    logger=pipeline.logger
                )

        if args.dry_run:
            print("DRY RUN: Validating configuration and listing files...")
            files = pipeline.source_provider.list_files()
            print(f"Found {len(files)} files to process:")
            for f in files:
                print(f"  - {f['name']} (ID: {f['identifier']})")
            return 0

        # Run pipeline
        success = pipeline.run(
            input_dir=args.input_dir,
            override_bank_type=args.bank
        )

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        if args.verbose:
            traceback.print_exc()
        return 1
