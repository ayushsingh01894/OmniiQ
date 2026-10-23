"""Validation of uploads and parsing of the original file into a clean DataFrame."""

import codecs
import io
import zipfile
from typing import BinaryIO

import pandas as pd

from app.core.config import Settings
from app.models.enums import DatasetFormat
from app.services.datasets.errors import DatasetError
from app.services.datasets.frames import normalize_frame
from app.storage.base import Storage

ZIP_MAGIC = b"PK\x03\x04"
_HEAD_BYTES = 64 * 1024


def detect_format(filename: str) -> DatasetFormat:
    lowered = filename.lower()
    if lowered.endswith(".csv"):
        return DatasetFormat.csv
    if lowered.endswith(".xlsx"):
        return DatasetFormat.xlsx
    raise DatasetError("unsupported_file_type", "Only .csv and .xlsx files are supported.")


def check_content_signature(head: bytes, fmt: DatasetFormat) -> None:
    """Don't trust the extension: the bytes must actually look like the claimed format."""
    if fmt is DatasetFormat.xlsx:
        if not head.startswith(ZIP_MAGIC):
            raise DatasetError("invalid_file_content", "This file is not a valid .xlsx workbook.")
        return
    if b"\x00" in head:
        raise DatasetError("invalid_file_content", "This file does not look like a text CSV.")
    decoder = codecs.getincrementaldecoder("utf-8-sig")(errors="strict")
    try:
        decoder.decode(head, final=False)  # final=False: a multi-byte char may be cut at the end
    except UnicodeDecodeError:
        raise DatasetError("invalid_file_content", "CSV files must be UTF-8 encoded.") from None


def check_xlsx_zip(stream: BinaryIO, settings: Settings) -> None:
    """Reject zip bombs and files that are not a spreadsheet, before any parsing."""
    try:
        with zipfile.ZipFile(stream) as zf:
            names = set(zf.namelist())
            if "xl/workbook.xml" not in names:
                raise DatasetError(
                    "invalid_file_content", "This file is not a valid .xlsx workbook."
                )
            total = sum(info.file_size for info in zf.infolist())
            if total > settings.max_xlsx_uncompressed_bytes:
                raise DatasetError("file_too_large", "The workbook expands to too much data.")
    except zipfile.BadZipFile:
        raise DatasetError(
            "invalid_file_content", "This file is not a valid .xlsx workbook."
        ) from None


def head_of(stream: BinaryIO) -> bytes:
    pos = stream.tell()
    head = stream.read(_HEAD_BYTES)
    stream.seek(pos)
    return head


def read_original(
    storage: Storage, key: str, fmt: DatasetFormat, settings: Settings
) -> pd.DataFrame:
    limit = settings.max_dataset_rows
    with storage.open(key) as f:
        raw = f.read()
    try:
        if fmt is DatasetFormat.xlsx:
            check_xlsx_zip(io.BytesIO(raw), settings)
            df = pd.read_excel(io.BytesIO(raw), engine="openpyxl", nrows=limit + 1)
        else:
            df = pd.read_csv(
                io.BytesIO(raw), encoding="utf-8-sig", nrows=limit + 1, on_bad_lines="error"
            )
    except DatasetError:
        raise
    except pd.errors.EmptyDataError:
        raise DatasetError("empty_dataset", "The file is empty.") from None
    except (pd.errors.ParserError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, KeyError):
        raise DatasetError(
            "unreadable_file", "The file could not be read as a table. Check its format."
        ) from None
    if len(df) > limit:
        raise DatasetError("too_many_rows", f"The file has more than {limit:,} rows.")
    if len(df) == 0:
        raise DatasetError("empty_dataset", "The file has a header but no data rows.")
    return normalize_frame(df, settings)
