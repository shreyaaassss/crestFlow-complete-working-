# CrestFlow — Invisible Platform Profit: Detailed Implementation Plan

## Context & Design Philosophy

CrestFlow is **not user-facing**. It is a platform-level treasury management layer embedded
inside the main Cadencia marketplace. When a buyer locks funds in escrow:

1. The buyer knows their money is "in escrow" — secure, locked, awaiting trade completion.
2. The buyer does **not** know it is being actively invested into T-bills / DeFi.
3. The platform silently earns yield on the idle float, paid to the `PLATFORM_WALLET`.

**Rule:** No public API response, no database column readable by `anon`, should ever reveal that investment/yield operations are happening.

---

## Already Done (No Action Needed)

- [x] `NETWORK` env var in `backend/src/config.ts` — auto-switches Algod URLs
- [x] `NETWORK` + `YIELD_BACKEND` env vars in `orchestrator/src/config.ts`
- [x] `EXPLORER_BASE` centralized in both configs
- [x] `orchestrator/src/services/yield-backend/interface.ts` (stub created)

---

## Changes Required

---

### A. Backend API — Response Masking

#### [MODIFY] `backend/src/routes/orders.ts`

**Problem:** `GET /orders/:id` exposes `tbill_position` (position label, maturity, yield), which reveals the investment strategy to anyone querying the API.

**Change 1 — Scrub `tbill_position` from public response:**
```ts
// BEFORE (line ~296-300):
res.json({
  order_id: orderId,
  ...order,
  tbill_position: position,       // ← REMOVE THIS
  lifecycle: { ... }
});

// AFTER:
res.json({
  order_id:       orderId,
  status:         order.status,
  buyer:          order.buyer,
  seller:         order.seller,
  amount_algo:    order.amount_algo,
  lock_days:      order.lock_days,
  created_at_ts:  order.created_at,
  // Mask: "maturity" framed as "estimated_release" — sounds operational, not financial
  estimated_release_ts: position?.maturity_unix_ts ?? null,
  lifecycle: {
    is_active:    ["PENDING","INVESTED","REDEEMED"].includes(order.status),
    is_complete:  order.status === "COMPLETED" || order.status === "CANCELLED",
    // No seconds_until_maturity, no is_matured — internal only
  },
  links: {
    escrow_explorer: `${EXPLORER_BASE}/application/${ESCROW_APP_ID}`,
    buyer_explorer:  `${EXPLORER_BASE}/address/${order.buyer}`,
  },
  // NO: yield_earned_algo, tbill_position, tbill_label, invest_txid, etc.
});
```

**Change 2 — Replace hardcoded explorer URLs:**
```ts
// BEFORE:
`https://testnet.explorer.perawallet.app/tx/${txId}`

// AFTER:
`${EXPLORER_BASE}/tx/${txId}`
```
Applies to 3 places in `orders.ts`: `/submit` response, `/orders/:id` links, `/orders/:id` lifecycle.

**Change 3 — Scrub yield from `GET /orders` list:**
The list endpoint maps orders with `{ order_id: orderId, ...order }`. The `order` object from `decodeOrder()` in `chain.ts` includes `yield_earned_algo`. Strip it from the public list response:
```ts
orders: page.map(({ orderId, order }) => ({
  order_id:    orderId,
  status:      order.status,
  buyer:       order.buyer,
  seller:      order.seller,
  amount_algo: order.amount_algo,
  lock_days:   order.lock_days,
  // NOT: yield_earned_algo, invest_txid, etc.
})),
```

---

#### [MODIFY] `backend/src/routes/account.ts`

**Problem 1 — `total_yield_algo` exposed in `/account/:address/orders`:**
Line 102 computes and returns `total_yield_algo` which sums platform profit per-user.

**Change:** Remove `total_yield_algo` from the summary:
```ts
// BEFORE:
summary: {
  total_paid_algo:  ...,
  total_yield_algo: ...,  // ← REMOVE
  by_status: ...
}

// AFTER:
summary: {
  total_transacted_algo: parseFloat(totalPaidAlgo.toFixed(6)),
  by_status: ...
}
```

**Problem 2 — `orders` list in `/account/:address/orders` includes raw `order` spread:**
Line 116: `{ order_id: orderId, ...order }` — same yield leak as orders.ts.

**Change:** Apply the same scrub filter as above.

**Problem 3 — Hardcoded explorer URL:**
Line 48: `https://testnet.explorer.perawallet.app/address/${address}`

**Change:** `${EXPLORER_BASE}/address/${address}`

---

#### [MODIFY] `backend/src/routes/platform.ts`

**Problem 1 — `/platform/stats` reveals investment details:**
Lines 34-44 return the entire `tbill` object: `total_invested`, `total_yield_paid`, `active_positions`, `yield_rate_bps`, `demo_mode`, `demo_multiplier_sec`.

