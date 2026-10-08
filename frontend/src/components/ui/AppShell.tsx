import { ReactNode, useState } from "react";
import { Outlet, NavLink } from "react-router-dom";
import { Icon } from "./Icon";

interface Props {
  children?: ReactNode;
}

const NAV_ITEMS = [
  { path: "/", label: "Import", icon: "Upload" },
  { path: "/library", label: "Library", icon: "Database" },
  { path: "/settings", label: "Settings", icon: "Settings" },
] as const;

export function AppShell({ children }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Top bar */}
      <header className="sticky top-0 z-[100] bg-white border-b border-slate-200">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-16 items-center justify-between">
            {/* Logo / Brand */}
            <div className="flex items-center gap-2">
              <Icon icon="GraduationCap" size={24} className="text-primary-600" />
              <span className="text-xl font-semibold text-slate-900">SATeacher</span>
            </div>

            {/* Desktop navigation */}
            <nav className="hidden md:flex items-center gap-1" aria-label="Main navigation">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-primary-50 text-primary-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                    }`
                  }
                >
                  <Icon icon={item.icon} size={18} />
                  {item.label}
                </NavLink>
              ))}
            </nav>

            {/* Mobile menu button */}
            <button
              className="md:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100"
              onClick={() => setMobileOpen(!mobileOpen)}
              aria-expanded={mobileOpen}
              aria-controls="mobile-menu"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
            >
              <Icon icon={mobileOpen ? "X" : "Menu"} size={24} />
            </button>
          </div>

          {/* Mobile navigation drawer */}
          {mobileOpen && (
            <div id="mobile-menu" className="md:hidden py-4 border-t border-slate-200 animate-slide-down">
              <nav className="flex flex-col gap-1" aria-label="Mobile navigation">
                {NAV_ITEMS.map((item) => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2.5 rounded-lg text-base font-medium transition-colors ${
                        isActive
                          ? "bg-primary-50 text-primary-700"
                          : "text-slate-500 hover:bg-slate-100 hover:text-slate-700"
                      }`
                    }
                  >
                    <Icon icon={item.icon} size={20} />
                    {item.label}
                  </NavLink>
                ))}
              </nav>
            </div>
          )}
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1" id="main-content">
        {children ?? <Outlet />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white py-4">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 text-center text-xs text-slate-500">
          SATeacher — Local-first SAT practice tool. Built with React 19, FastAPI, and SQLite.
        </div>
      </footer>
    </div>
  );
}