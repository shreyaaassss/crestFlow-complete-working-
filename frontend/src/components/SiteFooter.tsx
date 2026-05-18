import { Link } from "@tanstack/react-router";

export function SiteFooter() {
  return (
    <footer className="border-t border-[var(--hairline)] bg-[var(--canvas)]">
      <div className="container-editorial section-y grid gap-10 md:grid-cols-5">
        <div className="md:col-span-2">
          <div className="flex items-center gap-2.5">
            <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M19 8L12 4L5 8v8l7 4 7-4" stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M3 12c3-3 6-3 9 0s6 3 9 0" stroke="var(--link)" strokeWidth="2.5" strokeLinecap="round" />
            </svg>
            <span className="text-[15px] font-semibold text-[var(--ink)]">CrestFlow</span>
          </div>
          <p className="mt-4 max-w-sm text-sm text-[var(--muted)]">
            Non-custodial T-Bill yield engine on Algorand. Lock, invest, redeem — all on-chain.
          </p>
        </div>

        <Col title="Product" links={[
          { to: "/orders", label: "Order explorer" },
          { to: "/orders/new", label: "New order" },
          { to: "/dashboard", label: "Dashboard" },
        ]} />
        <Col title="Platform" links={[
          { to: "/admin", label: "Admin console" },
          { to: "/connect", label: "Connect wallet" },
        ]} />
        <Col title="Resources" links={[
          { to: "/", label: "How it works" },
        ]} />
      </div>
      <div className="border-t border-[var(--hairline)]">
        <div className="container-editorial flex h-14 items-center justify-between text-xs text-[var(--muted)]">
          <span>© {new Date().getFullYear()} CrestFlow. All rights reserved.</span>
          <span>Algorand testnet</span>
        </div>
      </div>
    </footer>
  );
}

function Col({ title, links }: { title: string; links: { to: string; label: string }[] }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wider text-[var(--ink)]">{title}</div>
      <ul className="mt-4 space-y-2">
        {links.map((l) => (
          <li key={l.to}>
            <Link to={l.to as any} className="text-sm text-[var(--muted)] hover:text-[var(--ink)]">
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
