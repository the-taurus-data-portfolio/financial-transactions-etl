# Data Processing Specification for Bank to Tiller Integration

---

## 1. Introduction

This document specifies the process for automating the extraction, transformation, and loading (ETL) of financial transaction data from various bank statements into a format suitable for import into Tiller Money. The system includes Transaction ID-based reconciliation (deduplication) capabilities to prevent duplicate entries in the target financial management system. The goal is to provide a flexible and extensible system that can accommodate different bank formats and potentially other financial management software in the future.

---

## 2. Data Formats Overview

This section describes the three primary data formats involved in the process. Detailed schema definitions for each format are provided in dedicated YAML files.

### 2.1. Source Bank CSV (Format 1)

* **Description**: This is the raw CSV export provided by a specific bank. Each bank may have its own unique column names, delimiters, and data representations.
* **Schema File**: `schemas/<bank>_source.yaml` (e.g., `schemas/swedbank_source.yaml`)
    * *Purpose*: Defines the structure, field names, and data types of the input CSV from the bank. It includes original field names and their standardized aliases for easier reference.

### 2.2. Intermediate Transaction Format (Format 2)

* **Description**: A universal, standardized CSV format that serves as a common ground for all bank transaction data. Data from any source bank is first transformed into this format. This acts as a buffer, ensuring consistency before data is passed to any target system.
* **Schema File**: `schemas/intermediate.yaml`
    * *Purpose*: Defines the standardized structure, field names, and data types for all common transaction attributes (e.g., `TransactionDate`, `Amount`, `Description`).

### 2.3. Tiller Target Format (Format 3)

* **Description**: The specific spreadsheet-based format required for importing or copy-pasting transactions into Tiller Money. This format adheres to Tiller's expected column headers and data representations, including a unique **Transaction ID** field.
* **Schema File**: `schemas/tiller_target.yaml`
    * *Purpose*: Defines the structure, field names, and expected data types and formats for the output CSV, matching Tiller's transaction sheet columns.

---

## 3. Mapping Rules Overview

This section describes the transformation rules that dictate how data is converted between the defined formats. These rules are stored in separate YAML files for modularity and easy updates.

### 3.1. Mapping: Bank Source to Intermediate (`<bank>_to_intermediate`)

* **Description**: This set of rules specifies how data from a specific **Source Bank CSV** (e.g., `swedbank_source.yaml`) is to be processed, filtered, and transformed into the **Intermediate Transaction Format** (`intermediate.yaml`).
* **Rules File**: `mappings/<bank>_to_intermediate.yaml` (e.g., `mappings/swedbank_to_intermediate.yaml`)
    * *Key aspects covered*: Row filtering (e.g., excluding initial balance entries), data type conversions (e.g., string to float, decimal separator changes), string cleaning (e.g., apostrophe removal), and data anonymization (e.g., IBAN masking).

### 3.2. Mapping: Intermediate to Tiller Target (`intermediate_to_tiller`)

* **Description**: This set of rules specifies how data from the **Intermediate Transaction Format** (`intermediate.yaml`) is to be transformed and mapped to the columns required by the **Tiller Target Format** (`tiller_target.yaml`).
* **Rules File**: `mappings/intermediate_to_tiller.yaml`
    * *Key aspects covered*: Date format conversions, direct field copying, and derivation of specific Tiller-required fields (e.g., `Month`, `Week`, `Date Added`, `Transaction ID`). It also clarifies which Tiller fields are not directly mapped and are expected to be handled by Tiller itself.

---

## 4. Overall Processing Flow

The data processing involves a two-step transformation pipeline with integrated deduplication:

1.  **Input Data Reception**: The user provides a bank statement in its native CSV format (e.g., from an Estonian bank).
2.  **Transformation Step 1: Source to Intermediate**:
    * The raw bank CSV data is read and parsed according to the specifications in `schemas/<bank>_source.yaml`.
    * Rows are **filtered** based on criteria defined in `mappings/<bank>_to_intermediate.yaml` (e.g., only processing transaction rows).
    * Each relevant field is **transformed** (e.g., amount sign adjustment, IBAN anonymization, string cleaning) and mapped to its corresponding field in the Intermediate Transaction Format, as specified in `mappings/<bank>_to_intermediate.yaml`.
    * The output of this step is a DataFrame conforming to `schemas/intermediate.yaml`.
3.  **Transformation Step 2: Intermediate to Tiller Target**:
    * The data from the Intermediate Transaction Format is processed.
    * Fields are **transformed** (e.g., date format conversion) and **mapped** to the specific columns required by Tiller, as defined in `mappings/intermediate_to_tiller.yaml` and `schemas/tiller_target.yaml`.
    * A unique **Transaction ID** is generated for each transaction according to the mapping rules.
    * Fields not explicitly mapped in `intermediate_to_tiller.yaml` (e.g., `Category`, `Account ID`) are left empty in the generated output, as they are typically filled by Tiller's internal logic or user input.
4.  **Transaction ID Reconciliation (Deduplication)**:
    * Before finalizing the output, the system loads existing **Transaction IDs** from the specified Tiller Google Sheet.
    * Each newly transformed transaction's **Transaction ID** is checked against this exclusion set.
    * If a match is found, the transaction is **excluded** from the final output to prevent duplicates.
5.  **Output Generation**:
    * The deduplicated data, now in Tiller's expected format, is generated as a CSV file.
    * For a small number of transactions, it can also be output to the console for easy copy-pasting directly into the Tiller spreadsheet.

---

## 5. Transaction ID Reconciliation

### 5.1. Purpose

The Transaction ID Reconciliation mechanism prevents duplicate transactions from being added to Tiller by comparing the generated Transaction IDs of incoming transactions against existing IDs in the Tiller Google Sheet.

### 5.2. Implementation Requirements

* **Google Sheets Integration**: The system must use the Google Sheets API to securely access the Tiller spreadsheet in read-only mode.
* **Transaction ID Column**: The system loads only the "Transaction ID" column from the specified worksheet/table.
* **Exclusion Set**: Transaction IDs are stored in a Python `Set` data structure for O(1) lookup efficiency.
* **Simple Matching**: Deduplication is based solely on exact Transaction ID matching—no complex multi-field key generation or description cleaning is required.

### 5.3. Configuration

The deduplication feature is configured in `config/config.yaml` under the `tiller_history_source` section:

```yaml
tiller_history_source:
  enabled: true  # Set to false to disable deduplication
  spreadsheet_id: "your-tiller-spreadsheet-id"
  worksheet_title: "Transactions"  # Title of the worksheet
  table_name: "Table1"  # Name of the table within the sheet
  credentials_file: "config/google-service-account.json"
```

### 5.4. Processing Logic

1. **Initialization**: When `TillerConverter` is initialized, it checks if deduplication is enabled.
2. **Load Exclusion Set**: If enabled, it uses `GoogleSheetsReader` to load all Transaction IDs from the specified Tiller sheet into a Set.
3. **Transform Transactions**: Incoming transactions are transformed to Tiller format, including Transaction ID generation.
4. **Check for Duplicates**: For each transaction, the system checks if its Transaction ID exists in the exclusion set.
5. **Exclude Duplicates**: Transactions with matching IDs are filtered out from the final output.
6. **Logging**: The system logs the number of duplicates found and removed, along with sample details.

### 5.5. Why Transaction ID?

* **Simplicity**: Single-field comparison is straightforward and easy to maintain.
* **Performance**: Set lookup is O(1), making deduplication fast even with thousands of historical transactions.
* **Reliability**: Transaction ID is specifically designed to be unique per transaction in Tiller's data model.
* **Maintainability**: No complex cleaning rules or multi-field key generation logic to maintain.

---

## 6. Extending the System (Adding New Banks / Target Systems)

