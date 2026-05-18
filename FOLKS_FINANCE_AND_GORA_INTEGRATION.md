# CrestFlow — Folks Finance & Gora Oracle Integration Report

> **Purpose:** Two-part document.
> 1. Full audit of where and how **Folks Finance** is referenced/implemented in the codebase today.
> 2. Architecture plan for a **Gora DQS (Algorand)** oracle stub so both protocols work together on mainnet.

---

> [!IMPORTANT]
> **Current Status (Testnet v2):** Yield is paid from a **pre-funded on-chain reserve** (`YIELD_BACKEND=reserve`).
> The Folks Finance and Tinyman integrations are **stubs** — they exist in the codebase with full
> implementation guides but are not activated. The swap UI widget has been **removed** from the
> order creation flow because it was misleading: swap is an internal investment mechanism, not a
> user payout preference.
>
> **Mainnet Investment Flow (Phase 2):**
> ```
> User locks ALGO in escrow
>    ↓  Orchestrator calls Tinyman v2 (SWAP_BACKEND=tinyman)
> ALGO → USDC
>    ↓  Orchestrator deposits into Folks Finance ALGO/USDC pool (YIELD_BACKEND=folks-finance)
> USDC earning ~3–5% APY from Folks Finance
>    ↓  At T-Bill maturity: orchestrator withdraws from Folks Finance
> USDC (principal + real yield)
>    ↓  Orchestrator swaps back via Tinyman
> ALGO → returned to seller
> ```
> To activate: set `YIELD_BACKEND=folks-finance` and `SWAP_BACKEND=tinyman` in production env
> and implement the two stubs listed in Section 1.2 and Section 2.

---

## PART 1 — Folks Finance Audit

### 1.1 What is Folks Finance (in this context)?

Folks Finance v2 is an Algorand-native DeFi lending protocol.  
CrestFlow intends to use it as a **yield backend** — idle ALGO locked inside the TBill contract
during an order's lock period would be deposited into the Folks Finance ALGO lending pool
(`fAlgo`) to earn ~3–5% APY. On maturity the platform withdraws principal + yield back to
the TBill contract before executing `tbill.redeem()`.

The SDK entry-point would be `@folks-finance/algo-defi-sdk`.

---

### 1.2 File-by-File Location Map

| # | File | Role | Status |
|---|------|------|--------|
| 1 | `orchestrator/src/services/yield-backend/interface.ts` | Defines the `YieldBackend` contract every backend must satisfy | ✅ Production |
| 2 | `orchestrator/src/services/yield-backend/reserve.ts` | Default no-op backend (on-chain reserve) | ✅ Production |
| 3 | `orchestrator/src/services/yield-backend/folks-finance.ts` | **Folks Finance stub** | 🟡 Stub (throws) |
| 4 | `orchestrator/src/services/yield-backend/index.ts` | Factory — reads `YIELD_BACKEND` env var | ✅ Production |
| 5 | `orchestrator/src/workers/investor.ts` | Calls `yb.deposit()` after `tbill.invest()` | ✅ Production hook |
| 6 | `orchestrator/src/workers/redeemer.ts` | Calls `yb.withdraw()` before `tbill.redeem()` | ✅ Production hook |
| 7 | `orchestrator/src/config.ts` | Exports `YIELD_BACKEND` from env | ✅ Production |
| 8 | `README.md` (line 462, 740, 742) | Documents the stub and env-flip strategy | 📄 Docs |

---

### 1.3 The `YieldBackend` Interface

**File:** `orchestrator/src/services/yield-backend/interface.ts`

```typescript
export interface YieldBackend {
  deposit(orderId: number, amountMicroAlgo: number, tbillType: number): Promise<void>;
  withdraw(orderId: number): Promise<{ principal: number; yield: number }>;
  isSupported(): boolean;
  name(): string;
}
```

**Design decision:** Deliberately minimal — any future DeFi protocol (Tinyman, Vestige, etc.)
can be plugged in by implementing just these 4 methods.

---

### 1.4 The Folks Finance Stub

**File:** `orchestrator/src/services/yield-backend/folks-finance.ts`

Key points:
- `isSupported()` returns `false` — a safety guard preventing accidental activation.
- Both `deposit()` and `withdraw()` throw immediately.
- TODO comments document the exact 3-step SDK integration path:
  1. `import { FolksFinance } from "@folks-finance/algo-defi-sdk"`
  2. `const ff = new FolksFinance({ algodClient, indexerClient, network: "mainnet" })`
  3. `await ff.deposit(FOLKS_ALGO_POOL_APP_ID, amount, orchestratorAccount)`
- `name()` returns `"folks-finance-v2"`.

---

### 1.5 The Factory / Router

**File:** `orchestrator/src/services/yield-backend/index.ts`

```typescript
// YIELD_BACKEND=reserve       → ReserveYieldBackend (default, testnet)
// YIELD_BACKEND=folks-finance → FolksFinanceYieldBackend (mainnet Phase 2)
export function getYieldBackend(): YieldBackend {
  if (_instance) return _instance;
  switch (YIELD_BACKEND) {
    case "folks-finance":
      _instance = new FolksFinanceYieldBackend();
      break;
    default:
      _instance = new ReserveYieldBackend();
  }
  return _instance;
}
```

Singleton pattern — one backend per process. Switching only requires `.env` change + restart.

---

### 1.6 How Workers Invoke the Backend

#### Investor Worker — `orchestrator/src/workers/investor.ts`
Called on `PENDING → INVESTED` transition:
1. `tbill.invest()` records position on-chain
2. `yb.deposit()` — would move ALGO to Folks Finance lending pool
3. `escrow.markInvested()` updates order state

The guard `if (yb.name() !== "on-chain-reserve")` ensures the no-op reserve backend
is never called through the DeFi path.

#### Redeemer Worker — `orchestrator/src/workers/redeemer.ts`
Called on maturity (`INVESTED → REDEEMED`):
1. `yb.withdraw()` — would redeem fAlgo → ALGO+yield back to TBill contract
2. `tbill.redeem()` executes on-chain
3. Yield flows to `PLATFORM_WALLET`

---

### 1.7 Environment Variable Wiring

| Variable | Default | Mainnet Value |
|----------|---------|---------------|
| `YIELD_BACKEND` | `reserve` | `folks-finance` |
| `NETWORK` | `testnet` | `mainnet` |
| `FOLKS_ALGO_POOL_APP_ID` | *(not yet defined)* | Folks Finance v2 ALGO pool App ID |

---

### 1.8 Current Status

| Aspect | Status |
|--------|--------|
| Interface defined | ✅ Complete |
| Factory/router | ✅ Complete |
| Worker hooks (invest + redeem) | ✅ Complete |
| Reserve backend (default) | ✅ Complete |
| Folks Finance stub class | 🟡 Stub — throws on call |
| `@folks-finance/algo-defi-sdk` installed | ❌ Not yet |
| `isSupported()` returns `true` | ❌ Blocked until SDK integrated |
| Mainnet ALGO pool App ID configured | ❌ Needs env var |

> **To activate on mainnet:** Install SDK → implement `deposit()`/`withdraw()` →
> add `FOLKS_ALGO_POOL_APP_ID` env var → flip `isSupported()` → set `YIELD_BACKEND=folks-finance`.

