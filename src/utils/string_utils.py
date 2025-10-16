# src/utils/string_utils.py
"""
String utility functions for the ETL pipeline.
"""

import logging
import re
from typing import Optional, List

import pandas as pd


def clean_string(text: str, remove_leading_apostrophe: bool = True,
                 strip_whitespace: bool = True) -> str:
    """
    Clean string according to specified rules.

    Args:
        text: Text to clean
        remove_leading_apostrophe: Whether to remove leading apostrophe
        strip_whitespace: Whether to strip whitespace

    Returns:
        Cleaned string
    """
    if pd.isna(text) or text is None:
        return ""

    text = str(text)

    if strip_whitespace:
        text = text.strip()

    if remove_leading_apostrophe and text.startswith("'"):
        text = text[1:]

    return text


def anonymize_iban(iban: str, country_length: int = 2, keep_last_digits: int = 5,
                   mask_char: str = "*", mask_count: int = 3) -> str:
    """
    Anonymize IBAN by keeping country prefix and last digits.

    Args:
        iban: IBAN string to anonymize
        country_length: Number of country prefix characters to keep
        keep_last_digits: Number of last digits to keep
        mask_char: Character to use for masking
        mask_count: Number of mask characters to use

    Returns:
        Anonymized IBAN
    """
    if pd.isna(iban) or not iban:
        return ""

    iban_clean = str(iban).strip().replace(" ", "")

    # Validate IBAN length (basic check)
    if len(iban_clean) < country_length + keep_last_digits:
        # Not a standard IBAN, return masked for safety or original based on policy
        return f"{iban_clean[:country_length]}{mask_char * mask_count}" if len(iban_clean) >= country_length else f"{mask_char * mask_count}"

    prefix = iban_clean[:country_length]
    suffix = iban_clean[-keep_last_digits:]
    masked_middle = mask_char * mask_count

    return f"{prefix}{masked_middle}{suffix}"


def convert_decimal_separator(amount_str: str, from_sep: str, to_sep: str) -> str:
    """
    Replace decimal separator in amount string.

    Args:
        amount_str: Amount string
        from_sep: Original separator (e.g., ',')
        to_sep: Target separator (e.g., '.')

    Returns:
        Amount string with replaced separator
    """
    if pd.isna(amount_str) or not amount_str:
        return ""
    return str(amount_str).replace(from_sep, to_sep)


def parse_amount(amount_str: str) -> Optional[float]:
    """
    Parse amount string to float.

    Args:
        amount_str: Amount string

    Returns:
        Parsed float or None if parsing fails
    """
    logger = logging.getLogger(__name__)
    if pd.isna(amount_str) or not amount_str:
        return None
    try:
        return float(amount_str)
    except ValueError as e:
        logger.warning(f"Failed to parse amount '{amount_str}': {e}")
        return None


def apply_amount_sign(amount: float, field_for_sign: str, debit_value: str, credit_value: str) -> float:
    """
    Apply sign to amount based on a debit/credit indicator field.

    Args:
        amount: Numeric amount
        field_for_sign: Value from the field determining sign (e.g., 'D' or 'K')
        debit_value: Value indicating a debit (expense)
        credit_value: Value indicating a credit (income)

    Returns:
        Signed amount
    """
    if pd.isna(amount):
        return 0.0 # Or raise error/handle as per policy

    if str(field_for_sign).strip().upper() == debit_value.upper():
        return -abs(amount)
    elif str(field_for_sign).strip().upper() == credit_value.upper():
        return abs(amount)
    else:
        # Default to positive if no clear debit/credit, or log warning
        logging.getLogger(__name__).warning(
            f"Unknown sign indicator '{field_for_sign}'. Amount {amount} treated as positive."
        )
        return abs(amount)


def prefix_string(text: str, prefix: str) -> str:
    """
    Adds a prefix to a string.

    Args:
        text: The original string.
        prefix: The string to add as a prefix.

    Returns:
        The prefixed string.
    """
    if pd.isna(text) or text is None:
        return prefix # Or "" depending on desired behavior for nulls, let's assume prefix even for nulls
    return f"{prefix}{text}"


def mask_sensitive_data(text: str, patterns: Optional[List[str]] = None) -> str:
    """
    Mask sensitive data in text using regex patterns.

    Args:
        text: Text to mask
        patterns: List of regex patterns to mask

    Returns:
        Text with sensitive data masked
    """
    if pd.isna(text) or not text:
        return ""

    if patterns is None:
        # Default patterns for common sensitive data
        patterns = [
            r'\b\d{11,}\b',  # Long numbers (could be account numbers)
            r'\b[A-Z]{2}\d{2}[A-Z0-9]{11,}\b',  # IBAN-like patterns
        ]

    masked_text = str(text)

    for pattern in patterns:
        masked_text = re.sub(pattern, '***', masked_text, flags=re.IGNORECASE)

    return masked_text


def validate_currency_code(currency: str) -> bool:
    """
    Validate currency code format.

    Args:
        currency: Currency code to validate

    Returns:
        True if valid currency code format
    """
    if pd.isna(currency) or not currency:
        return False

    currency = str(currency).strip().upper()

    # Basic validation: 3 letters
    return len(currency) == 3 and currency.isalpha()


def format_amount_for_display(amount: float, currency: str = "",
                              decimal_places: int = 2) -> str:
    """
    Format amount for display purposes.

    Args:
        amount: Amount to format
        currency: Currency code
        decimal_places: Number of decimal places

    Returns:
        Formatted amount string
    """
    if pd.isna(amount):
        return ""

    formatted = f"{amount:.{decimal_places}f}"

    if currency:
        return f"{formatted} {currency}"
    return formatted


SPLIT_SUFFIX_PATTERN = r'\[\d+\]$'
PREFIXES_TO_REMOVE = 'split:'

def normalize_tiller_transaction_id(transaction_id: str) -> str:
    if not isinstance(transaction_id, str):
        return ""

    normalized_id = transaction_id.strip()
    original_id = None

    while original_id != normalized_id:
        original_id = normalized_id
        for prefix in PREFIXES_TO_REMOVE:
            if normalized_id.lower().startswith(prefix):
                normalized_id = normalized_id[len(prefix):].strip()

    normalized_id = re.sub(SPLIT_SUFFIX_PATTERN, '', normalized_id).strip()

    return normalized_id