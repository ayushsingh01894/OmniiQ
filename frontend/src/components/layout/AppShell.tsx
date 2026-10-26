import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../../features/auth/AuthProvider";
import { Button } from "../ui/Button";

const plannedModules = ["Analytics Studio", "ML Lab", "Document AI", "Workflow Studio"];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-sm px-2 py-1.5 text-sm font-medium ${
    isActive ? "bg-accent-soft text-accent" : "text-ink hover:bg-paper"
  }`;

export function AppShell() {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-full flex-col md:flex-row">
      <aside className="flex flex-col border-b border-line bg-surface md:w-60 md:shrink-0 md:border-r md:border-b-0">
        <div className="px-5 py-5 text-xl font-semibold tracking-tight">OmniIQ</div>
        <nav aria-label="Main" className="flex-1 px-3 pb-4">
          <ul className="space-y-1">
            <li>
              <NavLink to="/" end className={linkClass}>
                Overview
              </NavLink>
            </li>
            <li>
              <NavLink to="/projects" className={linkClass}>
                Projects
              </NavLink>
            </li>
          </ul>
          <p className="mt-5 px-2 text-sm font-medium text-muted">Not built yet</p>
          <ul className="mt-1 space-y-1">
            {plannedModules.map((name) => (
              <li
                key={name}
                aria-disabled="true"
                className="cursor-not-allowed rounded-sm px-2 py-1.5 text-sm text-muted/70"
              >
                {name}
              </li>
            ))}
          </ul>
        </nav>
        <div className="border-t border-line px-5 py-4">
          <p className="truncate text-sm font-medium">{user?.display_name}</p>
          <p className="mb-3 truncate text-sm text-muted">{user?.email}</p>
          <Button variant="secondary" onClick={logout}>
            Sign out
          </Button>
        </div>
      </aside>
      <main className="flex-1 px-6 py-8 md:px-10 md:py-10">
        <Outlet />
      </main>
    </div>
  );
}
