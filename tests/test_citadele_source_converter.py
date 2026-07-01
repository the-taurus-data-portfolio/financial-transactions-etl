"""
Unit tests for CitadeleSourceConverter.

All external dependencies (schema_loader, file I/O) are mocked.
Tests cover: extract_header, post_process (transfers + purchases),
direct_float transformation, not_empty row filter.
"""

import io
from unittest.mock import MagicMock

import pandas as pd
import pytest

from converters.citadele_source_converter import CitadeleSourceConverter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INTERMEDIATE_FIELDS = [
    'TransactionDate', 'Amount', 'Currency', 'Description',
    'BudgetAccountNumber', 'OtherAccountName', 'TransactionID',
]

_CITADELE_SCHEMA = {
    'file_details': {'delimiter': '|', 'encoding': 'utf-8', 'skip_header_rows': 3},
    'fields': [
        {'name': 'Date', 'required': True},
        {'name': 'Type', 'required': False},
        {'name': 'Narrative', 'required': False},
        {'name': 'Payment No.', 'required': False},
        {'name': 'Bank Reference', 'required': False},
        {'name': 'Reference number', 'required': False},
        {'name': 'Amount DR/Amount CR', 'required': True},
    ],
}

_INTERMEDIATE_SCHEMA = {
    'fields': [{'name': f} for f in _INTERMEDIATE_FIELDS],
}


def _make_converter() -> CitadeleSourceConverter:
    schema_loader = MagicMock()
    schema_loader.load_schema.side_effect = (
        lambda name: _CITADELE_SCHEMA if 'citadele' in name else _INTERMEDIATE_SCHEMA
    )
    schema_loader.load_mapping.return_value = {'filters': [], 'field_mappings': []}
    return CitadeleSourceConverter(
        schema_loader=schema_loader,
        bank_type='citadele',
        source_schema_name='citadele_source.yaml',
        mapping_rules_name='citadele_to_intermediate.yaml',
    )


def _intermediate_row(description: str, other_account_name: str = '') -> pd.DataFrame:
    """Build a single-row intermediate DataFrame for post_process tests."""
    return pd.DataFrame(
        [{
            'TransactionDate': '01.06.2026',
            'Amount': -10.0,
            'Currency': 'EUR',
            'Description': description,
            'BudgetAccountNumber': 'EE***00001',
            'OtherAccountName': other_account_name,
            'TransactionID': 'CT00000001',
        }],
        index=[0],
    )


# ---------------------------------------------------------------------------
# extract_header
# ---------------------------------------------------------------------------

class TestExtractHeader:
    def test_parses_currency_and_iban(self):
        converter = _make_converter()
        content = b'"Account"|"EUR EE521234567890"\n'
        result = converter.extract_header(io.BytesIO(content))
        assert result['Currency'] == 'EUR'
        assert result['AccountIBAN'] == 'EE521234567890'

    def test_resets_file_position_after_read(self):
        converter = _make_converter()
        buf = io.BytesIO(b'"Account"|"EUR EE521234567890"\n')
        buf.read()  # advance past the start
        converter.extract_header(buf)
        assert buf.tell() == 0

    def test_returns_empty_dict_when_only_one_column(self):
        converter = _make_converter()
        result = converter.extract_header(io.BytesIO(b'single_column\n'))
        assert result == {}

    def test_returns_empty_dict_when_cell_has_one_token(self):
        converter = _make_converter()
        result = converter.extract_header(io.BytesIO(b'"Account"|"ONLYONETOKEN"\n'))
        assert result == {}


# ---------------------------------------------------------------------------
# post_process — transfer rows
# ---------------------------------------------------------------------------