---

*— Part 1 complete. —*

---

## PART 2 — Gora DQS (Algorand) Oracle Stub — Integration Architecture

### 2.1 What is Gora DQS on Algorand?

Gora is a decentralised oracle network that lets Algorand smart contracts query **any external data source** — price feeds, REST APIs, or off-chain computation — through a proof-of-stake consensus layer.

DQS (Developer Quick Start) is Gora's Algorand-specific SDK and example suite. The key integration points are:

| Gora Concept | CrestFlow Use-case |
|---|---|
| **Classic oracle (Type 1)** | Fetch live ALGO/USD price to validate order amounts |
| **General URL oracle (Type 2)** | Fetch Folks Finance fAlgo APY from their API on-chain |
| **Off-chain computation (Type 3)** | Run yield calculation WASM off-chain before committing |
| **Main App ID** | `439550742` (testnet) — the Gora entry-point contract |

---

### 2.2 Where Gora Fits in the CrestFlow Architecture

```
Orchestrator (Node.js)
  └── investor.ts
        └── getYieldBackend()  ← TODAY: reserve / folks-finance
              ↓  MAINNET PHASE 2 ADDITION
        └── getOracleBackend() ← NEW: gora oracle stub
              ├── fetchAlgoUsdPrice()   → Gora Type 1 classic request
              ├── fetchFolksFinanceApy() → Gora Type 2 URL request
              └── validateOrderValue()  → price × amount sanity check
```

Gora is **orthogonal** to Folks Finance:
- **Folks Finance** = where idle ALGO earns yield (capital routing)
- **Gora** = trusted source of truth for prices and APY data (oracle data)

They are designed to be used **together** on mainnet:

```
Order Created
  → Gora fetches live ALGO/USD price            (oracle truth)
  → Validates order amount is above min USD value
  → Gora fetches Folks Finance fAlgo APY         (oracle truth)
  → Orchestrator deposits ALGO to Folks Finance  (capital routing)
  → On maturity: Gora confirms Folks Finance pool state
  → Orchestrator withdraws from Folks Finance    (capital routing)
  → Yield calculated and routed to platform wallet
```

---

### 2.3 Gora Classic Oracle — How it Works on Algorand

A request is encoded as an Algorand ABI tuple and sent to the Gora main smart contract:

```typescript
// Request spec ABI structure (Type 1 — classic)
tuple(source_spec[], aggregation, user_data)
  source_spec = tuple(source_id: uint32, source_args: byte[][], max_age: uint32)
  aggregation = uint32  // 0=none, 1=max, 2=min, 3=average
  user_data   = byte[]
```

Gora nodes pick up the request, fetch from pre-defined sources, reach PoS consensus,
then call back the destination smart contract method with the result.

**For ALGO/USD price (source_id = predefined by Gora):**
```typescript
const sourceSpec = [sourceId, [Buffer.from("algo"), Buffer.from("usd")], 3600];
const requestSpec = requestSpecType.encode([[sourceSpec], 3 /* average */, Buffer.from("crestflow")]);
```

---

### 2.4 Gora Type 2 — General URL Request for Folks Finance APY

For fetching live Folks Finance lending pool APY:

```typescript
// Source spec for Type 2 (General URL)
{
  url:        "https://api.folksfinance.com/v2/pools/algo",
  value_expr: "jsonpath:$.supplyApy",   // extract APY from JSON response
  max_age:    3600,                       // cache for 1 hour
  value_type: 1,                          // numeric
  round_to:   4                           // 4 decimal places
}
```

This lets the on-chain TBill contract verify that the APY used for yield calculation
matches the real Folks Finance pool rate — fully trustless.

---

### 2.5 The Stub Plan — New Files to Create

Mirroring the `yield-backend` pattern, we create an `oracle-backend` service:

```
orchestrator/src/services/oracle-backend/
  ├── interface.ts        ← OracleBackend interface
  ├── mock.ts             ← Testnet stub (returns hardcoded values)
  ├── gora.ts             ← Gora DQS implementation (mainnet)
  └── index.ts            ← Factory: ORACLE_BACKEND=mock|gora
```

---

### 2.6 `OracleBackend` Interface (to create)

```typescript
// orchestrator/src/services/oracle-backend/interface.ts
export interface OracleBackend {
  /**
   * Returns the current ALGO/USD price.
   * Used to sanity-check order amounts before investing.
   */
  getAlgoUsdPrice(): Promise<number>;

  /**
   * Returns the current Folks Finance ALGO lending pool APY (as decimal, e.g. 0.045).
   * Used to project yield and optionally validate on-chain rate.
   */
  getFolksFinanceAlgoApy(): Promise<number>;

  /** Unique name for logging and routing. */
  name(): string;
}
```

---

### 2.7 Mock Oracle Backend — Testnet Stub (to create)

```typescript
// orchestrator/src/services/oracle-backend/mock.ts
export class MockOracleBackend implements OracleBackend {
  async getAlgoUsdPrice(): Promise<number> {
    // Hardcoded testnet price — no real oracle call
    return 0.18; // $0.18 per ALGO (example)
  }

  async getFolksFinanceAlgoApy(): Promise<number> {
    // Hardcoded testnet APY — mirrors CadenciaTBill yield_rate_bps=500
    return 0.05; // 5% APY
  }

  name(): string { return "mock-oracle"; }
}
```

**Why this approach:**
- Testnet has no live Gora node with real price data.
- Keeps the worker pipeline testable without real oracle dependency.
- Swap to `gora` backend on mainnet via single env var.

---

### 2.8 Gora Oracle Backend — Mainnet Implementation (to create)

```typescript
// orchestrator/src/services/oracle-backend/gora.ts
import algosdk from "algosdk";
import { algodClient, orchestratorAccount } from "../../config";

const GORA_MAIN_APP_ID = parseInt(process.env.GORA_MAIN_APP_ID || "0");
const GORA_DEST_APP_ID = parseInt(process.env.GORA_DEST_APP_ID || "0");

export class GoraOracleBackend implements OracleBackend {

  async getAlgoUsdPrice(): Promise<number> {
    // 1. Build ABI-encoded request spec (Type 1 — classic source)
    const requestSpec = encodeClassicRequest({
      sourceId: GORA_ALGO_USD_SOURCE_ID,   // pre-defined Gora source
      args: [Buffer.from("algo"), Buffer.from("usd")],
      maxAge: 300,                          // 5 minutes
      aggregation: 3,                       // average across nodes
    });

    // 2. Submit request to Gora main smart contract
    const reqId = await submitGoraRequest(requestSpec, "handle_algo_price");

    // 3. Poll destination app for callback result (up to 60s)
    const result = await waitForGoraCallback(reqId, 60_000);

    // 4. Decode 17-byte numeric oracle return value
    return decodeGoraNumeric(result);
  }

  async getFolksFinanceAlgoApy(): Promise<number> {
    // Type 2 — General URL request to Folks Finance API
    const requestSpec = encodeUrlRequest({
      url: "https://api.folksfinance.com/v2/pools/algo",
      valueExpr: "jsonpath:$.supplyApy",
      maxAge: 3600,
      valueType: 1,   // numeric
      roundTo: 4,
    });

    const reqId = await submitGoraRequest(requestSpec, "handle_ff_apy");
    const result = await waitForGoraCallback(reqId, 60_000);
    return decodeGoraNumeric(result);
  }

  name(): string { return "gora-dqs-v1"; }
}
```

