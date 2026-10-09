import { ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";

interface Props {
  children?: ReactNode;
}

/** Exam-flow routes render full-bleed: no chrome, no footer — like a real test. */
const EXAM_ROUTES = [/^\/doc\/\d+\/practice$/, /^\/session\/\d+\/result$/, /^\/doc\/\d+\/answers$/];

/**
 * App shell. Batch 17 removed the top navigation bar (SATeacher + Import /
 * Library / Settings) entirely: management lives behind the home page's
 * unobtrusive "Manage" link, and the exam flow must feel like a real test.
 */
export function AppShell({ children }: Props) {
  const { pathname } = useLocation();
  const exam = EXAM_ROUTES.some((re) => re.test(pathname));

  if (exam) {
    return (
      <div className="min-h-screen bg-slate-100">
        <main id="main-content">{children ?? <Outlet />}</main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <main className="flex-1" id="main-content">
        {children ?? <Outlet />}
      </main>

      <footer className="border-t border-slate-200 bg-white py-4">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500">
          SATeacher — Local-first SAT practice tool. Built with React 19, FastAPI, and SQLite.
        </div>
      </footer>
    </div>
  );
}