The modular design, leveraging separate YAML files for schemas and mappings, allows for easy extensibility:

* **To support a new bank (new data source)**:
    1.  Create a new schema file in the `schemas/` directory (e.g., `schemas/newbank_source.yaml`) to describe its unique CSV structure.
    2.  Create a new mapping file in the `mappings/` directory (e.g., `mappings/newbank_to_intermediate.yaml`) to define how this new bank's data maps to the `intermediate.yaml` schema.
    3.  Update `config/config.yaml` to add the new bank to the `source_converters` section.
* **To support a new financial management software (new target system)**:
    1.  Create a new schema file in the `schemas/` directory (e.g., `schemas/new_app_target.yaml`) to describe its required import format.
    2.  Create a new mapping file in the `mappings/` directory (e.g., `mappings/intermediate_to_new_app_target.yaml`) to define how the `intermediate.yaml` schema maps to the new target system's format.
    3.  Implement a new `TargetConverter` class following the interface pattern.

This approach ensures that the core processing logic remains stable, while allowing for flexible adaptation to evolving requirements.

---

## 7. Technical Implementation Details

This section outlines the core technical decisions for implementing the data processing pipeline.

### 7.1. Implementation Language

* **Python**: The entire ETL pipeline (parsing, transformation, deduplication, and output generation) is implemented using Python 3.8+.

### 7.2. Build Automation

* **Makefile**: The project uses a `Makefile` for automating common tasks such as setting up the environment, installing dependencies, running tests (if applicable), and executing the ETL process. This provides a consistent and reproducible way to manage the project workflow.

### 7.3. Environment Management

* **Virtual Environment (`virtualenv`)**: A dedicated Python virtual environment is used to manage project dependencies. This ensures that the project's dependencies are isolated from the system-wide Python installation and other projects, preventing conflicts.

### 7.4. Dependency Management

* **`requirements.txt`**: Project dependencies are managed using a `requirements.txt` file. This file lists all necessary Python packages and their versions, including:
    * `pandas`: For DataFrame operations and CSV processing
    * `PyYAML`: For configuration and schema file parsing
    * `python-dateutil`: For advanced date parsing capabilities
    * `gspread`: For Google Sheets API access
    * `google-api-python-client`: For Google API client library
    * `oauth2client`: For OAuth2 authentication

### 7.5. Configuration Management

* **Configuration YAML (`config.yaml`)**: A dedicated YAML file (`config/config.yaml`) is used to manage runtime configurations. This file specifies:
    * Logging settings
    * Output destinations and formats
    * Processing options
    * Tiller history source configuration for deduplication
    * Schema and mapping paths

### 7.6. Error Handling

* **Comprehensive Logging**: Error handling involves logging critical errors, warnings, and informational messages. The system provides immediate feedback on issues during processing through both console and file logging.

### 7.7. Logging

* **Python's `logging` module**: The standard Python `logging` module is used for all logging purposes.
    * **Output Destinations**: Logging is configured to output messages to both:
        * **Console**: For real-time feedback during execution.
        * **File**: For persistent records of processing activities, warnings, and errors. The log file path is configured in `config/config.yaml`.
    * **Levels**: Supports different logging levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) to control verbosity.
    * **Deduplication Logging**: Special attention is given to logging deduplication statistics, including number of duplicates found and sample details.

### 7.8. Extensibility and Interfaces

* **Abstract Base Classes (`abc` module)**: To ensure future extensibility and maintain a clear contract for different converters, Python's `abc` module is used to define abstract base classes (interfaces).
    * **`SourceConverter` Interface**: This interface defines the methods required for converting data from a specific bank's source format to the Intermediate Transaction Format. Each new bank implementation inherits from this interface.
    * **`TargetConverter` Interface**: This interface defines the methods required for converting data from the Intermediate Transaction Format to a specific target system's format (e.g., Tiller). Each new target system implementation inherits from this interface.
    * This approach promotes modularity, testability, and allows for easy integration of new data sources and targets without modifying core logic.

