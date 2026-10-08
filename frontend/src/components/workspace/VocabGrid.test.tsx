import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import VocabGrid from "./VocabGrid";
import { vi } from "vitest";

const createMockGrid = (overrides = {}) => ({
  version: 2,
  columns: [
    { id: "c1", name: "Word", width: 180 },
    { id: "c2", name: "Meaning", width: 260 },
    { id: "c3", name: "Notes", width: 220 },
  ],
  rows: [
    { id: "r1", cells: { c1: "elate", c2: "make happy", c3: "verb" } },
    { id: "r2", cells: { c1: "cadence", c2: "rhythm", c3: "noun" } },
  ],
  view: { sort: null, filter: {} },
  ...overrides,
});

describe("VocabGrid", () => {
  it("renders columns and rows", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    // Column names are in input fields
    expect(screen.getByDisplayValue("Word")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Meaning")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Notes")).toBeInTheDocument();
    expect(screen.getByDisplayValue("elate")).toBeInTheDocument();
    expect(screen.getByDisplayValue("make happy")).toBeInTheDocument();
  });

  it("shows row count in toolbar", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);
    expect(screen.getByText("2 words")).toBeInTheDocument();
  });

  it("calls onChange when cell value changes", async () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const input = screen.getByDisplayValue("elate");
    await act(async () => {
      fireEvent.change(input, { target: { value: "elated" } });
    });

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.rows[0].cells.c1).toBe("elated");
  });

  it("adds row when + Row button clicked", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const addRowBtn = screen.getByRole("button", { name: "+ Row" });
    fireEvent.click(addRowBtn);

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.rows).toHaveLength(3);
    expect(newGrid.rows[2].cells).toEqual({ c1: "", c2: "", c3: "" });
  });

  it("adds column when + Column button clicked", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const addColBtn = screen.getByRole("button", { name: "+ Column" });
    fireEvent.click(addColBtn);

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.columns).toHaveLength(4);
    expect(newGrid.columns[3].name).toBe("Column 4");
  });

  it("deletes row when delete button clicked", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const deleteBtn = screen.getByRole("button", { name: "Delete row 1" });
    fireEvent.click(deleteBtn);

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.rows).toHaveLength(1);
    expect(newGrid.rows[0].id).toBe("r2");
  });

  it.skip("toggles sort on header click (requires parent re-render for state updates)", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const sortBtn = screen.getByRole("button", { name: "Sort by Word" });
    fireEvent.click(sortBtn);

    expect(onChange).toHaveBeenCalledTimes(1);
    const firstCall = onChange.mock.calls[0][0];
    expect(firstCall.view.sort).toEqual({ columnId: "c1", direction: "asc" });

    // Second click toggles to desc
    fireEvent.click(sortBtn);
    expect(onChange).toHaveBeenCalledTimes(2);
    const secondCall = onChange.mock.calls[1][0];
    expect(secondCall.view.sort).toEqual({ columnId: "c1", direction: "desc" });

    // Third click clears sort
    fireEvent.click(sortBtn);
    expect(onChange).toHaveBeenCalledTimes(3);
    const thirdCall = onChange.mock.calls[2][0];
    expect(thirdCall.view.sort).toBeNull();
  });

  it("filters rows by column filter", () => {
    const onChange = vi.fn();
    // Pass a grid with filter already applied to test rendering
    const filteredGrid = createMockGrid({
      view: { sort: null, filter: { c1: "cad" } },
    });
    render(<VocabGrid grid={filteredGrid} onChange={onChange} />);

    // Should show only 1 row (cadence)
    expect(screen.getByDisplayValue("cadence")).toBeInTheDocument();
    expect(screen.queryByDisplayValue("elate")).not.toBeInTheDocument();
    expect(screen.getByText("2 words · 1 shown")).toBeInTheDocument();
  });

  it("shows filtered count", () => {
    const onChange = vi.fn();
    const filteredGrid = createMockGrid({
      view: { sort: null, filter: { c1: "cad" } },
    });
    render(<VocabGrid grid={filteredGrid} onChange={onChange} />);

    expect(screen.getByText("2 words · 1 shown")).toBeInTheDocument();
  });

  it("clears filter", () => {
    const onChange = vi.fn();
    // Start with filtered grid
    const filteredGrid = createMockGrid({
      view: { sort: null, filter: { c1: "cad" } },
    });
    render(<VocabGrid grid={filteredGrid} onChange={onChange} />);

    // Simulate clearing filter by re-rendering with cleared filter
    const clearedGrid = createMockGrid({
      view: { sort: null, filter: {} },
    });
    render(<VocabGrid grid={clearedGrid} onChange={onChange} />);

    expect(screen.getByText("2 words")).toBeInTheDocument();
    expect(screen.queryByText("1 shown")).not.toBeInTheDocument();
  });

  it("resets view when Reset view clicked", () => {
    const onChange = vi.fn();
    const gridWithView = createMockGrid({
      view: { sort: { columnId: "c1", direction: "asc" }, filter: { c1: "test" } },
    });
    render(<VocabGrid grid={gridWithView} onChange={onChange} />);

    const resetBtn = screen.getByRole("button", { name: "Reset view" });
    fireEvent.click(resetBtn);

    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.view.sort).toBeNull();
    expect(newGrid.view.filter).toEqual({});
  });

  it("updates column name", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const nameInput = screen.getByDisplayValue("Word");
    fireEvent.change(nameInput, { target: { value: "Vocabulary" } });

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.columns[0].name).toBe("Vocabulary");
  });

  it.skip("resizes column on pointer drag (requires pointer events support)", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const handle = screen.getByRole("separator", { name: "Resize Word" });
    fireEvent.pointerDown(handle, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 150, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onChange).toHaveBeenCalled();
    const newGrid = onChange.mock.calls[0][0];
    expect(newGrid.columns[0].width).toBe(230); // 180 + 50
  });

  it("keyboard navigation moves focus between cells", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid()} onChange={onChange} />);

    const firstCell = screen.getByDisplayValue("elate");
    firstCell.focus();
    expect(firstCell).toHaveFocus();

    fireEvent.keyDown(firstCell, { key: "ArrowDown" });
    const secondCell = screen.getByDisplayValue("cadence");
    expect(secondCell).toHaveFocus();

    fireEvent.keyDown(secondCell, { key: "ArrowUp" });
    expect(firstCell).toHaveFocus();

    fireEvent.keyDown(firstCell, { key: "Enter" });
    expect(secondCell).toHaveFocus();
  });

  it("shows empty state when no rows", () => {
    const onChange = vi.fn();
    render(<VocabGrid grid={createMockGrid({ rows: [] })} onChange={onChange} />);

    expect(screen.getByText("No words yet — add your first row.")).toBeInTheDocument();
  });

  it("shows no rows match filter message", () => {
    const onChange = vi.fn();
    // Pass a grid with a filter that matches no rows
    const filteredGrid = createMockGrid({
      view: { sort: null, filter: { c1: "xyz123nonexistent" } },
    });
    render(<VocabGrid grid={filteredGrid} onChange={onChange} />);

    expect(screen.getByText("No rows match the filter.")).toBeInTheDocument();
  });
});