---

### 2.9 Factory (to create)

```typescript
// orchestrator/src/services/oracle-backend/index.ts
// ORACLE_BACKEND=mock   → MockOracleBackend  (default, testnet)
// ORACLE_BACKEND=gora   → GoraOracleBackend  (mainnet)

export function getOracleBackend(): OracleBackend {
  if (_instance) return _instance;
  switch (ORACLE_BACKEND) {
    case "gora":
      _instance = new GoraOracleBackend();
      break;
    default:
      _instance = new MockOracleBackend();
  }
  return _instance;
}
```

---

### 2.10 How Both Integrate Together in `investor.ts` (Mainnet Flow)

```typescript
// orchestrator/src/workers/investor.ts — mainnet augmented flow
export async function investPendingOrders(): Promise<void> {
  const oracle = getOracleBackend();
  const yb     = getYieldBackend();

  const algoPrice = await oracle.getAlgoUsdPrice();         // Gora oracle
  const ffApy     = await oracle.getFolksFinanceAlgoApy();  // Gora oracle

  for (const { orderId, order } of eligible) {
    // Validate minimum USD value using oracle price
    const usdValue = (order.amount / 1e6) * algoPrice;
    if (usdValue < MIN_USD_ORDER_VALUE) {
      logger.warn(`Order ${orderId} below min USD value ($${usdValue.toFixed(2)}), skipping`);
      continue;
    }

    // Log oracle-sourced projected yield
    const projectedYield = (order.amount / 1e6) * ffApy * (lockDays / 365);
    logger.info(`Projected yield: ${projectedYield.toFixed(4)} ALGO @ ${(ffApy*100).toFixed(2)}% APY (Gora)`);

    // Invest via TBill contract
    await tbill.invest(orderId, order.amount, tbillType);

    // Deposit to Folks Finance via yield backend
    if (yb.name() !== "on-chain-reserve") {
      await yb.deposit(orderId, order.amount, tbillType); // Folks Finance
    }

    await escrow.markInvested(orderId);
    logger.info(`[oracle=${oracle.name()}] [backend=${yb.name()}]`);
  }
}
```

---

### 2.11 Environment Variables — Mainnet `.env` (full picture)

```bash
# Network
NETWORK=mainnet

# Yield backend (Folks Finance)
YIELD_BACKEND=folks-finance
FOLKS_ALGO_POOL_APP_ID=<Folks Finance v2 ALGO Pool App ID on mainnet>

# Oracle backend (Gora)
ORACLE_BACKEND=gora
GORA_MAIN_APP_ID=<Gora mainnet main app ID>
GORA_DEST_APP_ID=<Your destination app ID — receives oracle callbacks>
GORA_TOKEN_ASSET_ID=<GORA token ASA ID>
MIN_USD_ORDER_VALUE=1.0
```

**Testnet `.env` (no changes needed to existing keys):**
```bash
NETWORK=testnet
YIELD_BACKEND=reserve
ORACLE_BACKEND=mock     ← new, defaults to mock if absent
```

---

*— Part 2 complete. Part 3 (implementation checklist) below. —*

---

## PART 3 — Implementation Checklist, Gora Decoding & Migration Phases

### 3.1 Gora Numeric Response Decoding

Gora returns numeric oracle values as a **17-byte array**. Structure:

| Byte(s) | Meaning |
|---|---|
| `0` | Type: `0`=NaN, `1`=positive, `2`=negative |
| `1–8` | Integer part (big-endian uint64) |
| `9–17` | Decimal fraction part (big-endian uint64) |

**TypeScript decoder utility (to add to `orchestrator/src/utils/gora.ts`):**

```typescript
export function decodeGoraNumeric(raw: Uint8Array): number {
  if (raw.length !== 17) throw new Error(`Invalid Gora numeric: expected 17 bytes, got ${raw.length}`);
  const type    = raw[0];
  if (type === 0) return NaN;
  const intPart = Number(new DataView(raw.buffer, 1, 8).getBigUint64(0));
  const decPart = Number(new DataView(raw.buffer, 9, 8).getBigUint64(0));
  // decPart is the fractional part scaled to uint64 max
  const value   = intPart + decPart / Number(BigInt(2) ** BigInt(64));
  return type === 2 ? -value : value;
}
```

**Example:** `0x011000000000000000ff00000000000000`  
decodes as a positive number where integer = 0x10 = 16, fraction part = 0xff... ≈ 16.255 ✓

---

### 3.2 Gora ABI Encoding Helpers (to add to `orchestrator/src/utils/gora.ts`)

```typescript
import Algosdk from "algosdk";

const BASIC_TYPES = {
  sourceArgList: new Algosdk.ABIArrayDynamicType(Algosdk.ABIType.from("byte[]")),
  sourceId:      Algosdk.ABIType.from("uint32"),
  maxAge:        Algosdk.ABIType.from("uint32"),
  userData:      Algosdk.ABIType.from("byte[]"),
  aggregation:   Algosdk.ABIType.from("uint32"),
};

const SOURCE_SPEC_TYPE = new Algosdk.ABITupleType([
  BASIC_TYPES.sourceId,
  BASIC_TYPES.sourceArgList,
  BASIC_TYPES.maxAge,
]);

export const REQUEST_SPEC_TYPE = new Algosdk.ABITupleType([
  new Algosdk.ABIArrayDynamicType(SOURCE_SPEC_TYPE),
  BASIC_TYPES.aggregation,
  BASIC_TYPES.userData,
]);

export function encodeClassicRequest(opts: {
  sourceId: number;
  args: Buffer[];
  maxAge: number;
  aggregation: number;
}): Uint8Array {
  return REQUEST_SPEC_TYPE.encode([
    [[opts.sourceId, opts.args, opts.maxAge]],
    opts.aggregation,
    Buffer.from("crestflow"),
  ]);
}
```

---

### 3.3 Full Implementation Checklist

#### A — Folks Finance (Yield Backend) — Mainnet Phase 2

```
[ ] npm install @folks-finance/algo-defi-sdk --save  (in orchestrator/)
[ ] Add FOLKS_ALGO_POOL_APP_ID to .env.example
[ ] Implement deposit() in folks-finance.ts:
      - init FolksFinance SDK with algodClient + indexerClient
      - call ff.deposit(FOLKS_ALGO_POOL_APP_ID, amountMicroAlgo, orchestratorAccount)
      - store returned fAlgo receipt keyed by orderId (in Supabase or in-memory)
[ ] Implement withdraw() in folks-finance.ts:
      - retrieve fAlgo balance for orderId
      - call ff.withdraw(FOLKS_ALGO_POOL_APP_ID, fAlgoBalance, orchestratorAccount)
      - return { principal, yield } where yield = totalReceived - principal
[ ] Flip isSupported() to return true
[ ] Add integration test: deposit → wait 30s → withdraw → assert yield > 0
[ ] Set YIELD_BACKEND=folks-finance in mainnet .env
[ ] Monitor first 3 live orders manually before full automation
```

