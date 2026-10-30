import { describe, expect, it } from "vitest";

import { buildOp, describeOp, emptyDraft, type Draft } from "./cleaningOps";

const schema = [
  { name: "id", dtype: "integer", nullable: false },
  { name: "flag", dtype: "boolean", nullable: true },
  { name: "name", dtype: "string", nullable: true },
] as const;
const cols = [...schema];
const draft = (over: Partial<Draft>): Draft => ({ ...emptyDraft("id"), ...over });

describe("buildOp", () => {
  it("builds duplicate removal with and without a column subset", () => {
    expect(buildOp(draft({}), cols)).toEqual({ op: { op: "drop_duplicates", keep: "first" } });
    expect(buildOp(draft({ columns: ["id"], keep: "last" }), cols)).toEqual({
      op: { op: "drop_duplicates", keep: "last", subset: ["id"] },
    });
  });

  it("requires columns for drop_columns and refuses to drop them all", () => {
    expect(buildOp(draft({ type: "drop_columns" }), cols)).toEqual({ error: "Choose at least one column to remove." });
    expect(buildOp(draft({ type: "drop_columns", columns: ["id", "flag", "name"] }), cols)).toEqual({
      error: "You can't remove every column.",
    });
    expect(buildOp(draft({ type: "drop_columns", columns: ["id"] }), cols)).toEqual({
      op: { op: "drop_columns", columns: ["id"] },
    });
  });

  it("requires a new name when renaming and trims it", () => {
    expect("error" in buildOp(draft({ type: "rename_column" }), cols)).toBe(true);
    expect(buildOp(draft({ type: "rename_column", column: "id", newName: "  key " }), cols)).toEqual({
      op: { op: "rename_column", column: "id", new_name: "key" },
    });
  });

  it("fill_missing: statistics need no value; constants do; booleans send real booleans", () => {
    expect(buildOp(draft({ type: "fill_missing", strategy: "median" }), cols)).toEqual({
      op: { op: "fill_missing", column: "id", strategy: "median" },
    });
    expect("error" in buildOp(draft({ type: "fill_missing", strategy: "constant", column: "name" }), cols)).toBe(true);
    expect(buildOp(draft({ type: "fill_missing", strategy: "constant", column: "name", value: "n/a" }), cols)).toEqual({
      op: { op: "fill_missing", column: "name", strategy: "constant", value: "n/a" },
    });
    expect(buildOp(draft({ type: "fill_missing", strategy: "constant", column: "flag", value: "true" }), cols)).toEqual({
      op: { op: "fill_missing", column: "flag", strategy: "constant", value: true },
    });
    expect("error" in buildOp(draft({ type: "fill_missing", strategy: "constant", column: "flag", value: "maybe" }), cols)).toBe(true);
  });
});

describe("describeOp", () => {
  it("describes operations in plain language (also for stored versions)", () => {
    expect(describeOp({ op: "drop_duplicates", keep: "first" })).toBe("Remove duplicate rows, keep first");
    expect(describeOp({ op: "rename_column", column: "a", new_name: "b" })).toBe("Rename a to b");
    expect(describeOp({ op: "fill_missing", column: "x", strategy: "mean", value: null })).toBe("Fill missing in x with mean");
    expect(describeOp({ op: "trim_whitespace" })).toBe("Trim spaces in all text columns");
    expect(describeOp({ op: "cast_type", column: "x", to: "integer" })).toBe("Change x to integer");
  });
});