---

## 8. Architecture Principles

### 8.1. Current Architecture

The system follows a modular, interface-driven architecture:

* **Separation of Concerns**: Source conversion, target conversion, and deduplication are separate concerns with clear boundaries.
* **Dependency Injection**: Converters receive their dependencies (schema loaders, configurations) through constructor injection.
* **Configuration-Driven**: All behavior is controlled through YAML configuration files, not hardcoded values.
* **Two-Step Transformation**: The intermediate format serves as a universal adapter between sources and targets.

### 8.2. Code Style and Standards

* **Type Hints**: Python type hints are used throughout for better code documentation and IDE support.
* **Logging**: Consistent use of the `logging` module for all output and diagnostics.
* **DataFrames**: `pandas.DataFrame` is the primary data structure for all transformations.
* **YAML**: All schemas, mappings, and configurations use YAML format for human readability.
* **Error Handling**: Try-except blocks with appropriate logging at all integration points.

### 8.3. Future Extensibility

The architecture is designed to support future enhancements without major refactoring:

* **Direct Google Sheets Output**: The `TillerConverter` can be extended to write directly to Google Sheets by adding a new output method while keeping the transformation and deduplication logic unchanged.
* **Multiple Target Systems**: New target converters can be added by implementing the `TargetConverter` interface.
* **Advanced Deduplication**: The deduplication mechanism can be enhanced (e.g., fuzzy matching, ML-based matching) without changing the converter interface.
* **Batch Processing**: Large-scale processing can be added by implementing batch readers while maintaining the same transformation pipeline.

---

## 9. Google Sheets Integration Details

### 9.1. Authentication

* **Service Account**: Uses Google service account authentication for secure, automated access.
* **Credentials File**: JSON credentials file stored locally, referenced in configuration.
* **Minimal Permissions**: Service account only needs read access to the Tiller spreadsheet.

### 9.2. Data Access

* **Worksheet by Title**: Accesses worksheets by their title (e.g., "Transactions").
* **Table Support**: Can optionally specify a table name within the worksheet.
* **Efficient Loading**: Loads only the Transaction ID column to minimize data transfer and memory usage.

### 9.3. Error Handling

* **Connection Failures**: Gracefully handles network errors and authentication failures.
* **Missing Data**: Handles cases where worksheet or Transaction ID column doesn't exist.
* **Fallback**: If deduplication setup fails, the system continues without deduplication and logs a warning.

---

## 10. Performance Characteristics

* **Transformation Speed**: ~1,000 transactions per second on typical hardware
* **Deduplication Speed**: O(1) set lookup, ~100,000 comparisons per second
* **Memory Usage**: Proportional to input file size; typical usage is ~100MB per 10,000 transactions
* **Network Overhead**: Single Google Sheets API call per execution for loading Transaction IDs
* **Scalability**: Tested with files up to 100MB and 50,000 transactions

---

## 11. Security Considerations

* **Local Processing**: All transaction data is processed locally
* **API Credentials**: Service account credentials stored locally, not in code
* **Read-Only Access**: Google Sheets access is read-only for deduplication
* **Data Anonymization**: IBAN and other sensitive data can be masked during transformation
* **Audit Trail**: Complete processing history in log files

---

## 12. Glossary

* **Source Format**: The original CSV export from a bank
* **Intermediate Format**: Universal standardized format for all bank data
* **Target Format**: The specific format required by Tiller or another financial system
* **Transaction ID**: Unique identifier for each transaction in Tiller format
* **Exclusion Set**: Set of existing Transaction IDs used for deduplication
* **Reconciliation**: The process of matching new transactions against existing ones to prevent duplicates
* **Service Account**: Google Cloud service account used for API authentication
* **Worksheet**: Individual sheet/tab within a Google Sheets spreadsheet
* **Table**: Named table within a worksheet (optional, used in Excel-like structures)