#### B — Gora Oracle Backend — Mainnet Phase 2

```
[ ] Create orchestrator/src/services/oracle-backend/ directory
[ ] Write interface.ts (OracleBackend interface — see §2.6)
[ ] Write mock.ts     (MockOracleBackend — see §2.7)
[ ] Write gora.ts     (GoraOracleBackend skeleton — see §2.8)
[ ] Write index.ts    (factory — see §2.9)
[ ] Write utils/gora.ts (decodeGoraNumeric + encodeClassicRequest — see §3.1/3.2)
[ ] Register a destination smart contract to receive Gora callbacks
      - Deploy a minimal ARC-4 contract with handle_algo_price() and handle_ff_apy() methods
      - Fund it with GORA tokens (from Gora testnet faucet for testing)
      - Set GORA_DEST_APP_ID in .env
[ ] Get Gora main app ID from: gora info CLI tool or Gora Explorer
      - Testnet: ~439550742
      - Mainnet: check https://mainnet.base.explorer.gora.io (EVM) or Gora docs
[ ] Implement submitGoraRequest() — sends ABI-encoded spec to Gora main app
[ ] Implement waitForGoraCallback() — polls destination app box storage for result
[ ] Test with example_classic.py equivalent in TypeScript
[ ] Wire getOracleBackend() into investor.ts (see §2.10)
[ ] Add ORACLE_BACKEND=mock to .env.example
[ ] Add ORACLE_BACKEND=gora to mainnet .env
```

#### C — Config Updates

```
[ ] orchestrator/src/config.ts:
      export const ORACLE_BACKEND     = optionalEnv("ORACLE_BACKEND", "mock");
      export const GORA_MAIN_APP_ID   = parseInt(optionalEnv("GORA_MAIN_APP_ID", "0"));
      export const GORA_DEST_APP_ID   = parseInt(optionalEnv("GORA_DEST_APP_ID", "0"));
      export const MIN_USD_ORDER_VALUE = parseFloat(optionalEnv("MIN_USD_ORDER_VALUE", "0"));
      export const FOLKS_ALGO_POOL_APP_ID = parseInt(optionalEnv("FOLKS_ALGO_POOL_APP_ID", "0"));
[ ] .env.example — add all new keys with comments
[ ] README.md — update Mainnet Considerations section
```

---

### 3.4 Phased Migration Plan

| Phase | Network | YIELD_BACKEND | ORACLE_BACKEND | What changes |
|---|---|---|---|---|
| **Current (Phase 0)** | Testnet | `reserve` | *(none)* | Status quo |
| **Phase 1** | Testnet | `reserve` | `mock` | Add oracle-backend files, mock only |
| **Phase 2a** | Testnet | `reserve` | `gora` | Wire Gora on testnet, validate callbacks |
| **Phase 2b** | Testnet | `folks-finance` | `mock` | Wire Folks Finance SDK, validate deposits |
| **Phase 3** | Mainnet | `folks-finance` | `gora` | Full production — both active |

**Flip switches (only `.env` changes required):**
```bash
# Phase 1
ORACLE_BACKEND=mock

# Phase 2a (Gora testnet)
ORACLE_BACKEND=gora
GORA_MAIN_APP_ID=439550742

# Phase 2b (Folks Finance testnet)
YIELD_BACKEND=folks-finance
FOLKS_ALGO_POOL_APP_ID=<testnet pool id>

# Phase 3 (Mainnet full)
NETWORK=mainnet
YIELD_BACKEND=folks-finance
ORACLE_BACKEND=gora
```

---

### 3.5 Risk Notes

| Risk | Mitigation |
|---|---|
| Gora oracle timeout (>60s) | `waitForGoraCallback` falls back to last-known price from cache |
| Gora returns stale data | `max_age` enforced per request; reject if timestamp too old |
| Folks Finance pool dry | `withdraw()` checks available liquidity; alerts if insufficient |
| fAlgo balance mismatch | Store fAlgo receipt in Supabase `tbill_positions` at deposit time |
| Both backends fail simultaneously | Reserve backend is always the fallback; never removed from code |
| GORA token balance depleted | Monitor via `gora info` CLI; alert when below 10,000 microGORA |

---

### 3.6 Summary Diagram — Final Mainnet Architecture

```
.env (mainnet)
  NETWORK=mainnet
  YIELD_BACKEND=folks-finance
  ORACLE_BACKEND=gora

Orchestrator Poll (every 30s)
  ├─ investor.ts
  │     ├─ getOracleBackend()       →  GoraOracleBackend
  │     │     ├─ getAlgoUsdPrice()  →  Gora Type 1 (classic source)
  │     │     └─ getFolksFinanceApy() → Gora Type 2 (URL → FF API)
  │     └─ getYieldBackend()        →  FolksFinanceYieldBackend
  │           ├─ deposit()          →  FF SDK → fAlgo minted
  │           └─ tbill.invest()      →  On-chain position recorded
  │
  ├─ redeemer.ts
  │     ├─ getYieldBackend().withdraw() → FF SDK → fAlgo redeemed
  │     └─ tbill.redeem()               → On-chain settlement
  │
  └─ completer.ts
        └─ escrow.completeOrder()  → principal→seller, yield→platform
```

---

> Parts 1–3 document the existing audit and initial architecture.
> **Part 4 below** redefines the Gora workflow to exactly mirror the Folks Finance env-flag-switch pattern.

---

## PART 4 — Gora Oracle: Exact Mirror of the Folks Finance Env-Flag Pattern

### 4.1 The Canonical Pattern (Folks Finance as the reference)

The Folks Finance integration works as a **zero-touch env-flag switch**:

| Mechanism | Folks Finance (existing) | Gora Oracle (to match) |
|---|---|---|
| **Default value** | `YIELD_BACKEND=reserve` | `ORACLE_BACKEND=mock` |
| **Mainnet value** | `YIELD_BACKEND=folks-finance` | `ORACLE_BACKEND=gora` |
| **Default class** | `ReserveYieldBackend` (no-op) | `MockOracleBackend` (hardcoded) |
| **Mainnet class** | `FolksFinanceYieldBackend` (stub→real) | `GoraOracleBackend` (stub→real) |
| **Safety guard** | `isSupported()` returns `false` until implemented | `isSupported()` returns `false` until implemented |
| **Factory** | `getYieldBackend()` singleton | `getOracleBackend()` singleton |
| **Config export** | `export const YIELD_BACKEND = optionalEnv(...)` | `export const ORACLE_BACKEND = optionalEnv(...)` |
| **Switch action** | Change one `.env` line + restart | Change one `.env` line + restart |
| **Code change required** | ❌ None | ❌ None |

This is the **exact same workflow**. The only difference is the domain (yield capital vs oracle data).

---

### 4.2 Structural Correction to Earlier Plan

Parts 2 and 3 of this document described the architecture correctly but did **not** fully
emphasise that `GoraOracleBackend` must behave identically to `FolksFinanceYieldBackend` as a stub.

**The following constraints apply to `gora.ts` before mainnet activation:**