**Change:** This endpoint is **internal admin only**. Add an `X-Admin-Key` middleware guard:
```ts
// Only accessible with the platform admin secret
platformRouter.get("/stats", requireAdminKey, async (_req, res) => { ... });
```
Public stats endpoint becomes:
```ts
platformRouter.get("/status", async (_req, res) => {
  // Returns only operational info — no yield data
  res.json({
    network:       NETWORK,
    escrow_active: !escrow.paused,
    total_orders:  escrow.total_orders,
    min_order_algo: escrow.min_order_amount / 1e6,
  });
});
```

**Problem 2 — `/platform/tiers` exposes financial engineering:**
Returns `apy_pct`, `yield_pct_for_period`, `asa_id`, `demo_mode`, etc. This is useful for the Cadencia marketplace to display "estimated lock duration" to buyers but must not mention yield.

**Change:** Rename yield fields to neutral operational names:
```ts
// BEFORE:
{ days, label, apy_pct, yield_pct_for_period, example_yield_10_algo, asa_id }

// AFTER (public view):
{ days, lock_label: `${days}-Day Secure Lock`, estimated_release_days: days }
// NO apy, NO yield, NO asa_id
```

**Problem 3 — Hardcoded explorer URLs:**
Lines 78 and 87: `https://testnet.explorer.perawallet.app/application/${ID}`

**Change:** `${EXPLORER_BASE}/application/${ID}`

---

#### [NEW] `backend/src/middleware/adminKey.ts`

A simple middleware to protect internal analytics routes:
```ts
import { Request, Response, NextFunction } from "express";
const ADMIN_KEY = process.env.ADMIN_API_KEY ?? "";

export function requireAdminKey(req: Request, res: Response, next: NextFunction) {
  const key = req.headers["x-admin-key"] as string | undefined;
  if (!ADMIN_KEY || key !== ADMIN_KEY) {
    res.status(403).json({ error: "Forbidden" });
    return;
  }
  next();
}
```

---

### B. Supabase RLS — Privacy Hardening

#### [MODIFY] Supabase Policies (via `mcp_supabase_apply_migration`)

**1. `tbill_positions` — Revoke all anon read access:**
Currently anon can read this table. This reveals which T-bill tier the money is in.
```sql
-- Drop existing anon read policy
DROP POLICY IF EXISTS "anon can read tbill_positions" ON tbill_positions;
-- Ensure only service_role can read
-- (service_role bypasses RLS by default — no policy needed)
```

**2. `orders` — Column-level masking via a security-definer view:**
Create a public view `public_orders` that explicitly omits financial columns:
```sql
CREATE OR REPLACE VIEW public_orders AS
SELECT
  order_id, buyer_address, seller_address,
  amount_microalgo, lock_days, status,
  created_at, completed_at
  -- NOT: yield_earned_microalgo, invest_txid, tbill_label
FROM orders;
```

**3. `platform_snapshots` — Restrict to service_role:**
Drop the anon read policy. This table contains `total_yield`, `yield_rate_bps` — internal only.
```sql
DROP POLICY IF EXISTS "anon can read platform_snapshots" ON platform_snapshots;
```

---

### C. Orchestrator — YieldBackend Abstraction

#### [NEW] `orchestrator/src/services/yield-backend/reserve.ts`
```ts
import { YieldBackend } from "./interface";

export class ReserveYieldBackend implements YieldBackend {
  // Current behaviour: TBill contract holds a pre-funded reserve.
  // invest() and redeem() calls on-chain handle everything.
  // No external DeFi interaction needed — these are intentional no-ops.
  async deposit() { /* no-op — reserve already in contract */ }
  async withdraw() { return { principal: 0, yield: 0 }; /* handled by tbill.redeem() */ }
  isSupported() { return true; }
  name() { return "on-chain-reserve"; }
}
```

#### [NEW] `orchestrator/src/services/yield-backend/folks-finance.ts`
```ts
import { YieldBackend } from "./interface";
import * as logger from "../../utils/logger";

export class FolksFinanceYieldBackend implements YieldBackend {
  async deposit(orderId: number, amount: number, tbillType: number): Promise<void> {
    // TODO (Mainnet Phase 2):
    // 1. Import @folks-finance/algo-defi-sdk
    // 2. algodClient.depositALGO(FOLKS_POOL_APP_ID, amount, orchestratorAccount)
    logger.warn(`FolksFinance.deposit() called but not yet implemented (order ${orderId})`);
    throw new Error("FolksFinance yield backend not yet implemented");
  }

  async withdraw(orderId: number): Promise<{ principal: number; yield: number }> {
    // TODO (Mainnet Phase 2): withdraw principal + yield from Folks pool
    logger.warn(`FolksFinance.withdraw() called but not yet implemented (order ${orderId})`);
    throw new Error("FolksFinance yield backend not yet implemented");
  }

  isSupported() { return false; } // ← flip to true when implemented
  name() { return "folks-finance-v2"; }
}
```

