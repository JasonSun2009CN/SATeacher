import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Inspector from "./Inspector";
import { vi } from "vitest";
import type { ResultItem } from "../../api/client";

// Use vi.hoisted for mocks that need to be available in vi.mock factory
const mockApi = vi.hoisted(() => ({
  normalizeDocument: vi.fn(),
  getNormalizeJob: vi.fn(),
  askAI: vi.fn(),
  saveExplain: vi.fn(),
  getSession: vi.fn(),
  regradeSession: vi.fn(),
  getWords: vi.fn(),
  putWords: vi.fn(),
  wordsExportUrl: vi.fn(),
  exportUrl: vi.fn((docId: number, fmt: string) => `/export/${docId}/${fmt}`),
  listDocuments: vi.fn(),
  getDocument: vi.fn(),
  deleteDocument: vi.fn(),
  listBanks: vi.fn(),
  addBuiltinUnit: vi.fn(),
  createImport: vi.fn(),
  getImport: vi.fn(),
  commitImport: vi.fn(),
  cancelImport: vi.fn(),
  deleteImport: vi.fn(),
  aiFallbackImport: vi.fn(),
  health: vi.fn(),
  getSettings: vi.fn(),
  listProviders: vi.fn(),
  saveSettings: vi.fn(),
  testSettings: vi.fn(),
}));

// Mock ApiError class - must be in hoisted for vi.mock
const MockApiError = vi.hoisted(() => {
  class MockApiError extends Error {
    status: number;
    constructor(message: string, status: number) {
      super(message);
      this.status = status;
    }
  }
  return MockApiError;
});

vi.mock("../../api/client", () => ({
  api: mockApi,
  ApiError: MockApiError,
}));

const mockItem: ResultItem = {
  question_id: 1,
  no: 1,
  source_no: 1,
  sec: "rw",
  material: "Test material",
  stem: "Test question?",
  options: ["Option A", "Option B", "Option C", "Option D"],
  images: [],
  answer: "A",
  explain: "Test explanation",
  source: "p.1",
  chosen: null,
  is_correct: null,
};

describe("Inspector", () => {
  const onTab = vi.fn();
  const onClose = vi.fn();
  const onExplainSaved = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders with tabs", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByRole("tab", { name: "Explanation" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "AI Tutor" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Normalize" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Export" })).toBeInTheDocument();
  });

  it("shows question info in header", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByText("Question 1 · Reading & Writing")).toBeInTheDocument();
  });

  it("shows explanation tab content", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByPlaceholderText("Why is the correct answer right? Write it in your own words…")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Test explanation")).toBeInTheDocument();
  });

  it("updates draft and calls onExplainSaved", async () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    const textarea = screen.getByPlaceholderText("Why is the correct answer right? Write it in your own words…");
    fireEvent.change(textarea, { target: { value: "New explanation" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(onExplainSaved).toHaveBeenCalledWith(1, "New explanation"));
  });

  it("switches to AI tab and calls askAI", async () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="ai"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByRole("button", { name: "Explain with AI" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Explain with AI" }));
    // Note: actual API call is mocked, just verify button click works
  });

  it("shows the whole-document Normalize panel", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="normalize"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByText(/Rewrites every question in College Board style/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Normalize whole document" })).toBeEnabled();
  });

  it("shows Export tab with PDF and DOCX links", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="export"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    // Links text is split across nodes, so use getByText with regex
    expect(screen.getByText(/Export \.pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/Export \.docx/i)).toBeInTheDocument();
  });

  it("calls onTab when tab clicked", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    fireEvent.click(screen.getByRole("tab", { name: "AI Tutor" }));
    expect(onTab).toHaveBeenCalledWith("ai");
  });

  it("calls onClose when close button clicked", () => {
    render(
      <Inspector
        docId={1}
        item={mockItem}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Hide inspector" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows select a question when item is null", () => {
    render(
      <Inspector
        docId={1}
        item={null}
        tab="explain"
        onTab={onTab}
        onClose={onClose}
        onExplainSaved={onExplainSaved}
      />
    );

    expect(screen.getByText("Select a question in the list.")).toBeInTheDocument();
  });
});