- `isSupported()` must return `false` — prevents silent activation on wrong network
- Both `getAlgoUsdPrice()` and `getFolksFinanceAlgoApy()` must throw with a message like:
  `"Gora oracle not yet implemented — set ORACLE_BACKEND=mock"`
- `name()` returns `"gora-dqs-v1"`
- The factory `getOracleBackend()` guards on `isSupported()` before returning the instance:

```
if ORACLE_BACKEND=gora but gora.isSupported() === false
  → throw Error (fail fast, same as FolksFinance pattern)
```

This means activating `ORACLE_BACKEND=gora` on testnet will throw immediately, exactly like
setting `YIELD_BACKEND=folks-finance` throws today. You cannot accidentally run a partial
implementation against real orders.

---

### 4.3 Corrected Factory Guard (replaces §2.9)

The factory must include the same `isSupported()` guard that Folks Finance has:

```
getOracleBackend():
  switch ORACLE_BACKEND:
    case "gora":
      backend = new GoraOracleBackend()
      if NOT backend.isSupported():
        throw "Gora oracle backend not yet implemented — set ORACLE_BACKEND=mock"
      return backend
    default:
      return new MockOracleBackend()   ← always safe, always succeeds
```

This mirrors the intent of `folks-finance.ts` where calling `deposit()` or `withdraw()`
on the stub throws immediately.

---

### 4.4 The `isSupported()` Lifecycle for Both Protocols

Both backends go through an identical three-stage lifecycle:

```
Stage 1 — Stub (current state for both)
  isSupported() = false
  All methods throw
  Factory rejects if env flag is set to this backend
  Safe to deploy to any environment

Stage 2 — Partial (SDK installed, one method works)
  isSupported() = false (still)
  deposit/getAlgoUsdPrice implemented
  withdraw/getFolksFinanceAlgoApy still throws
  Env flag still blocked

Stage 3 — Complete (mainnet-ready)
  isSupported() = true
  All methods fully implemented and tested
  Set YIELD_BACKEND=folks-finance / ORACLE_BACKEND=gora in .env
  No code change required — restart orchestrator
```

---

### 4.5 Updated `.env.example` Additions (plan only)

The following keys must be added to `.env.example` with their defaults and comments.
These are **documentation changes only** — no logic changes:

```
# ─── Yield Backend ──────────────────────────────────────────────────────────
# reserve        = on-chain TBill reserve (testnet default, no external calls)
# folks-finance  = deposit idle ALGO into Folks Finance v2 ALGO pool (mainnet)
YIELD_BACKEND=reserve
FOLKS_ALGO_POOL_APP_ID=    # Required when YIELD_BACKEND=folks-finance

# ─── Oracle Backend ─────────────────────────────────────────────────────────
# mock           = hardcoded values (testnet default, no real oracle calls)
# gora           = live ALGO/USD price + Folks Finance APY via Gora DQS (mainnet)
ORACLE_BACKEND=mock
GORA_MAIN_APP_ID=          # Required when ORACLE_BACKEND=gora (get via: gora info)
GORA_DEST_APP_ID=          # Required when ORACLE_BACKEND=gora (your ARC-4 callback app)
GORA_TOKEN_ASSET_ID=       # Required when ORACLE_BACKEND=gora (GORA token ASA)
MIN_USD_ORDER_VALUE=0      # Min order value in USD (0 = disabled). Enforced by oracle price.
```

---

### 4.6 Updated Workers Guard Pattern (replaces §2.10)

The worker guard for Gora must mirror the Folks Finance worker guard exactly:

**Folks Finance pattern (existing in `investor.ts`):**
```
const yb = getYieldBackend();
if (yb.name() !== "on-chain-reserve") {
  await yb.deposit(...);   // only runs when YIELD_BACKEND=folks-finance
}
```

**Gora pattern (to add to `investor.ts`):**
```
const oracle = getOracleBackend();
if (oracle.name() !== "mock-oracle") {
  const price = await oracle.getAlgoUsdPrice();   // only runs when ORACLE_BACKEND=gora
  const apy   = await oracle.getFolksFinanceAlgoApy();
  // use price + apy for validation and logging
}
```

The fallback when `ORACLE_BACKEND=mock` is that price/APY validation is simply skipped —
same philosophy as the reserve backend being a no-op for deposits.

---

### 4.7 Complete Side-by-Side Env-Flip Reference

```
TESTNET (current, no changes needed):
  NETWORK=testnet
  YIELD_BACKEND=reserve          ← ReserveYieldBackend (no-op)
  ORACLE_BACKEND=mock            ← MockOracleBackend (hardcoded values)

MAINNET PHASE 2a — Folks Finance only:
  NETWORK=mainnet
  YIELD_BACKEND=folks-finance    ← FolksFinanceYieldBackend (real SDK calls)
  ORACLE_BACKEND=mock            ← MockOracleBackend (still hardcoded, safe)
  FOLKS_ALGO_POOL_APP_ID=<id>

MAINNET PHASE 2b — Gora only (Folks Finance still reserve):
  NETWORK=mainnet
  YIELD_BACKEND=reserve
  ORACLE_BACKEND=gora            ← GoraOracleBackend (real oracle calls)
  GORA_MAIN_APP_ID=<id>
  GORA_DEST_APP_ID=<id>
  GORA_TOKEN_ASSET_ID=<id>

MAINNET PHASE 3 — Both active (target state):
  NETWORK=mainnet
  YIELD_BACKEND=folks-finance    ← FolksFinanceYieldBackend
  ORACLE_BACKEND=gora            ← GoraOracleBackend
  FOLKS_ALGO_POOL_APP_ID=<id>
  GORA_MAIN_APP_ID=<id>
  GORA_DEST_APP_ID=<id>
  GORA_TOKEN_ASSET_ID=<id>
  MIN_USD_ORDER_VALUE=1.0
```

Each phase is a **single `.env` edit + process restart**. Zero code changes.

---

> ~~End of Report (all 4 parts).~~
> Report extended with two additional parts (5 & 6) covering the ALGO→USDC asset swap
> feature and four confirmed unresolved technical debt items from the CrestFlow audit.

---

## PART 5 — Asset Swap Feature: ALGO → USDC (Tinyman v2 Integration)

### 5.1 Purpose and Context

CrestFlow currently operates entirely in ALGO. Users lock ALGO, earn yield in ALGO, and receive
ALGO back on redemption. Adding an ALGO → USDC swap layer gives users an exit ramp to a
stable asset without leaving the platform — a critical UX feature for a treasury product.

**Why Tinyman, not Folks Finance, for swaps?**  
Folks Finance v2 is a *lending protocol* — it mints/burns fAlgo positions, it does not
have a native DEX order book. Tinyman v2 is the canonical Algorand AMM DEX and is the
standard integration point for ALGO ↔ ASA swaps on Algorand mainnet. The swap feature
plugs into the Folks Finance workflow at the yield-withdrawal stage: yield is returned in
ALGO, the user opts in to auto-swap that yield (or the principal) to USDC before it hits
their wallet.

---

### 5.2 Where Swap Fits in the CrestFlow Architecture