class TestPostProcessTransfer:
    def test_outward_transfer_extracts_name_and_cleans_description(self):
        converter = _make_converter()
        narrative = (
            'OUTWARD TRANSFER JANE SMITH 38000000001 HABAEE2X '
            'EE000000000000000001 End to end ID: NOTPROVIDED'
        )
        source_df = pd.DataFrame({'Type': ['OUTWARD TRANSFER']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'OtherAccountName'] == 'JANE SMITH'
        assert result.at[0, 'Description'] == 'OUTWARD TRANSFER'

    def test_inward_instant_payment_extracts_name_and_cleans_description(self):
        converter = _make_converter()
        narrative = (
            'INWARD INSTANT PAYMENT JOHN DOE 37000000002 HABAEE2X '
            'EE000000000000000002'
        )
        source_df = pd.DataFrame({'Type': ['INWARD INSTANT PAYMENT']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'OtherAccountName'] == 'JOHN DOE'
        assert result.at[0, 'Description'] == 'INWARD INSTANT PAYMENT'

    def test_inward_transfer_extracts_name(self):
        converter = _make_converter()
        narrative = (
            'INWARD TRANSFER ALICE BROWN 49000000003 HABAEE2X '
            'EE000000000000000003 End to end ID: NOTPROVIDED'
        )
        source_df = pd.DataFrame({'Type': ['INWARD TRANSFER']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'OtherAccountName'] == 'ALICE BROWN'

    def test_strips_end_to_end_id(self):
        converter = _make_converter()
        narrative = 'OUTWARD TRANSFER BOB LEE 38000000004 HABAEE2X EE000000000000000004 End to end ID: ABC123'
        source_df = pd.DataFrame({'Type': ['OUTWARD TRANSFER']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert 'End to end ID' not in result.at[0, 'Description']
        assert 'End to end ID' not in result.at[0, 'OtherAccountName']

    def test_does_not_modify_unknown_type(self):
        converter = _make_converter()
        narrative = 'SOME UNKNOWN NARRATIVE'
        source_df = pd.DataFrame({'Type': ['FEE']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'Description'] == narrative
        assert result.at[0, 'OtherAccountName'] == ''

    def test_three_word_org_name_extracts_last_two_words(self):
        # known limitation: only last 2 words become OtherAccountName; first word stays in Description
        converter = _make_converter()
        narrative = 'OUTWARD TRANSFER ACME CORP LTD 38000000001 HABAEE2X EE000000000000000001'
        source_df = pd.DataFrame({'Type': ['OUTWARD TRANSFER']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'OtherAccountName'] == 'CORP LTD'
        assert 'ACME' in result.at[0, 'Description']


# ---------------------------------------------------------------------------
# post_process — purchase rows
# ---------------------------------------------------------------------------

class TestPostProcessPurchase:
    def test_extracts_card_date_and_merchant(self):
        converter = _make_converter()
        narrative = (
            '15/06/2026 123456******7890 MCC-5411 REF: 9999999 '
            'SAMPLE GROCERY TALLINN EE HABAEE2X'
        )
        source_df = pd.DataFrame({'Type': ['PURCHASE']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'Description'].startswith('15/06/2026:')
        assert 'SAMPLE GROCERY' in result.at[0, 'OtherAccountName']

    def test_strips_masked_card_number(self):
        converter = _make_converter()
        narrative = '20/06/2026 123456******7890 MCC-1234 REF: 1111 MERCHANT NAME'
        source_df = pd.DataFrame({'Type': ['PURCHASE']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert '******' not in result.at[0, 'OtherAccountName']
        assert '******' not in result.at[0, 'Description']

    def test_strips_mcc_and_ref(self):
        converter = _make_converter()
        narrative = '01/01/2026 111111******2222 MCC-9999 REF: 88888 MY SHOP'
        source_df = pd.DataFrame({'Type': ['PURCHASE']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert 'MCC-' not in result.at[0, 'OtherAccountName']
        assert 'REF:' not in result.at[0, 'OtherAccountName']
        assert result.at[0, 'OtherAccountName'] == 'MY SHOP'

    def test_description_format_is_date_colon_merchant(self):
        converter = _make_converter()
        narrative = '25/12/2025 000000******9999 MCC-5812 REF: 12345 RESTAURANT ABC'
        source_df = pd.DataFrame({'Type': ['PURCHASE']}, index=[0])
        result = converter.post_process(_intermediate_row(narrative), source_df)

        assert result.at[0, 'Description'] == '25/12/2025: RESTAURANT ABC'


# ---------------------------------------------------------------------------
# direct_float transformation
# ---------------------------------------------------------------------------

class TestDirectFloat:
    def test_positive_decimal_string(self):
        converter = _make_converter()
        series = pd.Series(['100.00'])
        result = converter._apply_transformation(series, {'type': 'direct_float'}, pd.DataFrame())
        assert result.iloc[0] == pytest.approx(100.0)

    def test_negative_decimal_string(self):
        converter = _make_converter()
        series = pd.Series(['-7.20'])
        result = converter._apply_transformation(series, {'type': 'direct_float'}, pd.DataFrame())
        assert result.iloc[0] == pytest.approx(-7.20)

    def test_zero(self):
        converter = _make_converter()
        series = pd.Series(['0.00'])
        result = converter._apply_transformation(series, {'type': 'direct_float'}, pd.DataFrame())
        assert result.iloc[0] == pytest.approx(0.0)

    def test_empty_string_returns_none(self):
        converter = _make_converter()
        series = pd.Series([''])
        result = converter._apply_transformation(series, {'type': 'direct_float'}, pd.DataFrame())
        assert result.iloc[0] is None


# ---------------------------------------------------------------------------
# not_empty filter
# ---------------------------------------------------------------------------

class TestNotEmptyFilter:
    def _converter_with_not_empty_filter(self) -> CitadeleSourceConverter:
        converter = _make_converter()
        converter.mapping_rules = {
            'filters': [{'field': 'Date', 'operator': 'not_empty'}]
        }
        return converter

    def test_removes_empty_string_rows(self):
        converter = self._converter_with_not_empty_filter()
        df = pd.DataFrame({'Date': ['01.06.2026', '', '30.06.2026']})
        result = converter.filter_rows(df)
        assert list(result['Date']) == ['01.06.2026', '30.06.2026']

    def test_removes_whitespace_only_rows(self):
        converter = self._converter_with_not_empty_filter()
        df = pd.DataFrame({'Date': ['01.06.2026', '   ', '30.06.2026']})
        result = converter.filter_rows(df)
        assert list(result['Date']) == ['01.06.2026', '30.06.2026']

    def test_keeps_all_rows_when_no_empty_dates(self):
        converter = self._converter_with_not_empty_filter()
        df = pd.DataFrame({'Date': ['01.06.2026', '15.06.2026', '30.06.2026']})
        result = converter.filter_rows(df)
        assert len(result) == 3

    def test_removes_all_rows_when_all_dates_empty(self):
        converter = self._converter_with_not_empty_filter()
        df = pd.DataFrame({'Date': ['', '', '']})
        result = converter.filter_rows(df)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# post_process — duplicate TransactionID deduplication
# ---------------------------------------------------------------------------

class TestPostProcessDuplicateTransactionID:
    def test_suffixes_duplicate_transaction_ids(self):
        """CREDIT INTEREST + WITHHOLDING TAX sharing the same Bank Reference get -1/-2 suffixes."""
        converter = _make_converter()
        shared_id = 'CT60100000873757-20260630'
        intermediate_df = pd.DataFrame(
            [
                {
                    'TransactionDate': '30.06.2026', 'Amount': 0.79, 'Currency': 'EUR',
                    'Description': 'Value Date: 01.07.2026', 'BudgetAccountNumber': 'EE***14497',
                    'OtherAccountName': '', 'TransactionID': shared_id,
                },
                {
                    'TransactionDate': '30.06.2026', 'Amount': -0.17, 'Currency': 'EUR',
                    'Description': 'Value Date: 01.07.2026', 'BudgetAccountNumber': 'EE***14497',
                    'OtherAccountName': '', 'TransactionID': shared_id,
                },
            ],
            index=[0, 1],
        )
        source_df = pd.DataFrame({'Type': ['CREDIT INTEREST', 'WITHHOLDING TAX']}, index=[0, 1])
        result = converter.post_process(intermediate_df, source_df)

        assert result.at[0, 'TransactionID'] == f'{shared_id}-1'
        assert result.at[1, 'TransactionID'] == f'{shared_id}-2'

    def test_unique_transaction_ids_are_not_modified(self):
        converter = _make_converter()
        intermediate_df = pd.DataFrame(
            [
                {
                    'TransactionDate': '01.06.2026', 'Amount': -10.0, 'Currency': 'EUR',
                    'Description': 'PURCHASE', 'BudgetAccountNumber': 'EE***14497',
                    'OtherAccountName': '', 'TransactionID': 'CT00000001',
                },
                {
                    'TransactionDate': '02.06.2026', 'Amount': -20.0, 'Currency': 'EUR',
                    'Description': 'PURCHASE', 'BudgetAccountNumber': 'EE***14497',
                    'OtherAccountName': '', 'TransactionID': 'CT00000002',
                },
            ],
            index=[0, 1],
        )
        source_df = pd.DataFrame({'Type': ['PURCHASE', 'PURCHASE']}, index=[0, 1])
        result = converter.post_process(intermediate_df, source_df)

        assert result.at[0, 'TransactionID'] == 'CT00000001'
        assert result.at[1, 'TransactionID'] == 'CT00000002'
