"""
Unit tests for bank detection with skip_rows support.

Covers: csv_utils.read_csv_header(skip_rows=N) and
BankDetector detection of files with header metadata rows (e.g. Citadele).
"""

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from converters.bank_detector import BankDetector
from utils.csv_utils import read_csv_header

_PROJECT_ROOT = Path(__file__).parent.parent
_CITADELE_SAMPLE = str(_PROJECT_ROOT / 'data/samples/transactions/citadele_sample_ee.csv')
_LUMINOR_SAMPLE = str(_PROJECT_ROOT / 'data/samples/transactions/luminor_sample_ee.csv')

# Synthetic Citadele real-file content: 3 metadata rows + column headers + one data row
_CITADELE_REAL_CONTENT = (
    b'"Account"|"EUR EE000000000000000001"\n'
    b'"From"|"01.06.2026"|"to"|"30.06.2026"\n'
    b'|||||"Opening balance:"|"0.00"\n'
    b'"Date"|"Type"|"Narrative"|"Payment No."|"Bank Reference"|"Reference number"|"Amount DR/Amount CR"\n'
    b'"01.06.2026"|"OUTWARD TRANSFER"|"OUTWARD TRANSFER JANE SMITH 38000000001 HABAEE2X EE000000000000000002"||"CT00000001"||"-10.00"\n'
)


def _make_config(source_converters: dict) -> MagicMock:
    config = MagicMock()
    config.get.side_effect = lambda key, default=None: (
        source_converters if key == 'source_converters' else default
    )
    return config


# ---------------------------------------------------------------------------
# read_csv_header with skip_rows
# ---------------------------------------------------------------------------

class TestReadCsvHeaderSkipRows:
    def test_reads_first_row_by_default(self):
        content = b'"Date"|"Type"|"Amount"\n"data"\n'
        result = read_csv_header(io.BytesIO(content))
        assert result == ['Date', 'Type', 'Amount']

    def test_skips_rows_before_reading_header(self):
        content = (
            b'"Account"|"EUR EE521234567890"\n'
            b'"From"|"01.01.2026"\n'
            b'""\n'
            b'"Date"|"Type"|"Amount"\n'
        )
        result = read_csv_header(io.BytesIO(content), skip_rows=3)
        assert result == ['Date', 'Type', 'Amount']

    def test_returns_none_when_skipping_past_end_of_file(self):
        result = read_csv_header(io.BytesIO(b'"Date"|"Type"\n'), skip_rows=5)
        assert result is None

    def test_resets_buffer_position_before_reading(self):
        buf = io.BytesIO(b'"Date"|"Type"\n')
        buf.read()  # advance past start
        result = read_csv_header(buf)
        assert result is not None


# ---------------------------------------------------------------------------
# BankDetector — signature loading
# ---------------------------------------------------------------------------

class TestBankDetectorSignatureLoading:
    def test_loads_citadele_under_skip_rows_3(self):
        config = _make_config({
            'citadele': {
                'detection_header_row': 3,
                'sample_files': [_CITADELE_SAMPLE],
            }
        })
        detector = BankDetector(config)
        assert 3 in detector._signatures_by_skip
        assert 'citadele' in detector._signatures_by_skip[3].values()

    def test_loads_standard_bank_under_skip_rows_0(self):
        config = _make_config({
            'luminor': {
                'sample_files': [_LUMINOR_SAMPLE],
            }
        })
        detector = BankDetector(config)
        assert 0 in detector._signatures_by_skip
        assert 'luminor' in detector._signatures_by_skip[0].values()

    def test_banks_with_different_skip_rows_stored_separately(self):
        config = _make_config({
            'luminor': {
                'sample_files': [_LUMINOR_SAMPLE],
            },
            'citadele': {
                'detection_header_row': 3,
                'sample_files': [_CITADELE_SAMPLE],
            },
        })
        detector = BankDetector(config)
        assert 'luminor' not in detector._signatures_by_skip.get(3, {}).values()
        assert 'citadele' not in detector._signatures_by_skip.get(0, {}).values()


# ---------------------------------------------------------------------------
# BankDetector — detection
# ---------------------------------------------------------------------------

class TestBankDetectorDetection:
    def test_detects_citadele_from_real_file_with_metadata_rows(self):
        config = _make_config({
            'citadele': {
                'detection_header_row': 3,
                'sample_files': [_CITADELE_SAMPLE],
            }
        })
        detector = BankDetector(config)
        bank_type, _ = detector.detect_bank_from_header(io.BytesIO(_CITADELE_REAL_CONTENT))
        assert bank_type == 'citadele'

    def test_standard_bank_detection_unaffected(self):
        luminor_content = Path(_LUMINOR_SAMPLE).read_bytes()
        config = _make_config({
            'luminor': {
                'sample_files': [_LUMINOR_SAMPLE],
            }
        })
        detector = BankDetector(config)
        bank_type, _ = detector.detect_bank_from_header(io.BytesIO(luminor_content))
        assert bank_type == 'luminor'

    def test_returns_none_for_unknown_file(self):
        config = _make_config({
            'citadele': {
                'detection_header_row': 3,
                'sample_files': [_CITADELE_SAMPLE],
            }
        })
        detector = BankDetector(config)
        bank_type, _ = detector.detect_bank_from_header(io.BytesIO(b'"Unknown"|"Header"\n'))
        assert bank_type is None

    def test_citadele_metadata_row_does_not_false_match_skip0_banks(self):
        """Row 0 of a Citadele file must not be mistaken for another bank."""
        config = _make_config({
            'luminor': {
                'sample_files': [_LUMINOR_SAMPLE],
            },
            'citadele': {
                'detection_header_row': 3,
                'sample_files': [_CITADELE_SAMPLE],
            },
        })
        detector = BankDetector(config)
        bank_type, _ = detector.detect_bank_from_header(io.BytesIO(_CITADELE_REAL_CONTENT))
        assert bank_type == 'citadele'