```
Order Lifecycle (Mainnet Phase 3+)
  create_order (ALGO locked)
    ↓ orchestrator invest
  tbill.invest() + yb.deposit() [Folks Finance — ALGO → fAlgo]
    ↓ maturity
  yb.withdraw() [Folks Finance — fAlgo → ALGO+yield]
    ↓ NEW STEP (optional, user-controlled)
  swapService.swap(yieldAlgo, ALGO→USDC) [Tinyman v2]
    ↓
  escrow.completeOrder() — principal ALGO + USDC yield → seller
```

Two swap modes:
| Mode | Description |
|------|-------------|
| `yield-only` | Swap only the yield earned to USDC; principal returned as ALGO |
| `full` | Swap entire redemption (principal + yield) to USDC |

---

### 5.3 New Files to Create

```
orchestrator/src/services/swap/
  ├── interface.ts    ← SwapService interface
  ├── mock.ts         ← Testnet stub (no-op, returns input amount)
  ├── tinyman.ts      ← Tinyman v2 implementation (mainnet)
  └── index.ts        ← Factory: SWAP_BACKEND=mock|tinyman
```

**Frontend:**
```
frontend/src/components/SwapWidget.tsx   ← UI component for swap toggle
frontend/src/lib/swap.ts                 ← API helper for swap quote + execute
```

---

### 5.4 `SwapService` Interface

```typescript
// orchestrator/src/services/swap/interface.ts
export interface SwapService {
  /**
   * Get a quote for swapping microAlgo → USDC.
   * Returns expected USDC output (in micro-USDC, 6 decimals).
   */
  getQuote(microAlgoAmount: number): Promise<{ outputUsdc: number; priceImpact: number }>;

  /**
   * Execute the swap. Returns actual USDC received.
   * swapperAddress is the account whose funds are being swapped
   * (orchestrator account on behalf of platform, or user address).
   */
  swap(microAlgoAmount: number, swapperAddress: string): Promise<number>;

  /** Whether this backend is fully implemented and safe to call. */
  isSupported(): boolean;

  name(): string;
}
```

---

### 5.5 Mock Swap Backend (Testnet Stub)

```typescript
// orchestrator/src/services/swap/mock.ts
export class MockSwapService implements SwapService {
  async getQuote(microAlgoAmount: number) {
    // Hardcoded: 1 ALGO = $0.18, USDC has 6 decimals
    const algoAmount = microAlgoAmount / 1e6;
    return { outputUsdc: Math.floor(algoAmount * 0.18 * 1e6), priceImpact: 0 };
  }

  async swap(microAlgoAmount: number, _swapperAddress: string): Promise<number> {
    // No-op on testnet — return simulated output
    const { outputUsdc } = await this.getQuote(microAlgoAmount);
    return outputUsdc;
  }

  isSupported(): boolean { return true; } // mock is always safe
  name(): string { return "mock-swap"; }
}
```

---

### 5.6 Tinyman v2 Swap Backend (Mainnet)

```typescript
// orchestrator/src/services/swap/tinyman.ts
import algosdk from "algosdk";
import { algodClient, orchestratorAccount } from "../../config";

// Tinyman v2 mainnet pool validator app ID
const TINYMAN_APP_ID    = parseInt(process.env.TINYMAN_APP_ID    || "0");
// USDC ASA ID on Algorand mainnet
const USDC_ASA_ID       = parseInt(process.env.USDC_ASA_ID       || "31566704");
// Slippage tolerance (default 0.5%)
const SLIPPAGE_BPS      = parseInt(process.env.SWAP_SLIPPAGE_BPS || "50");

export class TinymanSwapService implements SwapService {

  async getQuote(microAlgoAmount: number) {
    // 1. Fetch pool info from Tinyman v2 SDK
    //    import { Tinyman } from "@tinymanorg/tinyman-js-sdk"
    //    const pool = await Tinyman.getPool(algodClient, TINYMAN_APP_ID, ALGO_ASA, USDC_ASA_ID)
    // 2. Calculate output using constant-product formula: dy = y * dx / (x + dx)
    // 3. Apply fee (0.3% for Tinyman v2 pools)
    // 4. Return output and price impact
    throw new Error("TinymanSwapService not yet implemented — set SWAP_BACKEND=mock");
  }

  async swap(microAlgoAmount: number, swapperAddress: string): Promise<number> {
    // 1. Get quote with slippage applied
    // 2. Build Tinyman v2 swap transaction group (atc — AtomicTransactionComposer)
    // 3. Sign with orchestratorAccount
    // 4. Submit and wait for confirmation
    // 5. Return actual USDC output from inner transaction log
    throw new Error("TinymanSwapService not yet implemented — set SWAP_BACKEND=mock");
  }

  isSupported(): boolean { return false; } // flip to true after implementation
  name(): string { return "tinyman-v2"; }
}
```

---

### 5.7 Factory

```typescript
// orchestrator/src/services/swap/index.ts
// SWAP_BACKEND=mock     → MockSwapService    (default, testnet)
// SWAP_BACKEND=tinyman  → TinymanSwapService (mainnet)

export function getSwapService(): SwapService {
  if (_instance) return _instance;
  switch (SWAP_BACKEND) {
    case "tinyman":
      _instance = new TinymanSwapService();
      if (!_instance.isSupported())
        throw new Error("Tinyman swap not yet implemented — set SWAP_BACKEND=mock");
      break;
    default:
      _instance = new MockSwapService();
  }
  return _instance;
}
```

---

### 5.8 Integration into `redeemer.ts` (Optional Swap on Redemption)

```typescript
// redeemer.ts — augmented redeem flow (mainnet Phase 3+)
const swap   = getSwapService();
const swapMode = order.swapPreference; // "none" | "yield-only" | "full" — stored in Supabase

let usdcYield = 0;
if (swapMode !== "none" && swap.name() !== "mock-swap") {
  const amountToSwap = swapMode === "full"
    ? totalRedeemed
    : yieldEarned;

  usdcYield = await swap.swap(amountToSwap, order.buyer);
  logger.info(`Swapped ${amountToSwap / 1e6} ALGO → ${usdcYield / 1e6} USDC [${swap.name()}]`);
}
```

---

### 5.9 Frontend SwapWidget Component Plan

A `SwapWidget` component on the order creation/dashboard page:

| Element | Description |
|---------|-------------|
| Toggle | "Auto-convert yield to USDC on maturity" (on/off) |
| Mode selector | Yield-only / Full swap |
| Live quote | Calls `/api/swap/quote?amount=N` → displays estimated USDC output |
| Slippage badge | Shows configured slippage tolerance |
| Confirmation | Saved to `swap_preference` field in Supabase `orders` table |

**API endpoint to add:**
```
GET /api/swap/quote?microAlgo=5000000
→ { outputUsdc: 900000, priceImpact: 0.12, backend: "mock-swap" }
```

---

### 5.10 New Environment Variables

```bash
# ─── Swap Backend ─────────────────────────────────────────────────────────────
# mock     = simulated quote, no real swap (testnet default)
# tinyman  = live ALGO→USDC swap via Tinyman v2 AMM (mainnet)
SWAP_BACKEND=mock
TINYMAN_APP_ID=1002541853        # Tinyman v2 validator app (mainnet)
USDC_ASA_ID=31566704             # USDC ASA on Algorand mainnet
SWAP_SLIPPAGE_BPS=50             # 50 bps = 0.5% slippage tolerance
```

