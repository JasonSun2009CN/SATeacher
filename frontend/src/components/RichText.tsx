import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { api } from "../api/client";

interface Props {
  text: string;
  /** Document id, used to resolve `assets/...` image paths. */
  docId?: number;
}

/** Markdown + `$math$` renderer shared by every question surface. */
export default function RichText({ text, docId }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
      components={{
        img: ({ src, alt }) => (
          <img
            src={api.assetUrl(docId, String(src ?? ""))}
            alt={alt ?? "figure"}
            className="my-2 max-w-full rounded"
            loading="lazy"
          />
        ),
        p: ({ children }) => <p className="my-1.5 leading-relaxed first:mt-0 last:mb-0">{children}</p>,
        ol: ({ children }) => <ol className="my-2 list-decimal pl-6">{children}</ol>,
        ul: ({ children }) => <ul className="my-2 list-disc pl-6">{children}</ul>,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
        h1: ({ children }) => <h3 className="my-2 text-lg font-semibold">{children}</h3>,
        h2: ({ children }) => <h3 className="my-2 text-base font-semibold">{children}</h3>,
        h3: ({ children }) => <h3 className="my-2 text-base font-semibold">{children}</h3>,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}