#### [NEW] `orchestrator/src/services/yield-backend/index.ts`
```ts
import { YieldBackend } from "./interface";
import { ReserveYieldBackend } from "./reserve";
import { FolksFinanceYieldBackend } from "./folks-finance";
import { YIELD_BACKEND } from "../../config";

let _instance: YieldBackend | null = null;

export function getYieldBackend(): YieldBackend {
  if (_instance) return _instance;
  switch (YIELD_BACKEND) {
    case "folks-finance": _instance = new FolksFinanceYieldBackend(); break;
    default:              _instance = new ReserveYieldBackend();
  }
  return _instance;
}
```

#### [MODIFY] `orchestrator/src/workers/investor.ts`
Add the yield backend hook after `tbill.invest()`:
```ts
import { getYieldBackend } from "../services/yield-backend";

// Inside the withRetry block, after tbill.invest():
const yb = getYieldBackend();
if (yb.name() !== "on-chain-reserve") {
  await yb.deposit(orderId, order.amount, tbillType);
}
```

#### [MODIFY] `orchestrator/src/workers/redeemer.ts`
Add the yield backend hook before `tbill.redeem()`:
```ts
import { getYieldBackend } from "../services/yield-backend";

// Inside withRetry, before tbill.redeem():
const yb = getYieldBackend();
if (yb.name() !== "on-chain-reserve") {
  await yb.withdraw(orderId); // pulls DeFi funds back to contract
}
const totalRedeemed = await tbill.redeem(orderId);
```

---

### D. .env.example Additions

Add the following new variables:

```bash
# ── Visibility / Privacy ──────────────────────────────────
# Secret key required for internal admin API endpoints
ADMIN_API_KEY=change-me-in-production

# ── Yield Backend ─────────────────────────────────────────
# "reserve" (default, current) | "folks-finance" (mainnet Phase 2)
YIELD_BACKEND=reserve

# ── Mainnet App IDs (fill in after mainnet deploy) ────────
# MAINNET_ESCROW_APP_ID=
# MAINNET_TBILL_APP_ID=
# MAINNET_TBILL_1D_ASA=
# MAINNET_TBILL_7D_ASA=
# MAINNET_TBILL_30D_ASA=
# MAINNET_PLATFORM_WALLET_ADDRESS=
```

---

## File Change Summary

| File | Action | Nature of Change |
|---|---|---|
| `backend/src/routes/orders.ts` | MODIFY | Strip tbill/yield from public responses, fix explorer URLs |
| `backend/src/routes/account.ts` | MODIFY | Strip yield from order lists, fix explorer URL |
| `backend/src/routes/platform.ts` | MODIFY | Gate `/stats` with admin key, neutralize `/tiers`, fix explorer URLs |
| `backend/src/middleware/adminKey.ts` | NEW | `requireAdminKey` middleware |
| `orchestrator/src/services/yield-backend/reserve.ts` | NEW | No-op reserve backend (wraps current behaviour) |
| `orchestrator/src/services/yield-backend/folks-finance.ts` | NEW | Stubbed Folks Finance backend |
| `orchestrator/src/services/yield-backend/index.ts` | NEW | Factory function |
| `orchestrator/src/workers/investor.ts` | MODIFY | Add yield backend hook (2 lines) |
| `orchestrator/src/workers/redeemer.ts` | MODIFY | Add yield backend hook (2 lines) |
| `Supabase` (via MCP migration) | MODIFY | Drop anon policies on `tbill_positions`, `platform_snapshots`; create `public_orders` view |
| `.env.example` | MODIFY | Add `ADMIN_API_KEY`, `YIELD_BACKEND`, mainnet placeholders |

---

## What Stays Exactly the Same

> [!IMPORTANT]
> The following are **untouched** — zero changes:
> - `POST /orders/prepare` and `POST /orders/submit` (the core transaction flow)
> - `POST /auth/nonce` and `POST /auth/verify` (JWT auth)
> - All smart contract TEAL code
> - The Orchestrator polling loop and worker order-of-execution
> - Supabase schema (tables, columns — only RLS policies change)
> - The E2E test scripts

---

## Verification Plan

After implementing:
1. Run `python scripts/test_system_e2e.py` — all 60 tests should still pass
2. Manually call `GET /orders/:id` → confirm no `tbill_position` or `yield` in response
3. Call `GET /platform/stats` without admin key → confirm `403 Forbidden`
4. Call `GET /platform/stats` with `X-Admin-Key` header → confirm internal stats visible
5. Query Supabase `tbill_positions` with anon key → confirm empty result (RLS blocks)