---

### 5.11 Implementation Checklist — Asset Swap

```
[ ] npm install @tinymanorg/tinyman-js-sdk --save  (in orchestrator/)
[ ] Add swap_preference column to Supabase orders table:
      ALTER TABLE orders ADD COLUMN swap_preference TEXT NOT NULL DEFAULT 'none';
      -- values: 'none' | 'yield-only' | 'full'
[ ] Create orchestrator/src/services/swap/interface.ts
[ ] Create orchestrator/src/services/swap/mock.ts
[ ] Create orchestrator/src/services/swap/tinyman.ts (stub — throws)
[ ] Create orchestrator/src/services/swap/index.ts (factory)
[ ] Add SWAP_BACKEND, TINYMAN_APP_ID, USDC_ASA_ID, SWAP_SLIPPAGE_BPS to config.ts
[ ] Add /api/swap/quote endpoint to backend
[ ] Implement TinymanSwapService.getQuote() using Tinyman v2 SDK pool math
[ ] Implement TinymanSwapService.swap() — atomic txn group + sign + submit
[ ] Flip TinymanSwapService.isSupported() to true after testing
[ ] Add swap_preference field to order creation API and frontend form
[ ] Create frontend/src/components/SwapWidget.tsx
[ ] Wire SwapWidget into order dashboard / order-creation page
[ ] Integration test: mock quote → assert outputUsdc > 0
[ ] Mainnet test: real Tinyman pool quote against live ALGO/USDC pool
[ ] Set SWAP_BACKEND=tinyman in mainnet .env
```

---

### 5.12 Phased Swap Rollout

| Phase | SWAP_BACKEND | What works |
|-------|-------------|------------|
| Current | *(none)* | No swap feature |
| Phase 1 | `mock` | SwapWidget visible; quote = hardcoded $0.18/ALGO |
| Phase 2 | `mock` | Live quote from `/api/swap/quote` (still mock) |
| Phase 3 | `tinyman` | Real Tinyman v2 quotes + execution on mainnet |

---

*— Part 5 complete. —*

---

## PART 6 — Technical Debt: Confirmed Unresolved Audit Issues

> All four issues below were validated against the live codebase on 2026-05-18.
> None are resolved. Each section documents the exact code location, root cause
> confirmation, and precise fix plan.

---

### 6.1 Issue 1 — Orchestrator Kick-in Takes Too Long (> 30s)

**Status: ❌ Unresolved**

**Confirmed Location:** `orchestrator/src/index.ts` line 57–61

```typescript
// CURRENT (broken):
while (true) {
  await runCycle(cycleCount);       // takes 15-20s
  await sleep(POLL_INTERVAL_MS);    // always sleeps full 30s AFTER cycle
}
// Effective interval = cycle time (~20s) + sleep (30s) = ~50s worst case
```

**Fix: Fixed-interval scheduling (decouple cycle time from sleep time)**

```typescript
// FIXED:
while (true) {
  const cycleStart = Date.now();
  try {
    await runCycle(cycleCount++);
  } catch (err: any) {
    logger.error(`Cycle error: ${err.message}`);
  }
  const elapsed   = Date.now() - cycleStart;
  const remaining = Math.max(0, POLL_INTERVAL_MS - elapsed);
  logger.info(`Cycle took ${elapsed}ms. Next poll in ${remaining}ms.`);
  await sleep(remaining);
}
// Effective interval = always exactly POLL_INTERVAL_MS regardless of cycle time
```

**Files to change:**
- `orchestrator/src/index.ts` — replace the `while(true)` loop body

**Config change:** Lower `POLL_INTERVAL_MS` to `10000` (10s) on testnet for demo responsiveness.

---

### 6.2 Issue 2 — Order Lifecycle Takes 4-5 Min Instead of ~1 Min

**Status: ❌ Unresolved**

**Root cause:** Delays compound across three independent bottlenecks.

**Confirmed bottlenecks:**

| Stage | Current delay | Source |
|-------|--------------|--------|
| Orchestrator pickup | Up to 50s | Issue 1 (fixed by §6.1) |
| Maturity timer starts at invest time, not create time | Up to 50s of wasted lock time | `cadencia_tbill/contract.py` |
| Redeem + Complete are two separate cycles | +30-50s extra wait | `redeemer.ts` + `completer.ts` |

**Fix A — Maturity from creation block (Smart Contract)**

The TBill contract must record `invest_start` as the escrow order's `created_at` round,
not the current round when `tbill.invest()` is called. This requires passing `created_at`
from the escrow box to the TBill invest call.

```python
# cadencia_tbill/contract.py — tbill.invest() signature change:
@arc4.abimethod()
def invest(
    self,
    order_id: arc4.UInt64,
    amount: arc4.UInt64,
    tbill_type: arc4.UInt8,
    created_at_round: arc4.UInt64,   # NEW: pass escrow order creation round
) -> None:
    # Use created_at_round instead of Global.round for maturity calculation
    maturity = created_at_round.native + self.lock_durations[tbill_type.native]
    self.positions[order_id] = TBillPosition(
        ...
        invest_start=created_at_round,   # was: arc4.UInt64(Global.round)
        maturity=arc4.UInt64(maturity),
    )
```

**Fix B — Combine Redeem + Complete into a single atomic group**

Instead of two separate orchestrator cycles, `redeemer.ts` should call `completeOrder`
in the same `withRetry` block immediately after `tbill.redeem()`:

```typescript
// redeemer.ts — combined redeem+complete:
await withRetry(async () => {
  const yb = getYieldBackend();
  if (yb.name() !== "on-chain-reserve") await yb.withdraw(orderId);

  const totalRedeemed = await tbill.redeem(orderId);
  const yieldEarned   = totalRedeemed > order.amount ? totalRedeemed - order.amount : 0;
  await escrow.receiveFromTreasury(orderId, totalRedeemed);
  await escrow.markRedeemed(orderId, yieldEarned);

  // Immediately complete — no second cycle needed
  await escrow.completeOrder(orderId, order.seller);
  logger.info(`Redeemed+completed order ${orderId} in single cycle`);
}, `redeem-complete(${orderId})`);
```

**Files to change:**
- `smart_contracts/cadencia_tbill/contract.py` — add `created_at_round` param to `invest()`
- `orchestrator/src/services/tbill.ts` — pass `order.createdAt` to `tbill.invest()`
- `orchestrator/src/workers/redeemer.ts` — combine redeem + complete steps
- `orchestrator/src/workers/completer.ts` — can be simplified/removed after above change

**Expected result:** Demo 1-day lifecycle drops from 4-5 min to ~70-90s.

---

### 6.3 Issue 3 — No Clear Separation Between Admin and Normal User Dashboards

**Status: ❌ Unresolved**

**Confirmed Location:** `frontend/src/lib/auth.tsx` line 210–213

```typescript
// CURRENT (vulnerable):
const adminEmail = import.meta.env.VITE_ADMIN_EMAIL as string | undefined;
isAdmin: !!session && (!adminEmail || session.user?.email === adminEmail),
//                     ^^^^^^^^^^^
//        If VITE_ADMIN_EMAIL is missing from GitHub Secrets / AWS build args, this is TRUE for ALL users
```

