# Comprehensive Task Specification for Tiller ETL Pipeline Enhancement (Transaction ID Reconciliation & Config Fix)

**Objective:** Fully integrate a robust **deduplication (reconciliation) mechanism** into the `TillerConverter`. This mechanism must prevent duplicate transactions by comparing the generated **Transaction ID** of incoming transactions against a set of existing IDs fetched from the Tiller Google Sheet. Additionally, ensure the configuration section is streamlined and correctly named for fetching data by sheet/table title rather than relying on named ranges or complex cleaning rules.

**Current Architecture Context:** The project utilizes a modular, two-step transformation (`Source → Intermediate → Tiller Target`). Architectural and coding standards are defined in `specification.md`.

---

## 1. Core Component and Dependencies

1.  **Dependencies:** Ensure necessary libraries for Google Sheets API access (e.g., `gspread`, `google-api-python-client`) are included in **`requirements.txt`**.
2.  **Configuration:** **Update `config/config.yaml` to use the streamlined structure below.** The fields must be named precisely as follows:
    ```yaml
    # Tiller history source configuration for deduplication
    tiller_history_source:
      enabled: true  # Set to false to disable deduplication
      spreadsheet_id: "your-tiller-spreadsheet-id-here"
      worksheet_title: "Transactions"  # The title of the worksheet containing the table (e.g., 'Transactions')
      table_name: "Table1"  # The name of the table within the sheet (can be renamed)
      credentials_file: "config/google-service-account.json"
    ```
3.  **Utility Implementation:** Create a new file, **`src/utils/google_sheets_reader.py`**, to securely connect to the Sheets API and specifically load **only the "Transaction ID" column** from the named table (`Table1` on the `Transactions` worksheet) into an efficient data structure (a Set) for quick lookups.

---

## 2. TillerConverter Enhancement (Transaction ID Reconciliation)

Modify **`src/converters/tiller_converter.py`** to implement the following:

1.  **Load Exclusion Set:**
    * Upon initialization, the `TillerConverter` must use the new utility to load **only the "Transaction ID" column** from the specified Tiller table.
    * Store these historical IDs in a **Set** (`exclusion_set`) for O(1) lookup efficiency.
    * ***Note: All previous complex logic for date filtering, description cleaning, and multi-field key generation is now obsolete and must be excluded. The reconciliation is strictly based on the unique Transaction ID field.***
2.  **Deduplication:**
    * Modify the main processing method. For each incoming transaction from the Intermediate Format, extract its generated value for the **"Transaction ID"** field.
    * **Exclusion Rule:** If the incoming transaction's **Transaction ID** is found in the `exclusion_set`, the transaction **must be skipped and excluded** from the final Tiller Target output DataFrame.

---

## 3. Documentation and Design Specification Updates

1.  **Update `README.md`:**
    * Update the **Features** section to highlight the new **"Tiller Reconciliation (Deduplication)"** capability, specifically noting that it uses the **Transaction ID** for precise matching.
    * Detail the required configuration in the **Quick Start** section, using the new fields (`worksheet_title`, `table_name`) from the configuration block above.
2.  **Update `specification.md`:**
    * **Add a new section (e.g., "Transaction ID Reconciliation")** detailing the new, simplified deduplication requirement: fetching only the "Transaction ID" column from the specified Tiller table/worksheet.
    * Explicitly state that **`specification.md`** serves as the primary document for:
        * **Current Architecture:** Detailing the use of `SourceConverter` and `TargetConverter` interfaces.
        * **Code Style and Standards:** Reiterating the use of Python's `logging` module and `pandas` DataFrames.

---

## 4. Future Design Considerations (Extensibility)

The project design must maintain modularity, adhering to the `TargetConverter` interface. The `TillerConverter` should be structured to allow the final **output mechanism to be easily swapped out** in a future phase. This means preparing the code to allow for a transition from the current CSV file output to **direct writing/appending of new transactions to the target Google Sheet** via the Sheets API, without requiring significant refactoring of the preceding reconciliation logic.

---

## 5. Deliverables

Provide the complete code for the following updated/new files:

-   `requirements.txt`
-   `config/config.yaml` (Updated with the new streamlined section)
-   **`README.md` (Updated)**
-   **`specification.md` (Updated)**
-   `src/converters/tiller_converter.py`
-   `src/utils/google_sheets_reader.py` (New utility focusing on ID retrieval)
-   `src/utils/string_utils.py` (Ensure complex cleaning logic is NOT included)