# Cadencia Treasury — Mainnet Strategy

## The Core Business Model

```
Marketplace buyer locks 10,000 ALGO in escrow for a 7-day order
    ↓
Those 10,000 ALGO sit idle for 7 days — earning nothing
    ↓
Cadencia invests them into short-term instruments
    ↓
After 7 days: seller gets 10,000 ALGO, Cadencia keeps the yield
    ↓
Yield = 10,000 × 5% × 7/365 = ~9.59 ALGO profit for Cadencia
```

Scale that to thousands of orders and you have a real revenue stream.

---

## Testnet vs Mainnet — What Changes

| Layer | Testnet (Now) | Mainnet |
|---|---|---|
| Smart Contracts | Same code, same ABI | **Identical** — redeploy same TEAL |
| ASA Tokens | cTBILL-2D/7D/14D | **Identical** — same ASAs, mainnet IDs |
| Orchestrator | Same Node.js service | **Identical** — change endpoint to mainnet |
| Demo Mode | ON (7 days = 7 minutes) | **OFF** (real time enforcement) |
| Yield Source | Pre-funded ALGO reserve | **Real yield backing** (see below) |
| Explorer | testnet.explorer.perawallet.app | explorer.perawallet.app |

**The only real difference is where the yield comes from.**

---

## Mainnet Yield Source — Three Options

### Option 1: Folks Finance v2 Mainnet (Simplest)

```
Escrow ALGO → CadenciaTBill contract
    → Orchestrator deposits into Folks Finance ALGO lending pool (mainnet)
    → Earns real variable yield (~3-5% APY)
    → At maturity: withdraw principal + real yield
    → Pay seller, keep yield
```

Folks Finance mainnet is live, liquid, and battle-tested. Their mainnet SDK works. This is the path of least resistance.

### Option 2: Institutional T-Bill Custodian (Most Impressive)

```
Escrow ALGO → Swap to USDC via Tinyman/Pact
    → Bridge USDC to Ethereum/Solana
    → Deposit into Ondo Finance (USDY) or OpenEden (TBILL)
    → Earns real US Treasury yield (~5% APY)
    → At maturity: redeem, bridge back, swap to ALGO
    → Pay seller, keep yield
```

This is the "real T-bill" story but adds bridging complexity and counterparty risk.

### Option 3: Hybrid (Recommended for Mainnet v1)

```
Escrow ALGO → Split:
    70% → Folks Finance ALGO lending (real DeFi yield, instant)
    30% → ALGO liquid staking or governance rewards
    → Blended yield: ~4-5% APY
    → No bridging, no custodian dependency
    → All on Algorand
```

---

## The Full Mainnet Flow

```
BUYER (Pera Wallet)
  │
  │ create_order(10,000 ALGO, seller, 7-day lock)
  ▼
┌──────────────────┐
│  CadenciaEscrow  │ ← 10,000 ALGO locked on-chain
│  (Mainnet)       │
└────────┬─────────┘
         │
         │ Orchestrator detects PENDING order (30s poll)
         ▼
┌──────────────────┐
│  CadenciaTBill   │ ← Issues cTBILL-7D tokens
│  (Mainnet)       │ ← Records maturity: now + 7 days
└────────┬─────────┘
         │
         │ BEHIND THE SCENES (invisible to buyer/seller):
         ▼
┌──────────────────┐
│  Folks Finance   │ ← 10,000 ALGO deposited
│  ALGO Pool       │ ← Earning real lending yield
│  (Mainnet)       │ ← ~4% APY variable
└──────────────────┘

         ... 7 days pass ...

┌──────────────────┐
│  Orchestrator    │ ← Detects maturity reached
│  auto-redeems    │
└────────┬─────────┘
         │
         │ 1. Withdraw from Folks Finance: 10,000 + ~7.67 ALGO yield
         │ 2. Burn cTBILL-7D tokens
         │ 3. Return 10,000 ALGO to Escrow
         │ 4. Send 7.67 ALGO yield to Platform Wallet
         ▼
┌──────────────────┐
│  Admin completes │ ← Seller receives 10,000 ALGO ✓
│  the order       │ ← Platform earned 7.67 ALGO ✓
└──────────────────┘
```

---

## Revenue Projection (Mainnet)

| Metric | Conservative | Growth |
|---|---|---|
| Average escrow volume | 100,000 ALGO/day | 1,000,000 ALGO/day |
| Average lock duration | 5 days | 7 days |
| Average idle ALGO | 500,000 ALGO | 7,000,000 ALGO |
| Yield rate | 4% APY | 5% APY |
| **Daily platform revenue** | **~54 ALGO/day** | **~958 ALGO/day** |
| **Monthly revenue** | **~1,644 ALGO** | **~28,767 ALGO** |

At ALGO ~$0.30, that's **$493–$8,630/month** from pure yield on idle funds. Zero additional cost to buyers or sellers.

---

## Investor Pitch

> *"Cadencia is a treasury management layer for escrow-based marketplaces. When funds sit idle in escrow, we invest them into short-term yield instruments — currently Algorand DeFi lending, with a roadmap to tokenized US Treasury bills via Ondo Finance. Every transaction is on-chain, every yield payment is verifiable, and the buyer/seller experience is unchanged. We're capturing the float — the same model that made PayPal $1B/year before they even charged fees."*

---

## Mainnet Roadmap

### Phase 1 — Launch (Month 1-2)
- Deploy contracts to Algorand Mainnet
- Demo mode OFF (real-time maturity)
- Yield source: Pre-funded reserve (bootstrap)
- Target: 10 marketplace partners, 1000 orders/month

### Phase 2 — DeFi Integration (Month 3-4)
- Integrate Folks Finance v2 Mainnet SDK
- Real ALGO lending yield backs all T-bill positions
- Remove pre-funded reserve dependency
- Target: 10,000 orders/month

### Phase 3 — Institutional Grade (Month 6+)
- Partner with regulated custodian (Ondo, OpenEden, or equivalent)
- Bridge to real US Treasury exposure
- Compliance framework for institutional escrow operators
- Target: 100,000+ orders/month, $1M+ idle ALGO under management

---

## Risk Assessment

| Risk | Mitigation |
|---|---|
| Folks Finance smart contract risk | Diversify across multiple protocols |
| ALGO price volatility | Orders are ALGO-denominated; yield is ALGO. No FX risk within the system |
| Insufficient reserve for yield | Phase 1 uses pre-funded reserve; Phase 2 eliminates this with real yield |
| Regulatory uncertainty | T-bill framing vs DeFi lending — choose narrative based on jurisdiction |
| Orchestrator downtime | Auto-redeem at maturity protects capital; manual admin fallback exists |
| Low marketplace adoption | B2B sales to existing Algorand marketplace operators |

---

*Document created: May 11, 2026*
*Status: Strategy defined — Testnet demo in progress*