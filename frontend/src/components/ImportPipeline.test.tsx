import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ImportPipeline from "./ImportPipeline";
import { vi } from "vitest";
import type { ImportJob } from "../api/client";

const createMockJob = (overrides: Partial<ImportJob> = {}): ImportJob => ({
  id: "job-123",
  filename: "test.pdf",
  status: "review",
  stage: "validate",
  kind: "pdf",
  import_source: "pdf",
  pages_total: 3,
  pages_done: 3,
  question_count: 5,
  used_ai: false,
  document_id: null,
  error: null,
  created_at: "2026-10-09T00:00:00Z",
  warnings: [],
  pages: [
    { no: 1, status: "text", source: null, confidence: null, reason: null },
    { no: 2, status: "ocr_ok", source: "tesseract", confidence: 0.95, reason: null },
    { no: 3, status: "low_confidence", source: "tesseract", confidence: 0.6, reason: "low OCR confidence" },
  ],
  needs_review: true,
  ...overrides,
});

describe("ImportPipeline", () => {
  const onCommit = vi.fn();
  const onCancel = vi.fn();
  const onAiFallback = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders job info", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Import pipeline")).toBeInTheDocument();
    expect(screen.getByText(/test\.pdf/)).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("shows stages with correct status", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Detect")).toBeInTheDocument();
    expect(screen.getByText("Convert")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Commit")).toBeInTheDocument();
  });

  it("displays page reports with status badges", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(screen.getByText("text layer")).toBeInTheDocument();
    expect(screen.getByText("OCR (tesseract)")).toBeInTheDocument();
    expect(screen.getByText("OCR · low confidence (tesseract)")).toBeInTheDocument();
  });

  it("shows confidence percentages", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("shows stats when in review stage", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Questions")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Answers")).toBeInTheDocument();
    expect(screen.getByText("AI used")).toBeInTheDocument();
    expect(screen.getByText("no (0 token)")).toBeInTheDocument();
  });

  it("shows warnings when present", () => {
    const job = createMockJob({ warnings: ["Warning 1", "Warning 2"] });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Warning 1")).toBeInTheDocument();
    expect(screen.getByText("Warning 2")).toBeInTheDocument();
  });

  it("shows commit and cancel buttons in review stage", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByRole("button", { name: "Looks good — import" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls onCommit when commit button clicked", async () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    fireEvent.click(screen.getByRole("button", { name: "Looks good — import" }));
    await waitFor(() => expect(onCommit).toHaveBeenCalled());
  });

  it("calls onCancel when cancel button clicked", async () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(onCancel).toHaveBeenCalled());
  });

  it("disables buttons when busy", () => {
    render(<ImportPipeline job={createMockJob()} busy={true} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByRole("button", { name: "Looks good — import" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows 'Imported X questions' when done", () => {
    const job = createMockJob({ status: "done", document_id: 1 });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Imported 5 questions.")).toBeInTheDocument();
  });

  it("shows error message when failed", () => {
    const job = createMockJob({ status: "failed", error: "Something went wrong" });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Import failed")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("shows per-page progress while converting", () => {
    const job = createMockJob({
      status: "converting",
      stage: "convert",
      pages: [],
      pages_done: 2,
      pages_total: 5,
      question_count: 0,
      needs_review: false,
    });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("Converting…")).toBeInTheDocument();
    expect(screen.getByText("2/5 pages")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: "Conversion progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "2");
    expect(bar).toHaveAttribute("aria-valuemax", "5");
    // no review actions until the conversion settles
    expect(screen.queryByRole("button", { name: "Looks good — import" })).not.toBeInTheDocument();
  });

  it("shows an indeterminate bar before the page count is known", () => {
    const job = createMockJob({
      status: "converting",
      stage: "convert",
      pages: [],
      pages_done: 0,
      pages_total: 0,
      needs_review: false,
    });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    expect(screen.getByText("counting pages")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Conversion progress" })).not.toHaveAttribute(
      "aria-valuenow",
    );
  });

  it("offers Cancel while converting and calls onCancel", async () => {
    const job = createMockJob({ status: "converting", stage: "convert", pages: [], needs_review: false });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(onCancel).toHaveBeenCalled());
  });

  it("offers AI fallback for unreadable pages in review", async () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} onAiFallback={onAiFallback} />);

    fireEvent.click(
      screen.getByRole("button", { name: "Run AI fallback on unreadable pages" }),
    );
    await waitFor(() => expect(onAiFallback).toHaveBeenCalled());
  });
});