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
3. **Download JSON credentials** and save to `config/google-service-account.json`
4. **Share Tiller spreadsheet** with service account email (Viewer permission)
5. **Update `config/config.yaml`**:
   ```yaml
   tiller_history_source:
     enabled: true
     spreadsheet_id: "your-tiller-spreadsheet-id"
     worksheet_title: "Transactions"
     table_name: "Table1"
     credentials_file: "config/google-service-account.json"
   ```

### 3. Prepare Your Data

Place your bank CSV files in a directory, e.g., `./data/`:

```
data/
├── swedbank_export_2024_01.csv
├── swedbank_export_2024_02.csv
└── swedbank_export_2024_03.csv
```

### 4. Run the Pipeline

```bash
# Using make (recommended)
make run INPUT_DIR=./data

# Or directly with python
python src/main.py --input-dir ./data
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
│   ├── main.py                  # Entry point
│   ├── core/                    # Core components
│   │   ├── interfaces.py        # Abstract base classes
│   │   ├── schema_loader.py     # YAML schema loader
│   │   └── config_manager.py    # Configuration management
│   ├── converters/              # Data converters
│   │   ├── generic_source_converter.py
│   │   └── tiller_converter.py  # Now with deduplication
│   └── utils/                   # Utility functions
│       ├── date_utils.py
│       ├── string_utils.py
│       ├── google_sheets_reader.py  # New: Google Sheets integration
│       └── logging_config.py
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

# Tiller history source configuration for deduplication (new)
tiller_history_source:
  enabled: true  # Set to false to disable deduplication
  spreadsheet_id: "your-tiller-spreadsheet-id-here"
  worksheet_title: "Transactions"  # The title of the worksheet
  table_name: "Table1"  # The name of the table within the sheet
  credentials_file: "config/google-service-account.json"
```

## Deduplication

The pipeline prevents duplicate transactions by comparing Transaction IDs:

- **How it works**: Loads existing Transaction IDs from Tiller Google Sheet, compares with new transactions
- **Performance**: O(1) set lookup, handles thousands of transactions efficiently
- **Logging**: Reports number of duplicates found and removed

To disable: Set `tiller_history_source.enabled: false` in config.

## Command Line Options

```bash
python src/main.py --help

Options:
  --input-dir DIR     Directory containing bank CSV files (required)
  --config FILE       Configuration file path (default: config/config.yaml)
  --verbose, -v       Enable verbose logging
  --dry-run          Validate files without processing
```

## Examples

### Basic Usage
```bash
python src/main.py --input-dir ./bank_exports
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

## Data Processing Flow

1. **Source Data Loading**: Load bank CSV files according to source schema
2. **Row Filtering**: Apply filters (e.g., exclude balance rows, include only transactions)
3. **Source Transformation**: Convert to intermediate format with:
   - Date format standardization
   - Amount sign calculation (debit/credit)
   - IBAN anonymization
   - String cleaning
4. **Target Transformation**: Convert to Tiller format with:
   - Date format conversion (DD.MM.YYYY → M/D/YYYY)
   - Month/week calculations
   - Transaction ID generation
   - Field mapping to Tiller columns
5. **Deduplication** (new): Check Transaction IDs against existing Tiller data, exclude duplicates
6. **Output Generation**: Save to files and/or display in console

## Supported Banks

Currently supported:
- **Swedbank Estonia**: Full support with schema and mappings

## Adding New Banks

To add support for a new bank:

1. **Create Source Schema**: Add `schemas/newbank_source.yaml` defining the CSV structure
2. **Create Mapping Rules**: Add `mappings/newbank_to_intermediate.yaml` with transformation rules
3. **Update Configuration**: Add bank to `source_converters` in `config/config.yaml`

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

## Adding New Target Systems

To add support for a new target system (beyond Tiller):

1. **Create Target Schema**: Add `schemas/newsystem_target.yaml`
2. **Create Mapping Rules**: Add `mappings/intermediate_to_newsystem.yaml`
3. **Create Converter Class**: Implement converter in `src/converters/newsystem_converter.py`
4. **Update Pipeline**: Modify main script to support the new target

## Troubleshooting

### Common Issues

**Google Sheets Access Errors** (new)
```bash
# Verify credentials file
cat config/google-service-account.json | python -m json.tool

# Check spreadsheet ID and service account permissions
```

**Deduplication Not Working** (new)
```bash
# Check if enabled
grep "tiller_history_source" config/config.yaml

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
2. **Add Tests**: Include unit tests for new converters (future enhancement)
3. **Update Documentation**: Add new bank/system support to this README
4. **Logging**: Use the provided logging infrastructure consistently

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