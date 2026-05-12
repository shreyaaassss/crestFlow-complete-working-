# Crestflow — Frontend Implementation Plan

> **Brand Name**: Crestflow
> **Target**: Lovable (React + TypeScript + Tailwind — Lovable's default stack)
> **Backend**: `http://localhost:3001` (15 endpoints, fully tested)
> **Wallet**: Pera Wallet SDK (`@perawallet/connect`)
> **Design**: Cohere-inspired enterprise system (detailed below)
> **Deployment**: Vercel (CORS + domain to be configured post-build)
> **Responsive**: Desktop-first, mobile responsive
> **Logo**: Generate minimalistic finance logomark — abstract upward crest/wave shape in deep-green (#003c33), geometric, no gradients, enterprise-grade

---

## 1. Design System (Cohere-Adapted for Cadencia)

### 1.1 Color Tokens

| Token | Hex | Usage |
|---|---|---|
| `--black` | `#000000` | Announcement bar |
| `--near-black` | `#17171c` | Primary CTAs, dark footer, UI cards |
| `--deep-green` | `#003c33` | Hero bands, dark feature sections |
| `--dark-navy` | `#071829` | Security/finance sections |
| `--action-blue` | `#1863dc` | Links, pagination, secondary actions |
| `--coral` | `#ff7759` | Category chips, warm accents |
| `--soft-coral` | `#ffad9b` | Chip borders, label details |
| `--canvas-white` | `#ffffff` | Default page background |
| `--soft-stone` | `#eeece7` | Product cards, testimonial surfaces |
| `--pale-green` | `#edfce9` | Section backdrops behind dark panels |
| `--pale-blue` | `#f1f5ff` | CTA surfaces |
| `--ink` | `#212121` | Body text |
| `--muted-slate` | `#93939f` | Metadata, dates, footer links |
| `--slate` | `#75758a` | Tertiary text |
| `--hairline` | `#d9d9dd` | Section dividers |
| `--border-light` | `#e5e7eb` | Secondary dividers |
| `--focus-blue` | `#4c6ee6` | Focus rings |
| `--error-red` | `#b30000` | Validation errors |

### 1.2 Typography

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|---|---|---:|---:|---:|---:|
| Hero Display | Space Grotesk | 96px | 400 | 1.00 | -1.92px |
| Product Display | Space Grotesk | 72px | 400 | 1.00 | -1.44px |
| Section Display | Inter | 60px | 400 | 1.00 | -1.2px |
| Section Heading | Inter | 48px | 400 | 1.20 | -0.48px |
| Card Heading | Inter | 32px | 400 | 1.20 | -0.32px |
| Feature Heading | Inter | 24px | 400 | 1.30 | 0 |
| Body Large | Inter | 18px | 400 | 1.40 | 0 |
| Body | Inter | 16px | 400 | 1.50 | 0 |
| Button | Inter | 14px | 500 | 1.71 | 0 |
| Caption | Inter | 14px | 400 | 1.40 | 0 |
| Mono Label | monospace | 14px | 400 | 1.40 | 0.28px |
| Micro | Inter | 12px | 400 | 1.40 | 0 |

### 1.3 Spacing, Radius, Elevation

- **Spacing**: 8px base (`8, 12, 16, 20, 24, 32, 40, 56, 64, 80`)
- **Radius**: `xs(4) sm(8) md(16) lg(22) xl(30) pill(32) full(9999)`
- **Elevation**: Flat. No shadows. Depth via surface alternation, borders (`1px #d9d9dd`), and rounded corners

### 1.4 Component Patterns

| Component | Style |
|---|---|
| `button-primary` | Near-black pill, 14px Inter 500, `px-6 py-3`, radius 32px |
| `button-secondary` | Text-only underlined link, no background |
| `button-pill-outline` | 1px dark border, transparent fill, radius 30px |
| `status-chip` | Uppercase mono 12px, pill shape, color per status |
| `dark-feature-band` | Full-width deep-green or navy section, white text |
| `capability-card` | Thin top-rule, 24px heading, body copy, text link |
| `stat-card` | Soft-stone background, large number, caption label |

---

## 2. Pages & Routes

### Page Map

| Route | Page | Auth | Primary API Endpoints |
|---|---|---|---|
| `/` | Landing / Home | No | `/platform/stats`, `/platform/tiers` |
| `/dashboard` | Buyer Dashboard | Yes | `/account/:addr`, `/account/:addr/orders`, `/platform/stats` |
| `/invest` | New Order Flow | Yes | `/orders/estimate`, `/orders/prepare`, `/orders/submit` |
| `/orders` | Order History | Yes | `/account/:addr/orders` (filters) |
| `/orders/:id` | Order Detail | Yes | `/orders/:id` (polling), `/tx/:txid` |
| `/explore` | Platform Explorer | No | `/orders` (list), `/platform/stats`, `/platform/config` |
| `/faq` | FAQ | No | None (static content) |

---

## 3. Page Specifications

### 3.1 Landing Page (`/`)

**Purpose**: Public marketing page — platform stats, tier showcase, CTA to connect wallet.

**Layout** (top to bottom):
1. **Announcement Bar** — Full-width black strip. "Crestflow is live on Algorand Testnet. [Try it now →]"
2. **Navigation** — Logo left, links center (`Explore`, `Dashboard`), "Connect Wallet" pill-primary right
3. **Hero Section** — Deep-green band
   - Display headline: "Treasury-Grade Yield. Zero Custody Risk." (96px Space Grotesk, white)
   - Subtitle: "Lock ALGO into tokenized T-Bills. Earn 5% APY. Non-custodial." (18px, muted white)
   - Two CTAs: [Start Investing] primary pill white, [Explore Platform →] secondary underlined
   - Crestflow logo (generated minimalistic finance mark) top-left in NavBar
4. **Live Stats Strip** — Canvas-white, 3 stat-cards in a row:
   - "Total Locked" → `GET /platform/stats` → `escrow.total_locked_algo`
   - "Total Yield Paid" → `tbill.total_yield_paid_algo`
   - "Active Orders" → `escrow.active_orders`
5. **How It Works** — 4-step horizontal cards on soft-stone:
   - Step 1: Connect Wallet (Pera icon)
   - Step 2: Choose Lock Period (tier selector)
   - Step 3: Sign & Deposit (transaction icon)
   - Step 4: Auto-Invest & Earn (yield icon)
6. **Tier Showcase** — `GET /platform/tiers` → 7 capability-cards in 3+3+1 grid
   - Each card: tier label (cTBILL-1D), APY %, period yield %, example yield for 10 ALGO, demo maturity time
7. **Platform Config** — Dark-navy band with `GET /platform/config` data:
   - Escrow App ID (linked to explorer), TBill App ID, Platform Wallet, Min Order, Network
8. **Footer** — Near-black. Links: FAQ, Explorer, GitHub. "Built on Algorand" badge. Crestflow wordmark.

**API calls on mount**: `GET /platform/stats`, `GET /platform/tiers`, `GET /platform/config`

---

### 3.2 Buyer Dashboard (`/dashboard`)

**Purpose**: Authenticated user's home — wallet overview, active orders, quick actions.

**Auth gate**: Redirect to `/` with "Connect Wallet" prompt if no JWT.

**Layout**:
1. **Wallet Header** — Full-width pale-green band
   - Address (truncated: `CFZR...3ICO`), copy button
   - Balance: `GET /account/:address` → `balance_algo` ALGO
   - Spendable: `spendable_algo` ALGO
   - Min Balance: `min_balance_algo` ALGO
   - [View on Explorer →] link using response's `explorer` field
2. **Quick Actions Row** — 2 cards:
   - [New Investment →] links to `/invest`
   - [View All Orders →] links to `/orders`
3. **Active Orders** — `GET /account/:address/orders?role=buyer&status=PENDING` + `INVESTED` + `REDEEMED`
   - Table with columns: Order ID, Amount (ALGO), Seller (truncated), Status (chip), Tier, Created
   - Each row clickable → `/orders/:id`
   - Status chips: PENDING=coral-outline, INVESTED=action-blue, REDEEMED=pale-green, COMPLETED=deep-green, CANCELLED=muted-slate
4. **Summary Stats** — From `GET /account/:address/orders` response's `summary` field:
   - Total orders, Completed, Total paid (ALGO), Total yield earned (ALGO)
   - Grouped by status bar chart (optional)
5. **Platform Overview** — Small stat strip from `GET /platform/stats`

**API calls on mount**: `GET /account/:address`, `GET /account/:address/orders?role=buyer`, `GET /platform/stats`

---

### 3.3 New Investment Page (`/invest`)

**Purpose**: The core transaction flow — estimate yield, prepare order, sign, submit.

**Auth gate**: Required.

**Layout — 3-step wizard**:

#### Step 1: Configure Order
- **Seller Address** — Text input, validated on blur via `algosdk.isValidAddress()`
- **Amount** — Number input (min 1 ALGO), shows "Min 5 ALGO for T-Bill investment" note
- **Lock Period** — 7 pill-outline buttons for each tier (1D, 3D, 7D, 14D, 30D, 60D, 90D)
  - Selected pill inverts to coral fill
  - Below each: demo maturity time from `/platform/tiers`
- **Yield Preview Panel** — Live updates on change via `GET /orders/estimate?amount_algo=X&lock_days=Y`
  - Shows: tier label, estimated yield (ALGO), total return, seller receives, platform receives
  - invest_eligible flag: if false, show warning "Below 5 ALGO threshold — no T-Bill investment"
  - Demo maturity label
- [Continue →] button (disabled until all fields valid)

#### Step 2: Review & Sign
- Order summary card (dark-feature-band style):
  - Buyer (your address), Seller, Amount, Lock Period, Estimated Yield, Tier
- On "Confirm" click: `POST /orders/prepare` → receives `unsigned_txns[]` and `order_id`
- Pera Wallet signing modal triggers: `peraWallet.signTransaction()`
  - Pass both unsigned txns as a group
- Loading state with "Waiting for wallet signature..."

#### Step 3: Submit & Track
- On sign success: `POST /orders/submit` with `signed_txns[]`
- Success card shows:
  - Order ID, Transaction ID (linked to explorer via response `next_steps.explorer`)
  - Confirmed round
  - "The orchestrator will invest your order within ~30 seconds"
- [Track Order →] button links to `/orders/:id`
- [Make Another →] resets wizard

**API flow**: `GET /orders/estimate` (live) → `POST /orders/prepare` → sign → `POST /orders/submit`

---

### 3.4 Order History (`/orders`)

**Purpose**: Filterable, paginated list of all user orders.

**Auth gate**: Required.

**Layout**:
1. **Filter Bar** — Horizontal row of pill-outline chips:
   - Role: `buyer` | `seller` | `any` (default: buyer)
   - Status: `ALL` | `PENDING` | `INVESTED` | `REDEEMED` | `COMPLETED` | `CANCELLED`
2. **Summary Strip** — From response `summary`:
   - Total orders, total paid, total yield, breakdown by status
3. **Order Table** — Rule-separated rows (research-table style):
   - Columns: Order ID, Amount (ALGO), Seller/Buyer, Status (chip), Yield Earned, Created Round
   - Click row → `/orders/:id`
4. **Pagination** — `limit` + `offset` controls, "Load More" or numbered pages

**API**: `GET /account/:address/orders?role=X&status=Y`

---

### 3.5 Order Detail (`/orders/:id`)

**Purpose**: Real-time order tracking with full lifecycle visualization.

**Auth gate**: Optional (public read), but cancel requires auth.

**Layout**:
1. **Order Header** — Large status chip + Order ID
   - Status with color-coded badge
   - `lifecycle.is_active` → show pulsing dot
2. **Lifecycle Timeline** — Horizontal 4-node stepper:
   - PENDING → INVESTED → REDEEMED → COMPLETED
   - Active node pulses, completed nodes filled green, future nodes gray
   - If CANCELLED: show red X at the cancelled stage
3. **Order Details Card** — Two-column grid:
   - Left: Buyer (linked), Seller (linked), Amount (ALGO), Lock Until (round), Created At (round)
   - Right: Status, Invest Eligible, Yield Earned (ALGO)
   - Links from response `links.buyer_explorer`, `links.seller_explorer`
4. **T-Bill Position Card** — Only if `tbill_position` is not null:
   - Tier label (cTBILL-7D), Principal (ALGO), Invested At (ISO), Maturity (ISO)
   - Countdown: `seconds_until_maturity` → live countdown timer
   - Progress bar: invested_at → maturity_timestamp → now
   - Status: ACTIVE / REDEEMED
   - `is_matured` badge
5. **Actions**:
   - If `lifecycle.is_active` && user is buyer: [Cancel Order] button → `DELETE /orders/:id`
   - Cancel confirmation modal with warning
6. **Auto-refresh**: Poll `GET /orders/:id` every 15 seconds while `lifecycle.is_active`

**API**: `GET /orders/:id` (polling), `DELETE /orders/:id` (cancel)

---

### 3.6 Platform Explorer (`/explore`)

**Purpose**: Public page showing all platform orders and contract info.

**Auth gate**: None.

**Layout**:
1. **Stats Dashboard** — `GET /platform/stats`:
   - Escrow: total locked, total released, total orders, active orders, min order, paused
   - TBill: total invested, total yield paid, active positions, APY, demo mode
   - Platform: total yield earned
2. **Contract Info** — `GET /platform/config`:
   - Escrow app ID + address + explorer link
   - TBill app ID + address + explorer link
   - Orchestrator address, Platform wallet, ASA IDs table
3. **All Orders Table** — `GET /orders?limit=50&offset=0`:
   - Filter chips: status, buyer address search, seller address search
   - Paginated table: Order ID, Buyer (truncated), Seller (truncated), Amount, Status, Yield
   - Click → `/orders/:id`

**API**: `GET /platform/stats`, `/platform/config`, `/orders`

---

### 3.7 FAQ Page (`/faq`)

**Purpose**: Static FAQ page answering common user questions.

**Auth gate**: None.

**Layout**:
1. **Hero** — Section heading: "Frequently Asked Questions" (48px, tight)
2. **FAQ Accordion** — Rule-separated expandable rows (research-table style):
   - "What is Crestflow?" → Crestflow is a non-custodial treasury platform on Algorand that invests escrowed ALGO into tokenized T-Bills to earn yield.
   - "How does the non-custodial auth work?" → You sign a random nonce with your Pera Wallet to prove ownership. We never touch your private keys.
   - "What are T-Bill tiers?" → 7 lock periods (1D to 90D). Longer locks earn more yield. In demo mode, 1 day = 60 seconds.
   - "What happens to my ALGO?" → Your ALGO is locked in the Escrow smart contract, then the orchestrator invests it into a T-Bill ASA. On maturity, it's redeemed and the principal goes to the seller, yield to the platform.
   - "Can I cancel an order?" → Yes, PENDING or REDEEMED orders can be cancelled. Your ALGO is refunded.
   - "What is demo mode?" → Demo mode compresses maturity times (1 day = 60 seconds) for testing on testnet.
   - "Is this on mainnet?" → Currently testnet only. Mainnet deployment will use real yield sources.
   - "What wallet do I need?" → Pera Wallet (iOS, Android, or web).
   - "What's the minimum investment?" → 5 ALGO for T-Bill investment eligibility, 1 ALGO minimum order.
   - "Where can I verify transactions?" → All transactions are on-chain. Use the Pera Explorer links shown on each order.
3. **CTA Band** — Dark-navy section: "Ready to start?" + [Connect Wallet] pill

**Components**: Accordion uses `hairline` border dividers, 24px Feature Heading for questions, 16px Body for answers. Expand/collapse with subtle height transition.

---

## 4. Shared Components

### 4.1 Navigation (`<NavBar />`)

- **Left**: Crestflow logo (minimalistic finance mark) + "Crestflow" wordmark (Space Grotesk 20px)
- **Center**: Home, Explore, FAQ, Dashboard (if connected)
- **Right**: 
  - Not connected: [Connect Wallet] pill-primary → triggers Pera connect + auth flow
  - Connected: Truncated address pill + [Disconnect] dropdown
- Mobile: Hamburger → slide-out menu

### 4.2 Wallet Connection Flow (via Pera Wallet SDK)

```
1. User clicks "Connect Wallet"
2. peraWallet.connect() → returns [address]
3. POST /auth/nonce {address} → {nonce}
4. peraWallet.signData([{data: Buffer.from(nonce,'hex')}], address) → sig
5. POST /auth/verify {address, nonce, signature} → {token}
6. Store token in localStorage, address in React context
7. Set Authorization: Bearer <token> on all subsequent requests
8. On token expiry (24h) or disconnect: clear state, redirect to /
```

### 4.3 Status Chip (`<StatusChip status="INVESTED" />`)

| Status | Background | Text | Border |
|---|---|---|---|
| PENDING | `#fff` | `#ff7759` | `#ff7759` |
| INVESTED | `#f1f5ff` | `#1863dc` | `#1863dc` |
| REDEEMED | `#edfce9` | `#003c33` | `#003c33` |
| COMPLETED | `#003c33` | `#fff` | `#003c33` |
| CANCELLED | `#eeece7` | `#93939f` | `#d9d9dd` |

### 4.4 Stat Card (`<StatCard label="Total Locked" value="30.5" unit="ALGO" />`)

- Soft-stone background, lg radius (22px)
- Large number (Card Heading 32px), caption label below

### 4.5 Address Display (`<AddressDisplay address="CFZR..." />`)

- Truncated: first 4 + "..." + last 4
- Copy button (clipboard API)
- Optional explorer link icon

### 4.6 Tier Selector (`<TierSelector selected={7} onChange={} />`)

- Row of 7 pill-outline buttons
- Selected: coral fill + dark text
- Unselected: transparent + dark border

### 4.7 Yield Preview (`<YieldPreview estimate={...} />`)

- Receives response from `GET /orders/estimate`
- Renders: tier, yield, total return, seller/platform split, eligibility, maturity

### 4.8 Lifecycle Stepper (`<LifecycleStepper status="INVESTED" />`)

- 4 horizontal nodes: PENDING → INVESTED → REDEEMED → COMPLETED
- Connected by lines, completed=green-filled, active=pulsing, future=gray-outline

### 4.9 Countdown Timer (`<CountdownTimer secondsLeft={120} />`)

- Displays mm:ss or hh:mm:ss
- Updates every second
- Turns coral when < 60s remaining

### 4.10 Transaction Link (`<TxLink txid="6X4L..." />`)

- Truncated txid with copy button
- Links to Pera Explorer

---

## 5. Complete API Reference (For Frontend)

### 5.1 Auth

```
POST /auth/nonce
  Body:     { address: string }
  Response: { nonce: string, expires_at: string, expires_in_seconds: number, message: string }

POST /auth/verify
  Body:     { address: string, nonce: string, signature: string }
  Response: { token: string, address: string, expires_in_seconds: 86400, message: string }
```

### 5.2 Orders

```
GET /orders?status=X&buyer=X&seller=X&limit=50&offset=0
  Response: { total, limit, offset, has_more, orders: [{order_id, buyer, seller, amount, 
              amount_algo, status, status_code, invest_eligible, yield_earned, yield_earned_algo, 
              created_at, lock_until}] }

GET /orders/estimate?amount_algo=10&lock_days=7
  Response: { amount_algo, lock_days, tier, tier_days, apy_pct, estimated_yield_algo, 
              total_return_algo, invest_eligible, demo_maturity_sec, demo_maturity_label, 
              seller_receives_algo, platform_receives_algo }

GET /orders/:id
  Response: { order_id, buyer, seller, amount, amount_algo, status, invest_eligible, 
              yield_earned, yield_earned_algo, created_at, lock_until,
              tbill_position: { principal_algo, tbill_label, maturity_iso, invested_at_iso, 
                                status, is_matured, seconds_until_maturity } | null,
              lifecycle: { is_active, is_complete, seconds_until_maturity, is_matured },
              links: { buyer_explorer, seller_explorer, escrow_explorer } }

POST /orders/prepare  [JWT]
  Body:     { seller_address, amount_algo, lock_days }
  Response: { order_id, unsigned_txns: [b64, b64], escrow_address, 
              details: { buyer, seller, amount_algo, tier, estimated_yield_algo, ... },
              signing_instructions: {...} }

POST /orders/submit  [JWT]
  Body:     { signed_txns: [b64, b64] }
  Response: { txid, confirmed_round, message, next_steps: { monitor, explorer } }

DELETE /orders/:id  [JWT]
  Response: { order_id, status, txid, confirmed_round, message, buyer_refunded_algo }
```

### 5.3 Platform

```
GET /platform/stats
  Response: { escrow: { total_locked_algo, total_released_algo, total_orders, active_orders, 
              min_order_algo, paused },
              tbill: { total_invested_algo, total_yield_paid_algo, active_positions, 
              yield_rate_bps, yield_rate_pct, demo_mode, demo_multiplier_sec, paused },
              platform: { platform_wallet, total_yield_earned_algo } }

GET /platform/config
  Response: { network, round, contracts: { escrow: { app_id, address, admin, paused, explorer }, 
              tbill: { app_id, address, admin, orchestrator, demo_mode, paused, explorer } },
              platform_wallet, min_order_algo, valid_lock_days: [1,3,7,14,30,60,90], 
              asa_ids: { "1D": id, ... } }

GET /platform/tiers
  Response: { yield_rate_bps, apy_pct, demo_mode, demo_note, 
              tiers: [{ days, label, apy_pct, yield_pct_for_period, demo_maturity_seconds, 
              demo_maturity_label, production_maturity_days, example_yield_10_algo, asa_id }] }
```

### 5.4 Account

```
GET /account/:address
  Response: { address, balance_algo, min_balance_algo, spendable_algo, opted_in_apps, 
              opted_in_assets, assets: [{asa_id, amount, frozen}], status, explorer }

GET /account/:address/orders?role=buyer|seller|any&status=X
  Response: { address, role, total_orders, 
              summary: { total_paid_algo, total_yield_algo, 
              by_status: { PENDING: n, INVESTED: n, ... } },
              orders: [{order_id, buyer, seller, amount_algo, status, ...}] }
```

### 5.5 Misc

```
GET /tx/:txid
  Response: { txid, confirmed, confirmed_round, pool_error, explorer }

GET /health
  Response: { status, network, round, escrow_app, tbill_app, timestamp, endpoints }
```

---

## 6. State Management

### 6.1 React Context: `WalletContext`

```typescript
interface WalletState {
  address: string | null;
  token: string | null;       // JWT
  isConnected: boolean;
  balance: number | null;     // ALGO
  connect: () => Promise<void>;
  disconnect: () => void;
}
```

### 6.2 API Client Singleton

- Base URL configurable via env var
- Auto-attaches `Authorization: Bearer` from context
- Auto-redirects to `/` on 401 responses (token expired)
- Typed response interfaces matching Section 5

### 6.3 Polling Hook: `useOrderPolling(orderId)`

- Polls `GET /orders/:id` every 15s
- Stops when `lifecycle.is_complete === true`
- Returns `{ order, position, lifecycle, loading, error }`

---

## 7. Lovable-Specific Instructions

> [!IMPORTANT]
> **Give Lovable these instructions per page**. Lovable works best with one page at a time, with explicit component names and exact data shapes.

### Build Order

1. **Design system first**: Create a `globals.css` with all color tokens, font imports (`Space Grotesk` + `Inter` from Google Fonts), and utility classes
2. **Shared components**: NavBar, StatusChip, StatCard, AddressDisplay, TierSelector, Footer
3. **Landing page** (`/`) — uses mock data first, then wire to API
4. **Wallet connection** — Pera SDK integration + auth context
5. **Dashboard** (`/dashboard`) — account info + active orders
6. **Invest page** (`/invest`) — 3-step wizard with estimate preview
7. **Order History** (`/orders`) — filtered table
8. **Order Detail** (`/orders/:id`) — lifecycle stepper + polling
9. **Explorer** (`/explore`) — public stats + order list
10. **FAQ** (`/faq`) — static accordion page

### Lovable Prompting Tips

- Reference component names exactly (e.g., "Create a `StatusChip` component...")
- Always refer to the brand as "Crestflow" (not Cadencia)
- Provide the exact API response JSON shape so Lovable types it correctly
- Specify Cohere design tokens by name (e.g., "Use `--deep-green` (#003c33) background")
- Tell Lovable to use `Space Grotesk` for display headings and `Inter` for body
- Ask for "no drop shadows, flat design, depth via surface alternation only"
- Specify radius: "22px for major cards, 8px for smaller cards, 32px pill for CTAs"

---

## 8. File Structure (Expected Lovable Output)

```
src/
├── App.tsx                    # Router setup
├── globals.css                # Design tokens, fonts, base styles
├── lib/
│   ├── api.ts                 # API client with typed methods
│   ├── types.ts               # All response interfaces
│   └── constants.ts           # Colors, tiers, status labels
├── contexts/
│   └── WalletContext.tsx       # Pera + JWT state
├── hooks/
│   ├── useOrderPolling.ts     # Auto-poll order status
│   ├── useYieldEstimate.ts    # Debounced estimate fetcher
│   └── usePlatformStats.ts    # Cached platform data
├── components/
│   ├── NavBar.tsx
│   ├── Footer.tsx
│   ├── StatusChip.tsx
│   ├── StatCard.tsx
│   ├── AddressDisplay.tsx
│   ├── TierSelector.tsx
│   ├── YieldPreview.tsx
│   ├── LifecycleStepper.tsx
│   ├── CountdownTimer.tsx
│   ├── TxLink.tsx
│   ├── OrderRow.tsx
│   ├── WalletButton.tsx
│   └── FaqAccordion.tsx
├── pages/
│   ├── Landing.tsx
│   ├── Dashboard.tsx
│   ├── Invest.tsx
│   ├── OrderHistory.tsx
│   ├── OrderDetail.tsx
│   ├── Explorer.tsx
│   └── Faq.tsx
```

---

## 9. Key UX Behaviors

| Behavior | Implementation |
|---|---|
| Wallet not connected | Show "Connect Wallet" CTA everywhere, disable invest/orders |
| Token expired (401) | Clear state, toast "Session expired", redirect to `/` |
| Order polling | 15s interval while `is_active`, stop on `is_complete` |
| Estimate updates | Debounce 500ms on amount/tier change, show loading skeleton |
| Cancel order | Confirmation modal with "This action cannot be undone" warning |
| Mobile nav | Hamburger → slide-out with all links + wallet status |
| Error states | Red border on inputs, toast notifications for API errors |
| Loading states | Skeleton shimmer on cards and tables (soft-stone color) |
| Empty states | Centered illustration + "No orders yet" + CTA to invest |

---

## Resolved Decisions

| Question | Answer |
|---|---|
| Brand name | **Crestflow** |
| Domain | Vercel (URL TBD, CORS configured post-deploy) |
| Logo | Generate minimalistic finance logomark — abstract upward crest/wave in deep-green, geometric, no gradients |
| Pages | 7 total: Landing, Dashboard, Invest, Order History, Order Detail, Explorer, **FAQ** |
| Responsive | Desktop-first, mobile responsive |
