# Bank to Tiller ETL Pipeline

A flexible and extensible ETL (Extract, Transform, Load) system for converting bank transaction data from various sources into a format suitable for import into Tiller Money.

## Features

- **Modular Architecture**: Easy to extend with new banks and target systems
- **Two-Step Transformation**: Bank → Intermediate → Tiller for maximum flexibility
- **Schema-Driven**: YAML-based schemas and mapping rules
- **Robust Error Handling**: Comprehensive logging and error recovery
- **Multiple Output Formats**: Console display and CSV file output
- **Configurable**: YAML-based configuration for all aspects
- **Tiller Reconciliation (Deduplication)**: Prevents duplicate imports by checking against existing transactions in the Tiller Sheet using Transaction ID matching

## Quick Start

### 1. Setup Environment

```bash
# Clone or create the project directory
mkdir bank_to_tiller_etl && cd bank_to_tiller_etl

# Create virtual environment
make setup
# or manually:
# python3 -m venv venv
# source venv/bin/activate  # On Windows: venv\Scripts\activate
# pip install -r requirements.txt
```

### 2. Configure Google Sheets (Required for Deduplication)

1. **Create Google Service Account** at [Google Cloud Console](https://console.cloud.google.com/)
2. **Enable Google Sheets API**
3. **Download JSON credentials** and save to `config/credentials/test-spreadsheet-credentials.json`
4. **Share Tiller spreadsheet** with service account email (Viewer permission)
5. **Update `config/config.yaml`**:
   ```yaml
   target_converters:
     tiller:
       deduplication:
         enabled: true
         spreadsheet_id: "your-tiller-spreadsheet-id"
         worksheet_title: "Transactions"
         table_name: "Table1"
         credentials_file: "config/credentials/test-spreadsheet-credentials.json"
   ```

### 3. Prepare Your Data

Place your bank CSV files in a directory. Files from multiple banks are supported:

```
data/
├── swedbank_export_2024_01.csv
├── swedbank_export_2024_02.csv
├── seb_export_2024_01.csv
└── lhv_export_2024_01.csv
```

The pipeline automatically detects the bank type from CSV headers.

### 4. Run the Pipeline

```bash
# Using make (recommended) - auto-detects bank types
make run INPUT_DIR=./data

# Or directly with python
python src/main.py --input-dir ./data

# With explicit bank type override (all files treated as this bank)
python src/main.py --input-dir ./data --bank swedbank
```

### 5. View Results

The pipeline will output:
- **Console**: Formatted transaction data ready for copy-paste into Tiller
- **Files**: CSV files in the `output/` directory
- **Logs**: Detailed processing logs in the `logs/` directory

## Project Structure

```
bank_to_tiller_etl/
├── config/
│   ├── config.yaml              # Main configuration
│   └── google-service-account.json  # Google API credentials (new)
├── schemas/
│   ├── swedbank_source.yaml     # Swedbank CSV schema
│   ├── intermediate.yaml        # Universal intermediate format
│   └── tiller_target.yaml       # Tiller import format
├── mappings/
│   ├── swedbank_to_intermediate.yaml  # Source transformation rules
│   └── intermediate_to_tiller.yaml    # Target transformation rules
├── src/
│   ├── main.py                  # Thin entry point
│   ├── core/                    # Core components
│   │   ├── cli.py               # CLI argument parsing
│   │   ├── etl_pipeline.py      # ETL pipeline orchestration
│   │   ├── target_converter_manager.py  # Target converter factory
│   │   ├── interfaces.py        # Abstract base classes
│   │   ├── schema_loader.py     # YAML schema loader
│   │   └── config_manager.py    # Configuration management
│   ├── converters/              # Data converters
│   │   ├── generic_source_converter.py  # Bank CSV to intermediate
│   │   ├── tiller_converter.py  # Intermediate to Tiller format
│   │   └── target_converter_manager.py  # Target converter manager
│   └── utils/                   # Utility functions
│       ├── bank_detector.py     # Automatic bank detection
│       ├── csv_utils.py         # Generic CSV utilities
│       ├── file_utils.py        # File discovery utilities
│       ├── date_utils.py        # Date transformations
│       ├── string_utils.py      # String transformations
│       ├── google_sheets_reader.py  # Google Sheets integration
│       └── logging_config.py    # Logging configuration
├── output/                      # Generated output files
├── logs/                        # Log files
├── requirements.txt             # Updated with gspread, google-api-python-client
├── Makefile
└── README.md
```

## Configuration

Edit `config/config.yaml` to customize the pipeline behavior:

```yaml
# Logging configuration
logging:
  level: "INFO"
  console: true
  file:
    enabled: true
    path: "logs/etl_pipeline.log"

# Output configuration
output:
  tiller_format:
    destination: "both"  # "console", "file", or "both"
    file_path: "output/tiller_transactions.csv"
    console_limit: 50

# Processing options
processing:
  strict_mode: false  # Stop on first error if true
  skip_invalid_rows: true
  validate_schemas: true

# Source bank configurations with sample files for header-based detection
source_converters:
  swedbank:
    source_schema: swedbank_source.yaml
    mapping: swedbank_to_intermediate.yaml
    sample_files:
      - "data/samples/transactions/swedbank_sample_ee.csv"
      - "data/samples/transactions/swedbank_sample_ru.csv"  # Multiple language versions supported
  lhv:
    source_schema: lhv_source.yaml
    mapping: lhv_to_intermediate.yaml
    sample_files:
      - "data/samples/transactions/lhv_sample_ee.csv"
  lhv_legacy:
    source_schema: lhv_legacy_source.yaml
    mapping: lhv_legacy_to_intermediate.yaml
    sample_files:
      - "data/samples/transactions/lhv_sample_legacy_ee.csv"
  seb:
    source_schema: seb_source.yaml
    mapping: seb_to_intermediate.yaml
    sample_files:
      - "data/samples/transactions/seb_sample_ee.csv"

# Target system configurations
target_converters:
  tiller:
    schema: tiller_target.yaml
    mapping: intermediate_to_tiller.yaml
    accounts_file: "config/tiller/accounts.yaml"  # Account mapping for Tiller
    # Deduplication configuration (set enabled: false to disable)
    deduplication:
      enabled: true
      spreadsheet_id: "your-tiller-spreadsheet-id-here"  # Your Tiller Google Sheet ID
      worksheet_title: "Transactions"  # Worksheet name
      table_name: "Table1"  # Table name in the worksheet
      credentials_file: "config/credentials/test-spreadsheet-credentials.json"  # Google API credentials

# Directory paths
paths:
  schemas_dir: "schemas"
  mappings_dir: "mappings"
  output_dir: "output"
  logs_dir: "logs"
```

## Customizing Accounts Mapping

The accounts file defines how to map account numbers to Tiller account names and IDs. To use a custom accounts file:

Edit `config.yaml`:
```yaml
target_converters:
  tiller:
    accounts_file: "config/tiller/accounts_sample.yaml"  # Your custom file path
```

No code changes needed - the pipeline will load your custom accounts file automatically.

## Deduplication

The pipeline prevents duplicate transactions by comparing Transaction IDs:

- **How it works**: Loads existing Transaction IDs from Tiller Google Sheet, compares with new transactions
- **Performance**: O(1) set lookup, handles thousands of transactions efficiently
- **Logging**: Reports number of duplicates found and removed

To disable deduplication: Set `target_converters.tiller.deduplication.enabled: false` in config.

## Command Line Options

```bash
python src/main.py --help

Options:
  --input-dir DIR     Directory containing bank CSV files (required)
  --config FILE       Configuration file path (default: config/config.yaml)
  --bank TYPE         Bank type to use (override auto-detection).
                      Supported: swedbank, seb, lhv.
                      If not specified, banks are detected from CSV headers.
  --verbose, -v       Enable verbose logging
  --dry-run          Validate files without processing
```

## Examples

### Basic Usage (Auto-detect bank types from CSV headers)
```bash
python src/main.py --input-dir ./bank_exports
```

### Mixed Banks in One Directory
```bash
# Process files from multiple banks automatically
python src/main.py --input-dir ./data
# Files are detected and processed based on their CSV headers
```

### Explicit Bank Type
```bash
# Force all files to be treated as Swedbank format
python src/main.py --input-dir ./data --bank swedbank
```

### With Custom Configuration
```bash
python src/main.py --input-dir ./data --config ./my_config.yaml
```

### Dry Run (Validation Only)
```bash
python src/main.py --input-dir ./data --dry-run
```

### Verbose Logging
```bash
python src/main.py --input-dir ./data --verbose
```

## Testing

### Sample Data

Sample CSV files in `data/samples/transactions/` are used for bank detection and testing:
- `swedbank_sample_ee.csv` - Swedbank (Estonian)
- `swedbank_sample_ru.csv` - Swedbank (Russian) - tests language detection
- `seb_sample_ee.csv` - SEB (Estonian)
- `lhv_sample_ee.csv` - LHV (Estonian)

### Quick Test

```bash
# Validate configuration and sample files
python src/main.py --input-dir data/samples/transactions --dry-run

# Process all samples with test config (disables deduplication, uses accounts_sample.yaml)
python src/main.py --input-dir data/samples/transactions --config config_test.yaml

# Test multi-bank auto-detection
python src/main.py --input-dir data/samples/transactions --verbose

# Test language detection (Russian Swedbank)
python src/main.py --input-dir data/samples/transactions --bank swedbank --verbose
```

### Validation

After testing, check:
- `output/tiller_transactions.csv` - Transaction data ready for Tiller
- `logs/etl_pipeline.log` - Processing details and bank detection messages

## Data Processing Flow

1. **Bank Type Detection**: Analyze CSV header row to identify the bank.
   - Matches required fields from configured bank schemas
   - Supports auto-detection or manual override via `--bank` parameter
   - Works with multiple banks in the same directory

2. **Source Data Loading**: Load bank CSV files according to detected bank's schema

3. **Row Filtering**: Apply filters (e.g., exclude balance rows, include only transactions)

4. **Source Transformation**: Convert to intermediate format with:
   - Date format standardization
   - Amount sign calculation (debit/credit)
   - IBAN anonymization
   - String cleaning

5. **Target Transformation**: Convert to Tiller format with:
   - Date format conversion (DD.MM.YYYY → M/D/YYYY)
   - Month/week calculations
   - Transaction ID generation
   - Field mapping to Tiller columns

6. **Deduplication**: Check Transaction IDs against existing Tiller data, exclude duplicates

7. **Output Generation**: Save to files and/or display in console

## How Bank Detection Works

The pipeline uses **exact header matching** for automatic bank detection:

1. **On Startup**:
   - Reads the first row (header) from each sample file in `config.yaml`
   - Stores these headers as "signatures" for each bank

2. **During Processing**:
   - For each CSV file, reads its first row
   - Compares it exactly against all known signatures
   - Matches the file to the bank if headers match (same column names, order, and capitalization)

3. **Key Features**:
   - ✅ Supports multiple languages (e.g., Swedbank in Estonian and Russian)
   - ✅ Handles different CSV delimiters (`;`, `,`, `\t`)
   - ✅ Requires exact header match for reliability
   - ✅ Falls back to `--bank` override if auto-detection fails

4. **Example**:
   ```
   File: transaction_jan_ru.csv
   Header: "Счëт клиентa";"Строковый тип";"Дата"...

   Check against signatures:
   ❌ Swedbank (EE): "Kliendi konto";"Reatüüp"... (doesn't match)
   ✅ Swedbank (RU): "Счëт клиентa";"Строковый тип"... (MATCH!)

   Result: Processed as Swedbank (Russian)
   ```

## Supported Banks

Currently supported (all with automatic header-based detection):
- **Swedbank Estonia**: Full support with schema and mappings (Estonian and Russian language headers)
- **SEB Estonia**: Full support with schema and mappings
- **LHV Estonia**: Full support for both modern (16-column) and legacy (19-column) CSV formats

The pipeline automatically detects which bank a CSV file belongs to by analyzing its headers.

## Adding New Banks

To add support for a new bank with automatic header detection:

1. **Create Source Schema**: Add `schemas/newbank_source.yaml` defining the CSV structure
2. **Create Mapping Rules**: Add `mappings/newbank_to_intermediate.yaml` with transformation rules
3. **Add Sample File**: Place a representative CSV export in `data/samples/transactions/newbank_sample_XX.csv`
   - Headers must exactly match your bank's export format (case-sensitive, same order)
   - The sample file header is used for automatic bank detection
   - Multiple samples per bank are supported (for different languages/versions)
4. **Update Configuration**: Add bank to `source_converters` in `config/config.yaml`:

```yaml
source_converters:
  newbank:
    source_schema: newbank_source.yaml
    mapping: newbank_to_intermediate.yaml
    sample_files:
      - "data/samples/transactions/newbank_sample_ee.csv"
      - "data/samples/transactions/newbank_sample_en.csv"  # Optional: another language/version
```

Example source schema structure:
```yaml
schema_name: "New Bank Source CSV Schema"
file_details:
  delimiter: ";"
  decimal_separator: ","
  date_format: "DD.MM.YYYY"
fields:
  - name: "Date"
    alias: "TransactionDate"
    type: "string"
    description: "Transaction date"
  # ... more fields
```

**Important**: The pipeline performs exact header matching on startup. The sample file header row must exactly match the real CSV exports from this bank (including column order and capitalization). This ensures reliable auto-detection across different CSV sources.

## Adding New Target Systems

To add support for a new target system (beyond Tiller):

1. **Create Target Schema**: Add `schemas/newsystem_target.yaml`
2. **Create Mapping Rules**: Add `mappings/intermediate_to_newsystem.yaml`
3. **Create Converter Class**: Implement converter in `src/converters/newsystem_converter.py` inheriting from `TargetConverter`
   - Must implement `save_output()` method for custom output handling
4. **Update Target Converter Manager**: Add to `src/core/target_converter_manager.py` in the `_create_converter()` method:
   ```python
   if target_name == 'newsystem':
       from converters.newsystem_converter import NewSystemConverter
       return NewSystemConverter(self.schema_loader, target_config)
   ```
5. **Add Configuration**: Add to `config.yaml` under `target_converters`:

```yaml
target_converters:
  newsystem:
    schema: newsystem_target.yaml
    mapping: intermediate_to_newsystem.yaml
    # Any system-specific configuration
    custom_setting: "value"
```

The configuration structure mirrors `source_converters` for consistency. The `TargetConverterManager` automatically instantiates the appropriate converter based on the configuration.

## Troubleshooting

### Common Issues

**Deduplication Configuration Issues**
```bash
# If you see: "Failed to initialize deduplication" or duplicate filtering not working

# Check if deduplication is enabled:
grep -A 5 "deduplication:" config/config.yaml

# Verify credentials file path exists:
ls -la config/credentials/test-spreadsheet-credentials.json

# To disable deduplication for testing:
target_converters:
  tiller:
    deduplication:
      enabled: false  # Set to false
```

**Custom Accounts File Not Loading**
```bash
# If accounts aren't being mapped correctly:

# 1. Verify the file path in config.yaml:
grep "accounts_file" config/config.yaml

# 2. Check if the file exists:
ls -la config/tiller/accounts_sample.yaml

# 3. Enable verbose logging to see what's happening:
python src/main.py --input-dir ./data --verbose 2>&1 | grep -i "accounts"
```

**Bank Auto-Detection Failing**
```bash
# If you see: "Could not auto-detect bank type for file.csv. Header does not match any known signatures."

# This means the CSV header doesn't match the sample files. Possible causes:
# 1. Different CSV format/language version not in config
# 2. Column order is different from sample files
# 3. Column names are different (case-sensitive!)

# Solution: Use explicit bank type to override auto-detection
python src/main.py --input-dir ./data --bank swedbank

# Or: Add a new sample file to data/samples/transactions/ for the new format
# Then add it to config.yaml under the bank's sample_files list
```

**Headers Don't Match Despite Same Bank**
- Check column capitalization and spelling (must match exactly)
- Verify column order matches the sample file
- Look at actual CSV header row: `head -1 yourfile.csv`
- Compare with sample: `head -1 data/samples/transactions/swedbank_sample_ee.csv`

**Google Sheets Access Errors**
```bash
# Verify credentials file
cat config/google-service-account.json | python -m json.tool

# Check spreadsheet ID and service account permissions
```

**Deduplication Not Working** (new)
```bash
# Check if enabled
grep -A 3 "deduplication:" config/config.yaml

# Check logs
grep "Transaction ID" logs/etl_pipeline.log
```

**File Not Found Errors**
```bash
# Ensure all required directories exist
mkdir -p schemas mappings config output logs

# Verify file paths in error messages
ls -la schemas/ mappings/
```

**Schema Validation Failures**
```bash
# Run with dry-run to validate configuration
python src/main.py --input-dir ./data --dry-run

# Check schema files match your CSV structure
head -1 your_bank_file.csv
```

**Date Parsing Issues**
- Verify date format in source schema matches your CSV
- Check for inconsistent date formats within the same file
- Enable verbose logging to see parsing details

**Amount Conversion Problems**
- Confirm decimal separator setting (comma vs dot)
- Verify debit/credit indicators in your data
- Check for thousand separators or currency symbols

### Debug Mode

Enable detailed logging:
```bash
# Edit config/config.yaml
logging:
  level: "DEBUG"  # Change from INFO to DEBUG

# Or use environment variable
export LOG_LEVEL=DEBUG
python src/main.py --input-dir ./data --verbose
```

### Log Analysis

Check logs for detailed processing information:
```bash
# View recent logs
tail -f logs/etl_pipeline.log

# Search for errors
grep -i error logs/etl_pipeline.log

# View deduplication stats (new)
grep -i "duplicate" logs/etl_pipeline.log
```

## Data Privacy and Security

The pipeline includes several privacy protection features:

- **IBAN Anonymization**: Automatically masks account numbers (e.g., EE333...5678 → EE***5678)
- **Local Processing**: All data processing happens locally, no external services
- **Read-Only Access**: Google Sheets access is read-only (new)
- **Configurable Masking**: Customize sensitive data masking patterns
- **Audit Logging**: Complete processing trail in log files

## Performance Considerations

- **Memory Usage**: Large CSV files are processed in pandas DataFrames; monitor memory usage
- **File Size Limits**: Tested with files up to 100MB; larger files may require chunking
- **Processing Speed**: ~1000 transactions per second on typical hardware
- **Deduplication**: O(1) set lookup, minimal performance impact (new)

## Contributing

When extending the pipeline:

1. **Follow Interfaces**: Inherit from `SourceConverter` or `TargetConverter` abstract classes
2. **Modular Architecture**: The pipeline uses a highly modular design:
   - `core/cli.py` - CLI argument parsing
   - `core/etl_pipeline.py` - Pipeline orchestration
   - `core/target_converter_manager.py` - Target converter factory
   - `utils/` - Reusable utilities (bank_detector, file_utils, csv_utils, etc.)
   - `converters/` - Source and target converter implementations
3. **Add Tests**: Include unit tests for new converters (future enhancement)
4. **Update Documentation**: Add new bank/system support to this README
5. **Update TargetConverterManager**: If adding new target systems, update `_create_converter()` method
6. **Logging**: Use the provided logging infrastructure consistently

## API Reference

### Core Classes

#### `ConfigManager`
Manages YAML configuration loading and access.

```python
config = ConfigManager('config/config.yaml')
log_config = config.get_logging_config()
output_config = config.get_output_config()
```

#### `YamlSchemaLoader`
Loads and validates YAML schemas and mappings.

```python
loader = YamlSchemaLoader('schemas', 'mappings')
schema = loader.load_schema('swedbank_source.yaml')
mapping = loader.load_mapping('swedbank_to_intermediate.yaml')
```

#### `GenericSourceConverter`
Converts any bank CSV to intermediate format.

```python
converter = GenericSourceConverter(schema_loader, 'swedbank', 'swedbank_source.yaml', 'swedbank_to_intermediate.yaml')
intermediate_df = converter.process_file('data/swedbank.csv')
```

#### `TillerConverter`
Converts intermediate format to Tiller format with deduplication.

```python
converter = TillerConverter(schema_loader, tiller_config)
tiller_df = converter.transform_to_target(intermediate_df)
```

#### `GoogleSheetsReader` (new)
Loads Transaction IDs from Google Sheets.

```python
reader = GoogleSheetsReader('config/google-service-account.json')
transaction_ids = reader.load_transaction_ids(spreadsheet_id, worksheet_title)
```

### Utility Functions

#### Date Utilities
```python
from src.utils.date_utils import convert_date_format, date_to_month_start

# Convert date formats
tiller_date = convert_date_format('31.12.2024', 'DD.MM.YYYY', 'M/D/YYYY')
# Result: '12/31/2024'

# Get month start
month_start = date_to_month_start('15.03.2024', 'DD.MM.YYYY', 'M/D/YY')
# Result: '3/1/24'
```

#### String Utilities
```python
from src.utils.string_utils import anonymize_iban, parse_amount

# Anonymize IBAN
safe_iban = anonymize_iban('EE382200221020145685')
# Result: 'EE***45685'

# Parse amount with different decimal separators
amount = parse_amount('1,234.56', decimal_separator='.')
# Result: 1234.56
```

## Version History

- **v1.0.0**: Initial release with Swedbank support
- **v2.0.0**: Added Google Sheets integration and Transaction ID-based deduplication (new)
- **Future**: Additional banks, enhanced error handling, performance improvements

## License

This project is provided as-is for personal and educational use. Ensure compliance with your bank's terms of service when exporting transaction data.

## Support

For issues and questions:

1. Check the troubleshooting section above
2. Review log files for detailed error information
3. Verify your CSV format matches the expected schema
4. Test with a small sample file first

## Technical Notes

### Dependencies
- **pandas**: DataFrame operations and CSV processing
- **PyYAML**: Configuration and schema file parsing
- **python-dateutil**: Advanced date parsing capabilities
- **gspread**: Google Sheets API integration (new)
- **google-api-python-client**: Google API client library (new)
- **oauth2client**: OAuth2 authentication (new)

### Python Version
- Minimum: Python 3.8
- Recommended: Python 3.9+

### Operating System
- Cross-platform: Windows, macOS, Linux
- Tested on: Ubuntu 20.04+, macOS 12+, Windows 10+

### Memory Requirements
- Minimum: 512MB RAM
- Recommended: 2GB+ for large datasets
- Disk space: ~100MB for installation + space for output files