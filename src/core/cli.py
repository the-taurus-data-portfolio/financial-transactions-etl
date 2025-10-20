"""
Command-line interface (CLI) argument parsing and handling.
"""

import argparse
import sys

from utils.file_utils import get_input_files


def create_argument_parser() -> argparse.ArgumentParser:
    """
    Create command line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Bank to Target System ETL Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input-dir ./data
  python main.py --input-dir /path/to/bank/exports --config custom_config.yaml
  python main.py --input-dir ./data --bank swedbank
        """
    )

    parser.add_argument(
        '--input-dir',
        required=True,
        help='Directory containing bank CSV files to process'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to configuration file (default: config/config.yaml)'
    )

    parser.add_argument(
        '--bank',
        default=None,
        help='Bank type to use (override auto-detection). '
             'Supported: swedbank, seb, lhv. If not specified, banks are detected from CSV headers.'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate files and configuration without processing'
    )

    return parser


def parse_arguments(args=None):
    """
    Parse command-line arguments.

    Args:
        args: Optional list of arguments to parse (for testing). If None, uses sys.argv.

    Returns:
        Parsed arguments
    """
    parser = create_argument_parser()
    return parser.parse_args(args)


def run_cli(pipeline_class):
    """
    Run the CLI application with the given pipeline class.

    Args:
        pipeline_class: The ETLPipeline class to instantiate and run

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_arguments()

    try:
        # Initialize pipeline
        pipeline = pipeline_class(config_path=args.config)

        if args.dry_run:
            print("DRY RUN: Validating configuration and finding files...")
            supported_extensions = pipeline.config.get_supported_extensions()
            input_files = get_input_files(args.input_dir, supported_extensions)
            print(f"Found {len(input_files)} files:")
            for file_path in input_files:
                print(f"  - {file_path}")
            print("Configuration validation passed. Use without --dry-run to process files.")
            return 0

        # Run pipeline with optional bank override
        success = pipeline.run(args.input_dir, override_bank_type=args.bank)

        return 0 if success else 1

    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        return 1
