# src/converters/citadele_source_converter.py
"""
Citadele bank source CSV converter.
"""

import io
import re
from typing import Any, Dict, Tuple

import pandas as pd

from converters.generic_source_converter import GenericSourceConverter


class CitadeleSourceConverter(GenericSourceConverter):
    """
    Source converter for Citadele bank CSV exports.

    Extends GenericSourceConverter with:
    - extract_header: reads IBAN and currency from the 3-row file metadata prefix
    - post_process: extracts OtherAccountName and cleans Description from Narrative
    """

    _TRANSFER_TYPES = frozenset({"INWARD TRANSFER", "OUTWARD TRANSFER", "INWARD INSTANT PAYMENT"})

    _IBAN_RE = re.compile(r'\b[A-Z]{2}\d{2}[A-Z0-9]{10,}\b')
    # BIC/SWIFT: 4 letters + EE at positions 4-5 + 2 alphanum + optional 3 alphanum (8-11 chars total)
    _BIC_RE = re.compile(r'\b[A-Z]{4}EE[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b')
    # Estonian personal/registration code: exactly 11 consecutive digits
    _ISIKUKOOD_RE = re.compile(r'\b\d{11}\b')
    _END_TO_END_RE = re.compile(r'\s*End to end ID:.*$', re.IGNORECASE)
    _MCC_RE = re.compile(r'\bMCC-\d+\b')
    _REF_RE = re.compile(r'\bREF:\s*\d+\b')
    # Masked card: NNNNNN******NNNN
    _MASKED_CARD_RE = re.compile(r'\b\d{6}\*{6}\d{4}\b')
    # Purchase card date at start of narrative: DD/MM/YYYY
    _CARD_DATE_RE = re.compile(r'^(\d{2}/\d{2}/\d{4})\s*')

    def extract_header(self, file_content: io.BytesIO) -> Dict[str, Any]:
        """
        Extract IBAN and currency from line 0 of the Citadele export file.

        Row 0 format: "Account"|"EUR EE52XXXXXXXXXXXX"
        Returns {"AccountIBAN": "<iban>", "Currency": "<currency>"}.
        These become virtual columns injected into the DataFrame before field mapping.
        """
        file_content.seek(0)
        try:
            first_line = file_content.readline().decode('utf-8').strip()
        finally:
            file_content.seek(0)

        delimiter = self.source_schema.get('file_details', {}).get('delimiter', '|')
        parts = first_line.split(delimiter)
        if len(parts) < 2:
            self.logger.warning("Citadele header row has fewer than 2 columns; skipping IBAN/currency extraction")
            return {}

        cell = parts[1].strip().strip('"')
        tokens = cell.split()
        if len(tokens) < 2:
            self.logger.warning(f"Citadele header cell has unexpected format: '{cell}'")
            return {}

        return {"Currency": tokens[0], "AccountIBAN": tokens[-1]}

    def post_process(self, intermediate_df: pd.DataFrame, source_df: pd.DataFrame) -> pd.DataFrame:
        """
        Populate OtherAccountName and refine Description for each row.

        Reads the Type column from source_df (not mapped to intermediate) to
        distinguish PURCHASE rows from transfer rows.
        """
        result = intermediate_df.copy()

        for idx in result.index:
            row_type = str(source_df.at[idx, 'Type']).strip()
            description = str(result.at[idx, 'Description'])

            if row_type == 'PURCHASE':
                desc, name, card_date = self._process_purchase(description)
                if card_date:
                    result.at[idx, 'TransactionDate'] = card_date
            elif row_type in self._TRANSFER_TYPES:
                desc, name = self._process_transfer(description)
            else:
                continue

            result.at[idx, 'Description'] = desc
            result.at[idx, 'OtherAccountName'] = name

        # Suffix duplicate TransactionIDs with -1, -2, ... to ensure uniqueness.
        # Bank Reference can collide for same-date bank-internal entries (e.g. CREDIT INTEREST + WITHHOLDING TAX).
        dupes_mask = result.duplicated('TransactionID', keep=False)
        for tid, group in result[dupes_mask].groupby('TransactionID'):
            for i, idx in enumerate(group.index, start=1):
                result.at[idx, 'TransactionID'] = f"{tid}-{i}"

        return result

    def _process_transfer(self, text: str) -> Tuple[str, str]:
        """Strip PII/routing tokens from a transfer narrative; extract counterparty name."""
        text = self._END_TO_END_RE.sub('', text).strip()
        text = self._IBAN_RE.sub('', text).strip()
        text = self._BIC_RE.sub('', text).strip()
        text = self._ISIKUKOOD_RE.sub('', text).strip()
        text = re.sub(r'\s+', ' ', text).strip()

        words = text.split()
        if len(words) >= 2:
            name = ' '.join(words[-2:])
            description = ' '.join(words[:-2]).strip()
        else:
            name = text
            description = ''

        return description, name

    def _process_purchase(self, text: str) -> Tuple[str, str, str]:
        """Strip card metadata tokens from a purchase narrative; extract merchant name and card date.

        Returns (description, name, card_date) where card_date is DD.MM.YYYY or '' if not found.
        """
        text = self._END_TO_END_RE.sub('', text).strip()

        card_date = ''
        m = self._CARD_DATE_RE.match(text)
        if m:
            card_date = m.group(1).replace('/', '.')
            text = text[m.end():]

        text = self._MASKED_CARD_RE.sub('', text).strip()
        text = self._MCC_RE.sub('', text).strip()
        text = self._REF_RE.sub('', text).strip()
        text = re.sub(r'\s+', ' ', text).strip()

        name = text
        return name, name, card_date
