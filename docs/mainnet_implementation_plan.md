# CrestFlow — Mainnet Stub Implementation Plan

## Objective

Introduce a **`NETWORK` environment variable** (`testnet` | `mainnet`) that acts as the single switch for the entire system. When flipped to `mainnet`, all network-specific values (Algod endpoints, explorer URLs, App IDs, demo flags) resolve to their mainnet equivalents **with zero code changes needed at flip time**. The current testnet flow is completely untouched.

The yield-backing integration (Folks Finance) is **stubbed as a no-op** in the `tbill.ts` service — same interface, real implementation left TODO — so the orchestrator worker code never needs editing when you wire up real yield.

---

## What Actually Changes Testnet → Mainnet

| Thing | Testnet value | Mainnet value | How to handle |
|---|---|---|---|
| Algod server | `testnet-api.algonode.cloud` | `mainnet-api.algonode.cloud` | `NETWORK` env → auto-resolved in `config.ts` |
| Explorer base URL | `testnet.explorer.perawallet.app` | `explorer.perawallet.app` | Same config resolution |
| ESCROW_APP_ID | `762218790` | TBD after mainnet deploy | Separate env var |
| TBILL_APP_ID | `762214340` | TBD after mainnet deploy | Separate env var |
| ASA IDs | 7 testnet IDs | 7 mainnet IDs | Separate env vars |
| `demo_mode` flag | ON in contract | OFF in mainnet contract | Contract-level, not code |
| Yield backing | Pre-funded reserve | Folks Finance / real yield | **Stubbed as no-op** now |
| Platform wallet | Testnet address | Mainnet address | Separate env var |

**Nothing in the order lifecycle, orchestrator workers, or API routes changes.** Only config values swap.

---

## Proposed Changes

### Component: Shared Network Config

#### [MODIFY] `backend/src/config.ts`
- Add `NETWORK = opt("NETWORK", "testnet")` — default stays testnet
- Derive `ALGOD_SERVER` from `NETWORK` if not explicitly overridden
- Export `EXPLORER_BASE` URL derived from `NETWORK`
- Export `IS_MAINNET` boolean flag

#### [MODIFY] `orchestrator/src/config.ts`
- Same `NETWORK` resolution as backend
- Derive `ALGOD_SERVER` and `INDEXER_SERVER` from `NETWORK`
- Export `IS_MAINNET`

---

### Component: Explorer URL Centralisation

#### [MODIFY] `backend/src/routes/orders.ts`
- Replace hardcoded `testnet.explorer.perawallet.app` strings with `EXPLORER_BASE` from config
- Affects 2 lines in `GET /orders/:id` response

#### [MODIFY] `backend/src/routes/account.ts`
- Replace hardcoded explorer URL in account info response

#### [MODIFY] `backend/src/routes/platform.ts`
- Replace hardcoded explorer URLs in `/platform/config` response

---

### Component: Yield-Backing Stub

#### [NEW] `orchestrator/src/services/yield-backend/interface.ts`
```ts
export interface YieldBackend {
  deposit(orderId: number, amountMicroAlgo: number, tbillType: number): Promise<void>;
  withdraw(orderId: number): Promise<{ principal: number; yield: number }>;
  isSupported(): boolean;
  name(): string;
}
```

#### [NEW] `orchestrator/src/services/yield-backend/reserve.ts`
The current behaviour: yield is pre-funded in the TBill contract reserve. **This is the active implementation** — just wrapped in the interface.
```ts
export class ReserveYieldBackend implements YieldBackend {
  // deposit() → no-op (funds already in contract reserve)
  // withdraw() → no-op (tbill.redeem() handles it on-chain)
  isSupported() { return true; }
  name() { return "on-chain-reserve"; }
}
```

#### [NEW] `orchestrator/src/services/yield-backend/folks-finance.ts`
The future mainnet implementation. **Stubbed with TODO markers now.**
```ts
export class FolksFinanceYieldBackend implements YieldBackend {
  async deposit(orderId, amount, tbillType) {
    // TODO: Folks Finance v2 SDK deposit call
    // ff.deposit(ALGO_POOL_APP_ID, amount, orchestratorAccount)
    throw new Error("FolksFinance backend not yet implemented");
  }
  async withdraw(orderId) {
    // TODO: Folks Finance v2 SDK withdraw call
    throw new Error("FolksFinance backend not yet implemented");
  }
  isSupported() { return false; } // flip to true when implemented
  name() { return "folks-finance-v2"; }
}
```

