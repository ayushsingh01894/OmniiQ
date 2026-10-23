"""DataFrame <-> storage helpers, schema inference and JSON-safe conversion."""

import hashlib
import io
import json
import math
import re
from typing import Any

import pandas as pd
from pandas.api import types as ptypes

from app.core.config import Settings
from app.services.datasets.errors import DatasetError
from app.storage.base import Storage

KINDS = ("integer", "float", "boolean", "datetime", "string")
_ISO_DATE_START = re.compile(r"^\d{4}-\d{2}-\d{2}")


def column_kind(series: pd.Series) -> str:
    if ptypes.is_bool_dtype(series):
        return "boolean"
    if ptypes.is_integer_dtype(series):
        return "integer"
    if ptypes.is_float_dtype(series):
        return "float"
    if ptypes.is_datetime64_any_dtype(series):
        return "datetime"
    return "string"


def infer_schema(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {"name": str(name), "dtype": column_kind(df[name]), "nullable": bool(df[name].isna().any())}
        for name in df.columns
    ]


def _normalize_series(series: pd.Series) -> pd.Series:
    kind = column_kind(series)
    if kind != "string":
        return series
    if ptypes.is_string_dtype(series):
        non_null = series.dropna()
    else:
        # object column: Excel can hand back a mix of numbers and text. Keep it lossless as text.
        if series.map(lambda v: isinstance(v, str) or v is None or v != v).all():
            non_null = series.dropna()
        else:
            return series.map(lambda v: None if v is None or v != v else str(v)).astype("str")
    # Convert to datetime only when EVERY value is an ISO date, so no information is lost.
    if len(non_null) and non_null.str.match(_ISO_DATE_START).all():
        parsed = pd.to_datetime(non_null, format="ISO8601", errors="coerce", utc=True)
        if parsed.notna().all():
            return pd.to_datetime(series, format="ISO8601", utc=True).dt.tz_localize(None)
    return series.astype("str")


def normalize_frame(df: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    if df.shape[1] == 0:
        raise DatasetError("empty_dataset", "The file has no columns.")
    if df.shape[1] > settings.max_dataset_columns:
        raise DatasetError(
            "too_many_columns", f"The file has more than {settings.max_dataset_columns} columns."
        )
    names = [str(c).strip() for c in df.columns]
    if any(n == "" for n in names):
        raise DatasetError("empty_column_name", "Every column needs a header name.")
    if len(set(names)) != len(names):
        raise DatasetError("duplicate_columns", "Column names must be unique.")
    out = df.copy()
    out.columns = pd.Index(names)
    for name in names:
        out[name] = _normalize_series(out[name])
    return out.reset_index(drop=True)


def frame_to_parquet(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, engine="pyarrow", index=False)
    return buf.getvalue()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_version_frame(storage: Storage, key: str) -> pd.DataFrame:
    with storage.open(key) as f:
        return pd.read_parquet(io.BytesIO(f.read()), engine="pyarrow")


def to_json_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """NaN/NaT become null and datetimes ISO strings, so the result is valid JSON."""
    records: list[dict[str, Any]] = json.loads(str(df.to_json(orient="records", date_format="iso")))
    return records


def safe_number(value: Any) -> float | int | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return int(number) if isinstance(value, int) and not isinstance(value, bool) else number
