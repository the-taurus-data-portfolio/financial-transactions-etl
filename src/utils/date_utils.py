"""
Date utility functions for the ETL pipeline.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Union
import pandas as pd


def parse_date(date_str: str, source_format: str) -> Optional[datetime]:
    """
    Parse date string according to source format.

    Args:
        date_str: Date string to parse
        source_format: Source date format (e.g., "DD.MM.YYYY")

    Returns:
        Parsed datetime object or None if parsing fails
    """
    logger = logging.getLogger(__name__)

    if not date_str or pd.isna(date_str):
        return None

    # Convert format specification to strptime format
    format_mapping = {
        'DD.MM.YYYY': '%d.%m.%Y',
        'M/D/YYYY': '%m/%d/%Y',
        'M/D/YY': '%m/%d/%y',
        'YYYY-MM-DD': '%Y-%m-%d',
        'DD/MM/YYYY': '%d/%m/%Y'
    }

    strptime_format = format_mapping.get(source_format)
    if not strptime_format:
        logger.warning(f"Unknown date format: {source_format}")
        return None

    try:
        return datetime.strptime(str(date_str).strip(), strptime_format)
    except ValueError as e:
        logger.warning(f"Failed to parse date '{date_str}' with format '{source_format}': {e}")
        return None


def format_date(date_obj: datetime, target_format: str) -> str:
    """
    Format datetime object according to target format.

    Args:
        date_obj: Datetime object to format
        target_format: Target date format (e.g., "M/D/YYYY")

    Returns:
        Formatted date string
    """
    if not date_obj:
        return ""

    # Convert format specification to strftime format
    format_mapping = {
        'DD.MM.YYYY': '%d.%m.%Y',
        'M/D/YYYY': '%-m/%-d/%Y' if hasattr(datetime, 'strftime') else '%m/%d/%Y',
        'M/D/YY': '%-m/%-d/%y' if hasattr(datetime, 'strftime') else '%m/%d/%y',
        'YYYY-MM-DD': '%Y-%m-%d',
        'DD/MM/YYYY': '%d/%m/%Y'
    }

    strftime_format = format_mapping.get(target_format, target_format)

    try:
        formatted = date_obj.strftime(strftime_format)
        # Remove leading zeros for M/D formats if platform doesn't support %-
        if target_format in ['M/D/YYYY', 'M/D/YY']:
            parts = formatted.split('/')
            if len(parts) >= 2:
                parts[0] = str(int(parts[0]))  # Remove leading zero from month
                parts[1] = str(int(parts[1]))  # Remove leading zero from day
                formatted = '/'.join(parts)
        return formatted
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to format date {date_obj} with format '{target_format}': {e}")
        return str(date_obj.date())


def convert_date_format(date_str: str, source_format: str, target_format: str) -> str:
    """
    Convert date string from source format to target format.

    Args:
        date_str: Date string to convert
        source_format: Source date format
        target_format: Target date format

    Returns:
        Converted date string
    """
    parsed_date = parse_date(date_str, source_format)
    if parsed_date:
        return format_date(parsed_date, target_format)
    return ""


def get_month_start(date_obj: datetime) -> datetime:
    """
    Get the first day of the month for given date.

    Args:
        date_obj: Input date

    Returns:
        First day of the month
    """
    return date_obj.replace(day=1)


def get_week_start(date_obj: datetime, start_of_week: str = "Sunday") -> datetime:
    """
    Get the first day of the week for given date.

    Args:
        date_obj: Input date
        start_of_week: "Sunday" or "Monday"

    Returns:
        First day of the week
    """
    days_since_start = date_obj.weekday()

    if start_of_week.lower() == "sunday":
        # Sunday = 6, Monday = 0, etc.
        days_since_start = (date_obj.weekday() + 1) % 7

    return date_obj - timedelta(days=days_since_start)


def date_to_month_start(date_str: str, source_format: str, target_format: str) -> str:
    """
    Convert date to first day of month in target format.

    Args:
        date_str: Date string to convert
        source_format: Source date format
        target_format: Target date format

    Returns:
        First day of month in target format
    """
    parsed_date = parse_date(date_str, source_format)
    if parsed_date:
        month_start = get_month_start(parsed_date)
        return format_date(month_start, target_format)
    return ""


def date_to_week_start(date_str: str, source_format: str, target_format: str,
                       start_of_week: str = "Sunday") -> str:
    """
    Convert date to first day of week in target format.

    Args:
        date_str: Date string to convert
        source_format: Source date format
        target_format: Target date format
        start_of_week: "Sunday" or "Monday"

    Returns:
        First day of week in target format
    """
    parsed_date = parse_date(date_str, source_format)
    if parsed_date:
        week_start = get_week_start(parsed_date, start_of_week)
        return format_date(week_start, target_format)
    return ""


def get_current_date(target_format: str) -> str:
    """
    Get current date in target format.

    Args:
        target_format: Target date format

    Returns:
        Current date in target format
    """
    return format_date(datetime.now(), target_format)


def validate_date_range(date_obj: datetime, min_year: int = 1900, max_year: int = 2100) -> bool:
    """
    Validate that date is within reasonable range.

    Args:
        date_obj: Date to validate
        min_year: Minimum allowed year
        max_year: Maximum allowed year

    Returns:
        True if date is valid, False otherwise
    """
    if not date_obj:
        return False

    return min_year <= date_obj.year <= max_year


def is_future_date(date_obj: datetime, buffer_days: int = 1) -> bool:
    """
    Check if date is in the future (with optional buffer).

    Args:
        date_obj: Date to check
        buffer_days: Number of days buffer to allow

    Returns:
        True if date is in the future beyond buffer
    """
    if not date_obj:
        return False

    today = datetime.now().date()
    check_date = date_obj.date()

    return check_date > today + timedelta(days=buffer_days)