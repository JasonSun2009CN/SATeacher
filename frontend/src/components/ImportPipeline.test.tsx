import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ImportPipeline from "./ImportPipeline";
import { vi } from "vitest";

const createMockJob = (overrides = {}) => ({
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

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders job info", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Import pipeline")).toBeInTheDocument();
    expect(screen.getByText(/test\.pdf/)).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("shows stages with correct status", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Detect")).toBeInTheDocument();
    expect(screen.getByText("Convert")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Commit")).toBeInTheDocument();
  });

  it("displays page reports with status badges", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Page 1")).toBeInTheDocument();
    expect(screen.getByText("text layer")).toBeInTheDocument();
    expect(screen.getByText("OCR (tesseract)")).toBeInTheDocument();
    expect(screen.getByText("OCR · low confidence (tesseract)")).toBeInTheDocument();
  });

  it("shows confidence percentages", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("shows stats when in review stage", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Questions")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Answers")).toBeInTheDocument();
    expect(screen.getByText("AI used")).toBeInTheDocument();
    expect(screen.getByText("no (0 token)")).toBeInTheDocument();
  });

  it("shows warnings when present", () => {
    const job = createMockJob({ warnings: ["Warning 1", "Warning 2"] });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Warning 1")).toBeInTheDocument();
    expect(screen.getByText("Warning 2")).toBeInTheDocument();
  });

  it("shows commit and cancel buttons in review stage", () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByRole("button", { name: "Looks good — import" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("calls onCommit when commit button clicked", async () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole("button", { name: "Looks good — import" }));
    await waitFor(() => expect(onCommit).toHaveBeenCalled());
  });

  it("calls onCancel when cancel button clicked", async () => {
    render(<ImportPipeline job={createMockJob()} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(onCancel).toHaveBeenCalled());
  });

  it("disables buttons when busy", () => {
    render(<ImportPipeline job={createMockJob()} busy={true} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByRole("button", { name: "Looks good — import" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
  });

  it("shows 'Imported X questions' when done", () => {
    const job = createMockJob({ status: "done", document_id: 1 });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Imported 5 questions.")).toBeInTheDocument();
  });

  it("shows error message when failed", () => {
    const job = createMockJob({ status: "failed", error: "Something went wrong" });
    render(<ImportPipeline job={job} busy={false} onCommit={onCommit} onCancel={onCancel} />);

    expect(screen.getByText("Import failed")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});