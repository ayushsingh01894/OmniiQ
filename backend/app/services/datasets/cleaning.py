"""Explicit, reproducible cleaning operations. Same input + same operations => same output.

Errors never include cell values, only column names and counts.
"""

from typing import Any

import pandas as pd

from app.schemas.cleaning import (
    CastType,
    DropColumns,
    DropDuplicates,
    DropMissing,
    FillMissing,
    Operation,
    RenameColumn,
    TrimWhitespace,
)
from app.services.datasets.errors import DatasetError
from app.services.datasets.frames import column_kind

_TRUE = {"true", "t", "yes", "y", "1"}
_FALSE = {"false", "f", "no", "n", "0"}


def _require(df: pd.DataFrame, columns: list[str] | None) -> list[str]:
    if columns is None:
        return [str(c) for c in df.columns]
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DatasetError("unknown_column", f"Unknown column(s): {', '.join(missing)}.")
    return columns


def _cast(series: pd.Series, name: str, target: str) -> pd.Series:
    def fail() -> DatasetError:
        return DatasetError(
            "cast_failed", f"Some values in column '{name}' cannot be converted to {target}."
        )

    try:
        if target == "string":
            return series.astype("str")
        if target == "datetime":
            if column_kind(series) == "datetime":
                return series
            return pd.to_datetime(series, format="ISO8601", utc=True).dt.tz_localize(None)
        if target == "boolean":
            if column_kind(series) == "boolean":
                return series
            if column_kind(series) in ("integer", "float"):
                nums = series.astype("float64")
                if not nums.dropna().isin([0.0, 1.0]).all():
                    raise fail()
                return nums.map(lambda v: pd.NA if v != v else bool(v)).astype("boolean")
            lowered = series.astype("str").str.strip().str.lower()
            out = pd.Series(pd.NA, index=series.index, dtype="boolean")
            out[lowered.isin(_TRUE)] = True
            out[lowered.isin(_FALSE)] = False
            unconverted = series.notna() & out.isna()
            if unconverted.any():
                raise fail()
            return out
        numeric = pd.to_numeric(series, errors="raise")
        if target == "float":
            return numeric.astype("float64")
        # integer: only whole numbers qualify
        if column_kind(numeric) == "float" and not (numeric.dropna() % 1 == 0).all():
            raise fail()
        return numeric.astype("Int64")
    except DatasetError:
        raise
    except (ValueError, TypeError, OverflowError):
        raise fail() from None


def _fill_constant(series: pd.Series, name: str, value: Any) -> pd.Series:
    kind = column_kind(series)
    try:
        if kind == "integer":
            if isinstance(value, bool) or float(value) % 1 != 0:
                raise ValueError
            return series.fillna(int(float(value)))
        if kind == "float":
            if isinstance(value, bool):
                raise ValueError
            return series.fillna(float(value))
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError
            return series.fillna(value)
        if kind == "datetime":
            return series.fillna(
                pd.to_datetime(str(value), format="ISO8601", utc=True).tz_localize(None)
            )
        return series.fillna(str(value))
    except (ValueError, TypeError):
        raise DatasetError(
            "invalid_fill_value", f"The fill value is not valid for the {kind} column '{name}'."
        ) from None


def _apply_one(df: pd.DataFrame, op: Operation) -> pd.DataFrame:
    if isinstance(op, DropDuplicates):
        subset = _require(df, op.subset) if op.subset else None
        return df.drop_duplicates(subset=subset, keep=op.keep).reset_index(drop=True)

    if isinstance(op, DropMissing):
        subset = _require(df, op.columns) if op.columns else None
        return df.dropna(subset=subset, how=op.how).reset_index(drop=True)

    if isinstance(op, FillMissing):
        _require(df, [op.column])
        out = df.copy()
        series = out[op.column]
        kind = column_kind(series)
        if op.strategy in ("mean", "median"):
            if kind not in ("integer", "float"):
                raise DatasetError(
                    "invalid_operation",
                    f"'{op.strategy}' needs a numeric column; '{op.column}' is {kind}.",
                )
            if series.dropna().empty:
                raise DatasetError(
                    "invalid_operation", f"Column '{op.column}' has no values to compute from."
                )
            number = (
                series.astype("float64").mean()
                if op.strategy == "mean"
                else series.astype("float64").median()
            )
            out[op.column] = series.astype("float64").fillna(number)
        elif op.strategy == "mode":
            modes = series.mode(dropna=True)
            if modes.empty:
                raise DatasetError(
                    "invalid_operation", f"Column '{op.column}' has no values to compute from."
                )
            out[op.column] = series.fillna(modes.iloc[0])
        else:
            out[op.column] = _fill_constant(series, op.column, op.value)
        return out

    if isinstance(op, DropColumns):
        cols = _require(df, op.columns)
        if len(set(cols)) >= df.shape[1]:
            raise DatasetError("invalid_operation", "You cannot drop every column.")
        return df.drop(columns=cols)

    if isinstance(op, RenameColumn):
        _require(df, [op.column])
        if op.new_name != op.column and op.new_name in df.columns:
            raise DatasetError(
                "duplicate_columns", f"A column named '{op.new_name}' already exists."
            )
        return df.rename(columns={op.column: op.new_name})

    if isinstance(op, TrimWhitespace):
        cols = _require(df, op.columns)
        out = df.copy()
        for name in cols:
            if column_kind(out[name]) != "string":
                if op.columns is not None:
                    raise DatasetError("invalid_operation", f"Column '{name}' is not text.")
                continue
            out[name] = out[name].str.strip()
        return out

    if isinstance(op, CastType):
        _require(df, [op.column])
        out = df.copy()
        out[op.column] = _cast(out[op.column], op.column, op.to)
        return out

    raise DatasetError("invalid_operation", "Unknown operation.")  # unreachable via the schema


def apply_operations(
    df: pd.DataFrame, operations: list[Operation]
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    steps: list[dict[str, Any]] = []
    for index, op in enumerate(operations, start=1):
        before = len(df)
        try:
            df = _apply_one(df, op)
        except DatasetError as exc:
            raise DatasetError(exc.code, f"Step {index} ({op.op}): {exc.message}") from None
        steps.append(
            {
                "step": index,
                "op": op.op,
                "rows_before": int(before),
                "rows_after": int(len(df)),
                "columns_after": int(df.shape[1]),
            }
        )
    return df, steps
