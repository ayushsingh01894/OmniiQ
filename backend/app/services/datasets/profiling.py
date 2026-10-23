"""Deterministic data-quality profile. All numbers come from pandas, never from a model."""

from typing import Any

import pandas as pd

from app.services.datasets.frames import column_kind, safe_number

HIGH_MISSING_PCT = 50.0
HIGH_CARDINALITY_RATIO = 0.9
TOP_N = 5


def build_profile(df: pd.DataFrame) -> dict[str, Any]:
    rows = int(len(df))
    columns: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    duplicates = int(df.duplicated().sum()) if rows else 0
    if duplicates:
        issues.append(
            {
                "severity": "warning",
                "column": None,
                "code": "duplicate_rows",
                "message": f"{duplicates} duplicate row(s) found.",
            }
        )

    for name in df.columns:
        series = df[name]
        kind = column_kind(series)
        missing = int(series.isna().sum())
        missing_pct = round(100.0 * missing / rows, 2) if rows else 0.0
        unique = int(series.nunique(dropna=True))
        col: dict[str, Any] = {
            "name": str(name),
            "dtype": kind,
            "missing": missing,
            "missing_pct": missing_pct,
            "unique": unique,
            "stats": None,
            "top_values": None,
        }
        non_null = series.dropna()
        if kind in ("integer", "float") and len(non_null):
            numeric = non_null.astype("float64")
            col["stats"] = {
                "min": safe_number(numeric.min()),
                "max": safe_number(numeric.max()),
                "mean": safe_number(numeric.mean()),
                "std": safe_number(numeric.std()) if len(numeric) > 1 else None,
                "median": safe_number(numeric.median()),
                "q1": safe_number(numeric.quantile(0.25)),
                "q3": safe_number(numeric.quantile(0.75)),
            }
        elif kind == "datetime" and len(non_null):
            col["stats"] = {"min": non_null.min().isoformat(), "max": non_null.max().isoformat()}
        if kind in ("string", "boolean") and len(non_null):
            counts = non_null.astype(str).value_counts().head(TOP_N)
            col["top_values"] = [{"value": str(v), "count": int(c)} for v, c in counts.items()]
        columns.append(col)

        if rows and missing_pct >= HIGH_MISSING_PCT:
            issues.append(
                {
                    "severity": "warning",
                    "column": str(name),
                    "code": "high_missing",
                    "message": f"{missing_pct}% of values are missing.",
                }
            )
        if rows > 1 and unique <= 1 and missing < rows:
            issues.append(
                {
                    "severity": "info",
                    "column": str(name),
                    "code": "constant_column",
                    "message": "Every non-missing value is identical.",
                }
            )
        if (
            kind == "string"
            and rows >= 20
            and unique / max(rows - missing, 1) >= HIGH_CARDINALITY_RATIO
        ):
            issues.append(
                {
                    "severity": "info",
                    "column": str(name),
                    "code": "high_cardinality",
                    "message": "Almost every value is different (an identifier or free text?).",
                }
            )

    return {
        "row_count": rows,
        "column_count": int(df.shape[1]),
        "duplicate_rows": duplicates,
        "missing_cells": int(df.isna().sum().sum()),
        "columns": columns,
        "issues": issues,
    }
