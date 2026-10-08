import { render, screen, fireEvent } from "@testing-library/react";
import Splitter from "../workspace/Splitter";
import { vi } from "vitest";

describe("Splitter", () => {
  it("renders with correct role and aria attributes", () => {
    render(<Splitter label="Test splitter" onResize={vi.fn()} />);
    const splitter = screen.getByRole("separator", { name: "Test splitter" });
    expect(splitter).toBeInTheDocument();
    expect(splitter).toHaveAttribute("aria-orientation", "vertical");
    expect(splitter).toHaveAttribute("tabIndex", "0");
  });

  it.skip("calls onResize when dragged (requires setPointerCapture)", () => {
    const onResize = vi.fn();
    render(<Splitter label="Test" onResize={onResize} orientation="vertical" />);
    const splitter = screen.getByRole("separator");

    fireEvent.pointerDown(splitter, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 150, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onResize).toHaveBeenCalledWith(50);
  });

  it.skip("calls onResize with negative delta when dragged left (requires setPointerCapture)", () => {
    const onResize = vi.fn();
    render(<Splitter label="Test" onResize={onResize} orientation="vertical" />);
    const splitter = screen.getByRole("separator");

    fireEvent.pointerDown(splitter, { clientX: 100, pointerId: 1 });
    fireEvent.pointerMove(window, { clientX: 80, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onResize).toHaveBeenCalledWith(-20);
  });

  it.skip("horizontal orientation uses clientY (requires setPointerCapture)", () => {
    const onResize = vi.fn();
    render(<Splitter label="Test" onResize={onResize} orientation="horizontal" />);
    const splitter = screen.getByRole("separator");

    fireEvent.pointerDown(splitter, { clientY: 100, pointerId: 1 });
    fireEvent.pointerMove(window, { clientY: 130, pointerId: 1 });
    fireEvent.pointerUp(window, { pointerId: 1 });

    expect(onResize).toHaveBeenCalledWith(30);
  });

  it("calls onReset on double click", () => {
    const onResize = vi.fn();
    const onReset = vi.fn();
    render(<Splitter label="Test" onResize={onResize} onReset={onReset} />);
    const splitter = screen.getByRole("separator");

    fireEvent.doubleClick(splitter);
    expect(onReset).toHaveBeenCalled();
  });

  it("keyboard navigation works", () => {
    const onResize = vi.fn();
    render(<Splitter label="Test" onResize={onResize} step={10} />);
    const splitter = screen.getByRole("separator", { name: "Test" });

    fireEvent.keyDown(splitter, { key: "ArrowRight" });
    expect(onResize).toHaveBeenCalledWith(10);

    fireEvent.keyDown(splitter, { key: "ArrowLeft" });
    expect(onResize).toHaveBeenCalledWith(-10);

    const onReset = vi.fn();
    render(<Splitter label="Test2" onResize={onResize} onReset={onReset} />);
    const splitter2 = screen.getByRole("separator", { name: "Test2" });
    fireEvent.keyDown(splitter2, { key: "Enter" });
    expect(onReset).toHaveBeenCalled();
  });
});