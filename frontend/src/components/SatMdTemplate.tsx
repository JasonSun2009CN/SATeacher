import { useState } from "react";

/** Minimal, valid SAT-MD the user can copy or download and fill in by hand. */
export const SAT_MD_TEMPLATE = `---
satmd: 1
title: "My practice set"
source: "my-set.sat.md"
lang: en
answers: none
---

:::q {#Q001 sec=rw no=1}
@stem
Replace this line with the question stem.

- A. First choice
- B. Second choice
- C. Third choice
- D. Fourth choice
:::

:::q {#Q002 sec=math no=2}
! answer: B
! explain: Optional hand-written explanation (no tokens).
What is the value of $x$ if $x + 2 = 5$?

- A. 1
- B. 3
- C. 5
- D. 7
:::
`;

export default function SatMdTemplate() {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(SAT_MD_TEMPLATE);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const downloadUrl = `data:text/markdown;charset=utf-8,${encodeURIComponent(SAT_MD_TEMPLATE)}`;

  return (
    <details className="mt-4 rounded-lg border bg-slate-50 p-4">
      <summary className="cursor-pointer text-sm font-medium text-slate-700">
        Or start from the <code className="rounded bg-slate-200 px-1">.sat.md</code> template
      </summary>
      <p className="mt-3 text-sm text-slate-600">
        A plain-text format you can write or edit by hand — imported with zero tokens and no
        cloud. Questions use a <code className="rounded bg-slate-200 px-1">{":::q"}</code> block
        with exactly four <code className="rounded bg-slate-200 px-1">A–D</code> options.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          onClick={copy}
          className="rounded-lg border bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-100"
        >
          {copied ? "Copied ✓" : "Copy template"}
        </button>
        <a
          href={downloadUrl}
          download="template.sat.md"
          className="rounded-lg border bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-100"
        >
          Download .sat.md
        </a>
      </div>
      <pre className="mt-3 max-h-72 overflow-auto rounded-lg bg-slate-900 p-3 text-xs leading-relaxed text-slate-100">
        {SAT_MD_TEMPLATE}
      </pre>
    </details>
  );
}