#### [NEW] `orchestrator/src/services/yield-backend/index.ts`
Factory that selects the right backend based on `NETWORK` and `YIELD_BACKEND` env:
```ts
export function getYieldBackend(): YieldBackend {
  const backend = process.env.YIELD_BACKEND ?? "reserve";
  if (backend === "folks-finance") return new FolksFinanceYieldBackend();
  return new ReserveYieldBackend(); // default — current behaviour
}
```

#### [MODIFY] `orchestrator/src/workers/investor.ts`
Add a hook point (no logic change):
```ts
// After tbill.invest() succeeds on-chain:
const yb = getYieldBackend();
if (yb.isSupported() && yb.name() !== "on-chain-reserve") {
  await yb.deposit(orderId, order.amount, tbillType);
}
```

#### [MODIFY] `orchestrator/src/workers/redeemer.ts`
Add a hook point (no logic change):
```ts
// Before tbill.redeem():
const yb = getYieldBackend();
if (yb.isSupported() && yb.name() !== "on-chain-reserve") {
  await yb.withdraw(orderId); // brings funds back to TBill contract
}
// then existing tbill.redeem() runs as normal
```

---

### Component: .env Additions

#### [MODIFY] `.env.example`
Add the new variables with clear testnet defaults and mainnet placeholders:
```bash
# ── Network ──────────────────────────────────────────────
# "testnet" (default) | "mainnet"
NETWORK=testnet

# ── Yield Backend ─────────────────────────────────────────
# "reserve" (default, current) | "folks-finance" (mainnet Phase 2)
YIELD_BACKEND=reserve

# ── Mainnet App IDs (fill in after mainnet deploy) ────────
# MAINNET_ESCROW_APP_ID=
# MAINNET_TBILL_APP_ID=
# MAINNET_TBILL_1D_ASA=
# MAINNET_TBILL_3D_ASA=
# MAINNET_TBILL_7D_ASA=
# MAINNET_TBILL_14D_ASA=
# MAINNET_TBILL_30D_ASA=
# MAINNET_TBILL_60D_ASA=
# MAINNET_TBILL_90D_ASA=
# MAINNET_PLATFORM_WALLET_ADDRESS=
# MAINNET_ORCHESTRATOR_MNEMONIC=
```

---

## Flip-to-Mainnet Checklist (Future)

When ready for mainnet, these are the **only steps needed**:

```
[ ] Deploy contracts to Algorand Mainnet (same TEAL, same ABI)
[ ] Create 7 cTBILL ASAs on mainnet
[ ] Fill in MAINNET_* env vars in .env
[ ] Set NETWORK=mainnet in .env
[ ] Set NETWORK=mainnet in Railway/Vercel environment
[ ] Set demo_mode=False in mainnet contract (admin call)
[ ] (Phase 2) Set YIELD_BACKEND=folks-finance + implement FolksFinanceYieldBackend
[ ] Run test_system_e2e.py against mainnet backend
[ ] Done
```

No other code changes required.

---

## What is NOT Changing

> [!IMPORTANT]
> The following are explicitly **left untouched** by this plan:
> - All 5 API route files (`orders.ts`, `auth.ts`, `account.ts`, `platform.ts`)
> - All 3 orchestrator worker files (`investor.ts`, `redeemer.ts`, `completer.ts`)
> - All smart contract TEAL/PyTeal code
> - The Supabase schema
> - The E2E test scripts
> - The nonce auth flow
> - JWT handling

---

## Open Questions

> [!NOTE]
> **Mainnet App IDs are TBD** — they'll only exist after you deploy. The plan uses separate `MAINNET_*` prefixed vars so testnet and mainnet configs can coexist in the same `.env` during transition.

> [!NOTE]
> **Folks Finance stub**: Should `deposit()` throw or silently log a warning when not implemented? Currently planned to throw, which surfaces misconfig immediately. Change to warn-and-continue if you prefer graceful degradation.