**Fix A — Harden the frontend check (immediate, no DB change)**

```typescript
// auth.tsx — hardened:
const adminEmail = import.meta.env.VITE_ADMIN_EMAIL as string | undefined;
// If env var is absent, NOBODY is admin (fail-closed, not fail-open)
isAdmin: !!session && !!adminEmail && session.user?.email === adminEmail,
//                    ^^^^^^^^^^^^
//        Force false if var is missing
```

**Fix B — Migrate to RBAC via Supabase (recommended, longer term)**

1. Create a `user_roles` table in Supabase:
```sql
CREATE TABLE user_roles (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  role    TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin'))
);

-- RLS: only service role can write; users can read their own row
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users can read own role"
  ON user_roles FOR SELECT USING (auth.uid() = user_id);
```

2. Frontend reads role from the `user_roles` table on session load:
```typescript
const { data } = await supabase
  .from("user_roles")
  .select("role")
  .eq("user_id", session.user.id)
  .single();
isAdmin = data?.role === "admin";
```

3. Backend verifies role server-side (not just `ADMIN_EMAIL` env var):
```typescript
// backend: check user_roles table instead of env var email match
const { data } = await supabaseAdmin
  .from("user_roles")
  .select("role")
  .eq("user_id", userId)
  .single();
if (data?.role !== "admin") return res.status(403).json({ error: "Forbidden" });
```

**Additional steps:**
- [ ] Disable public sign-ups in Supabase Dashboard → Auth → Settings
- [x] Set `VITE_ADMIN_EMAIL` as a GitHub Secret (injected via `--build-arg` in deploy.yml) — **DONE**
- [ ] Apply Fix A immediately; schedule Fix B for next sprint

**Files to change:**
- `frontend/src/lib/auth.tsx` — Fix A (one-line change)
- Supabase migration — new `user_roles` table (Fix B)
- `backend/src/middleware/auth.ts` (or equivalent) — server-side RBAC check (Fix B)

---

### 6.4 Issue 4 — Cancel Order Flow Does Not Work for Eligible Orders

**Status: ❌ Unresolved**

**Confirmed Location:** `smart_contracts/cadencia_escrow/contract.py` lines 166–185

```python
# CURRENT (broken):
def cancel_order(self, order_id: arc4.UInt64) -> None:
    ...
    if order.invest_eligible == arc4.Bool(False):
        assert order.status == arc4.UInt8(PENDING), "INVALID_STATUS"
        # refund buyer
    else:
        assert order.status == arc4.UInt8(REDEEMED), "STILL_INVESTED"  # ← BUG
        # Any PENDING eligible order fails here — can never be cancelled
```

**Fix — Pivot on `order.status`, use `invest_eligible` only for yield distribution**

```python
# FIXED cancel_order:
@arc4.abimethod()
def cancel_order(self, order_id: arc4.UInt64) -> None:
    assert order_id in self.orders, "ORDER_NOT_FOUND"
    order = self.orders[order_id].copy()
    assert Txn.sender == self.admin or Txn.sender == order.buyer.native, "UNAUTHORIZED"

    if order.status == arc4.UInt8(PENDING):
        # Not yet invested — immediate full refund regardless of invest_eligible
        itxn.Payment(
            receiver=order.buyer.native,
            amount=order.amount.native,
            fee=UInt64(0),
        ).submit()

    elif order.status == arc4.UInt8(REDEEMED):
        # Already redeemed — refund principal + distribute yield
        itxn.Payment(
            receiver=order.buyer.native,
            amount=order.amount.native,
            fee=UInt64(0),
        ).submit()
        if order.yield_earned.native > UInt64(0):
            itxn.Payment(
                receiver=self.platform_wallet,
                amount=order.yield_earned.native,
                fee=UInt64(0),
            ).submit()

    else:
        # INVESTED or COMPLETED or CANCELLED — cannot cancel
        assert False, "CANNOT_CANCEL_IN_CURRENT_STATUS"

    self.orders[order_id] = OrderRecord(
        buyer=order.buyer, seller=order.seller, amount=order.amount,
        created_at=order.created_at, lock_until=order.lock_until,
        status=arc4.UInt8(CANCELLED),
        invest_eligible=order.invest_eligible, yield_earned=order.yield_earned,
    )
    self.total_locked -= order.amount.native
    self.active_orders -= UInt64(1)
```

**Key logic change:** The original code forked on `invest_eligible`; the fixed code forks
on `order.status`. The `invest_eligible` flag is now irrelevant to whether a cancellation
is allowed — it only matters for how yield is distributed on a post-redeem cancellation.

**After contract fix — orchestrator must also handle in-flight INVESTED orders:**

If a user tries to cancel while status is `INVESTED`, the orchestrator should:
1. Call `yb.withdraw()` (pull from Folks Finance back to TBill)
2. Call `tbill.redeem()` early
3. Then allow `cancel_order` (status will be `REDEEMED` by then)

This flow can be triggered via a `/api/orders/:id/cancel` backend endpoint.

**Files to change:**
- `smart_contracts/cadencia_escrow/contract.py` — rewrite `cancel_order` (see above)
- Re-compile + redeploy escrow contract (new App ID required)
- `backend/src/routes/orders.ts` — add early-redeem logic for INVESTED cancellations
- `frontend/src/` — update Cancel button to call the new cancel endpoint with loading state

---

### 6.5 Combined Fix Checklist (Issues 1–4)

```
ISSUE 1 — Orchestrator timing
[ ] orchestrator/src/index.ts: replace while-loop with fixed-interval scheduler
[ ] Set POLL_INTERVAL_MS=10000 in .env for demo (10s poll)

ISSUE 2 — Order lifecycle duration
[ ] smart_contracts/cadencia_tbill/contract.py: add created_at_round param to invest()
[ ] orchestrator/src/services/tbill.ts: pass order.createdAt to tbill.invest()
[ ] orchestrator/src/workers/redeemer.ts: merge completeOrder() into redeem cycle
[ ] Rebuild + redeploy TBill contract

ISSUE 3 — Admin/user separation
[ ] frontend/src/lib/auth.tsx: change !adminEmail → !!adminEmail (fail-closed)
[ ] Supabase: disable public sign-ups in Auth settings
[x] GitHub Actions: VITE_ADMIN_EMAIL set as GitHub Secret, injected via --build-arg in deploy.yml — DONE
[ ] (Phase 2) Supabase migration: create user_roles table
[ ] (Phase 2) backend auth middleware: server-side RBAC check

ISSUE 4 — Cancel order bug
[ ] smart_contracts/cadencia_escrow/contract.py: rewrite cancel_order (see §6.4)
[ ] Rebuild + redeploy Escrow contract (new App ID)
[ ] backend/src/routes/orders.ts: add early-redeem flow for INVESTED cancellations
[ ] frontend: update Cancel button with loading/error handling
```

---

> **End of Report (all 6 parts).**
> Parts 5–6 added 2026-05-18: ALGO→USDC swap via Tinyman v2 (Part 5) and four confirmed
> unresolved technical debt items with precise fix plans (Part 6). Issues 1–4 are all
> live in the codebase and require explicit fixes before production.

