import { Link } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth";
import { shortAddr } from "@/lib/format";

export function TopNav() {
  const { isConnected, address, disconnect, connecting } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--hairline)] bg-[var(--canvas)]/95 backdrop-blur">
      <div className="container-editorial flex h-16 items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <svg className="h-7 w-7" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M22 8a9 9 0 1 0 0 12" stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" />
            <path d="M11 17l4-4 4 4 5-5" stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="text-[15px] font-medium tracking-tight text-[var(--ink)]">
            CrestFlow
          </span>
        </Link>

        <nav className="hidden items-center gap-7 md:flex">
          <Link to="/" className="text-sm text-[var(--body)] [&.active]:text-[var(--ink)]" activeOptions={{ exact: true }}>
            Home
          </Link>
          <Link to="/orders" className="text-sm text-[var(--body)] [&.active]:text-[var(--ink)]">
            Orders
          </Link>
          <Link to="/dashboard" className="text-sm text-[var(--body)] [&.active]:text-[var(--ink)]">
            Dashboard
          </Link>
          <Link to="/admin" className="text-sm text-[var(--body)] [&.active]:text-[var(--ink)]">
            Admin
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {isConnected ? (
            <>
              <span className="badge hidden sm:inline-flex">
                <span className="badge-dot" />
                {shortAddr(address)}
              </span>
              <button onClick={disconnect} className="btn-secondary !py-2 !px-3 !text-sm">
                Disconnect
              </button>
            </>
          ) : (
            <Link to="/connect" className="btn-primary !py-2.5 !px-4 !text-sm">
              {connecting ? "Connecting…" : "Connect wallet"}
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
