from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

ColumnName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
ColumnList = Annotated[list[ColumnName], Field(min_length=1, max_length=500)]


class _Op(BaseModel):
    model_config = {"extra": "forbid"}


class DropDuplicates(_Op):
    op: Literal["drop_duplicates"]
    subset: ColumnList | None = None
    keep: Literal["first", "last"] = "first"


class DropMissing(_Op):
    op: Literal["drop_missing"]
    columns: ColumnList | None = None
    how: Literal["any", "all"] = "any"


class FillMissing(_Op):
    op: Literal["fill_missing"]
    column: ColumnName
    strategy: Literal["mean", "median", "mode", "constant"]
    value: str | int | float | bool | None = None

    @model_validator(mode="after")
    def _constant_needs_value(self) -> "FillMissing":
        if self.strategy == "constant" and self.value is None:
            raise ValueError("A value is required when strategy is 'constant'.")
        if self.strategy != "constant" and self.value is not None:
            raise ValueError("A value is only allowed when strategy is 'constant'.")
        return self


class DropColumns(_Op):
    op: Literal["drop_columns"]
    columns: ColumnList


class RenameColumn(_Op):
    op: Literal["rename_column"]
    column: ColumnName
    new_name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TrimWhitespace(_Op):
    op: Literal["trim_whitespace"]
    columns: ColumnList | None = None


class CastType(_Op):
    op: Literal["cast_type"]
    column: ColumnName
    to: Literal["integer", "float", "string", "boolean", "datetime"]


Operation = Annotated[
    DropDuplicates
    | DropMissing
    | FillMissing
    | DropColumns
    | RenameColumn
    | TrimWhitespace
    | CastType,
    Field(discriminator="op"),
]


class CleaningRequest(BaseModel):
    base_version: int | None = Field(default=None, ge=1)
    operations: Annotated[list[Operation], Field(min_length=1, max_length=50)]
