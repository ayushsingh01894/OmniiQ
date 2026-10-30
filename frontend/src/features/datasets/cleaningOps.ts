import type { ColumnSchema, DType } from "../../lib/api";

export type CleaningOp =
  | { op: "drop_duplicates"; subset?: string[]; keep: "first" | "last" }
  | { op: "drop_missing"; columns?: string[]; how: "any" | "all" }
  | {
      op: "fill_missing";
      column: string;
      strategy: "mean" | "median" | "mode" | "constant";
      value?: string | boolean;
    }
  | { op: "drop_columns"; columns: string[] }
  | { op: "rename_column"; column: string; new_name: string }
  | { op: "trim_whitespace"; columns?: string[] }
  | { op: "cast_type"; column: string; to: DType };

export type OpType = CleaningOp["op"];

export const OP_LABELS: Record<OpType, string> = {
  drop_duplicates: "Remove duplicate rows",
  drop_missing: "Remove rows with missing values",
  fill_missing: "Fill missing values",
  drop_columns: "Remove columns",
  rename_column: "Rename a column",
  trim_whitespace: "Trim spaces in text",
  cast_type: "Change a column's type",
};

export type Draft = {
  type: OpType;
  columns: string[];
  column: string;
  strategy: "mean" | "median" | "mode" | "constant";
  value: string;
  newName: string;
  keep: "first" | "last";
  how: "any" | "all";
  to: DType;
};

export const emptyDraft = (firstColumn: string): Draft => ({
  type: "drop_duplicates",
  columns: [],
  column: firstColumn,
  strategy: "mean",
  value: "",
  newName: "",
  keep: "first",
  how: "any",
  to: "string",
});

/** Turns the form state into an operation, or says what is missing. */
export function buildOp(d: Draft, schema: ColumnSchema[]): { op: CleaningOp } | { error: string } {
  const subset = d.columns.length > 0 ? { columns: d.columns } : {};
  switch (d.type) {
    case "drop_duplicates":
      return { op: { op: "drop_duplicates", keep: d.keep, ...(d.columns.length ? { subset: d.columns } : {}) } };
    case "drop_missing":
      return { op: { op: "drop_missing", how: d.how, ...subset } };
    case "trim_whitespace":
      return { op: { op: "trim_whitespace", ...subset } };
    case "drop_columns":
      if (d.columns.length === 0) return { error: "Choose at least one column to remove." };
      if (d.columns.length >= schema.length) return { error: "You can't remove every column." };
      return { op: { op: "drop_columns", columns: d.columns } };
    case "rename_column":
      if (!d.newName.trim()) return { error: "Enter the new column name." };
      return { op: { op: "rename_column", column: d.column, new_name: d.newName.trim() } };
    case "cast_type":
      return { op: { op: "cast_type", column: d.column, to: d.to } };
    case "fill_missing": {
      if (d.strategy !== "constant") return { op: { op: "fill_missing", column: d.column, strategy: d.strategy } };
      const dtype = schema.find((c) => c.name === d.column)?.dtype;
      if (dtype === "boolean") {
        if (d.value !== "true" && d.value !== "false") return { error: "Choose true or false." };
        return { op: { op: "fill_missing", column: d.column, strategy: "constant", value: d.value === "true" } };
      }
      if (d.value === "") return { error: "Enter the value to fill with." };
      return { op: { op: "fill_missing", column: d.column, strategy: "constant", value: d.value } };
    }
  }
}

const list = (cols: unknown) => (Array.isArray(cols) ? cols.join(", ") : "");

/** One plain-language line per operation (also used for stored versions, hence Record<string, unknown>). */
export function describeOp(op: Record<string, unknown>): string {
  const columns = list(op["columns"] ?? op["subset"]);
  switch (op["op"]) {
    case "drop_duplicates":
      return `Remove duplicate rows${columns ? ` (by ${columns})` : ""}, keep ${String(op["keep"] ?? "first")}`;
    case "drop_missing":
      return `Remove rows where ${op["how"] === "all" ? "all" : "any"} value is missing${columns ? ` in ${columns}` : ""}`;
    case "fill_missing":
      return `Fill missing in ${String(op["column"])} with ${op["strategy"] === "constant" ? `“${String(op["value"])}”` : String(op["strategy"])}`;
    case "drop_columns":
      return `Remove columns ${columns}`;
    case "rename_column":
      return `Rename ${String(op["column"])} to ${String(op["new_name"])}`;
    case "trim_whitespace":
      return `Trim spaces${columns ? ` in ${columns}` : " in all text columns"}`;
    case "cast_type":
      return `Change ${String(op["column"])} to ${String(op["to"])}`;
    default:
      return String(op["op"]);
  }
}
