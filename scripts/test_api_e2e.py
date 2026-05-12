#!/usr/bin/env python3
"""
Cadencia Treasury — Full API E2E Test
Tests the complete backend API flow using the deployer wallet as buyer
and the orchestrator wallet as seller.

Run with:
  python scripts/test_api_e2e.py [--tier 1] [--amount 10]

Requires:
  pip install requests algosdk python-dotenv
"""

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

# Force UTF-8 on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore

import requests
from algosdk import mnemonic, account, encoding, util
from algosdk import transaction as txn_module
from dotenv import load_dotenv
try:
    import msgpack  # algosdk dependency, always available
except ImportError:
    msgpack = None  # type: ignore

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Config ────────────────────────────────────────────────────────────────────

BASE_URL     = "http://localhost:3001"
POLL_SECONDS = 10
MAX_WAIT_SEC = 600  # 10 min max

BUYER_MNEMONIC  = os.environ["DEPLOYER_MNEMONIC"]
SELLER_MNEMONIC = os.environ["ORCHESTRATOR_MNEMONIC"]

buyer_sk   = mnemonic.to_private_key(BUYER_MNEMONIC)
buyer_pk   = account.address_from_private_key(buyer_sk)
seller_sk  = mnemonic.to_private_key(SELLER_MNEMONIC)
seller_pk  = account.address_from_private_key(seller_sk)

# ── ANSI helpers ──────────────────────────────────────────────────────────────

G  = "\033[92m"   # green
Y  = "\033[93m"   # yellow
R  = "\033[91m"   # red
B  = "\033[94m"   # blue
C  = "\033[96m"   # cyan
W  = "\033[97m"   # white bold
DIM = "\033[2m"
RST = "\033[0m"

def hdr(title: str):
    print(f"\n{B}{'─'*60}{RST}")
    print(f"{W}  {title}{RST}")
    print(f"{B}{'─'*60}{RST}")

def ok(msg: str):  print(f"  {G}✓{RST}  {msg}")
def info(msg: str): print(f"  {C}→{RST}  {msg}")
def warn(msg: str): print(f"  {Y}⚠{RST}  {msg}")
def fail(msg: str): print(f"  {R}✗{RST}  {msg}"); sys.exit(1)
def dim(msg: str):  print(f"  {DIM}{msg}{RST}")

# ── HTTP helpers ──────────────────────────────────────────────────────────────

session = requests.Session()
session.headers["Content-Type"] = "application/json"

def GET(path: str, **kwargs):
    r = session.get(f"{BASE_URL}{path}", **kwargs)
    if r.status_code >= 400:
        fail(f"GET {path} → {r.status_code}: {r.text[:300]}")
    return r.json()

def POST(path: str, body=None, **kwargs):
    r = session.post(f"{BASE_URL}{path}", json=body, **kwargs)
    if r.status_code >= 400:
        fail(f"POST {path} → {r.status_code}: {r.text[:300]}")
    return r.json()

def set_token(token: str):
    session.headers["Authorization"] = f"Bearer {token}"

# ── Steps ─────────────────────────────────────────────────────────────────────

def step_health():
    hdr("1. Health Check")
    data = GET("/health")
    ok(f"API is up — Network round: {data['round']}")
    ok(f"Escrow: {data['escrow_app']}  |  TBill: {data['tbill_app']}")
    return data

def step_platform(tier: int):
    hdr("2. Platform Info")

    config = GET("/platform/config")
    ok(f"Min order: {config['min_order_algo']} ALGO")
    ok(f"Valid tiers: {config['valid_lock_days']}")

    tiers = GET("/platform/tiers")
    ok(f"APY: {tiers['apy_pct']}%  |  Demo mode: {tiers['demo_mode']}")
    tier_info = next(t for t in tiers["tiers"] if t["days"] == tier)
    ok(f"Selected tier: {tier_info['label']}  |  Demo maturity: {tier_info['demo_maturity_label']}")
    return tiers

def step_estimate(amount: float, tier: int):
    hdr("3. Yield Estimate")
    data = GET(f"/orders/estimate?amount_algo={amount}&lock_days={tier}")
    ok(f"Amount:         {data['amount_algo']} ALGO")
    ok(f"Tier:           {data['tier']}")
    ok(f"Estimated yield:{data['estimated_yield_algo']} ALGO")
    ok(f"Total return:   {data['total_return_algo']} ALGO")
    ok(f"Seller gets:    {data['seller_receives_algo']} ALGO")
    ok(f"Platform gets:  {data['platform_receives_algo']} ALGO")
    ok(f"Invest eligible: {data['invest_eligible']}")
    ok(f"Demo maturity:  {data['demo_maturity_label']}")
    return data

def step_check_accounts():
    hdr("4. Account Balances")
    for label, addr in [("Buyer", buyer_pk), ("Seller", seller_pk)]:
        data = GET(f"/account/{addr}")
        ok(f"{label}: {addr[:16]}…  balance={data['balance_algo']:.4f} ALGO  spendable={data['spendable_algo']:.4f} ALGO")

def step_auth():
    hdr("5. Non-Custodial Auth (Nonce Challenge)")

    # 5a. Request nonce
    nonce_resp = POST("/auth/nonce", {"address": buyer_pk})
    nonce = nonce_resp["nonce"]
    ok(f"Nonce issued: {nonce[:24]}…  expires in {nonce_resp['expires_in_seconds']}s")

    # 5b. Sign nonce with buyer private key (algosdk.signBytes prepends "MX")
    nonce_bytes = bytes.fromhex(nonce)
    sig_raw     = util.sign_bytes(nonce_bytes, buyer_sk)
    # algosdk may return str (already b64) or raw bytes depending on version
    sig_b64 = sig_raw if isinstance(sig_raw, str) else base64.b64encode(sig_raw).decode()
    ok(f"Signature:    {sig_b64[:24]}  (Ed25519, signed off-server)")

    # 5c. Verify → JWT
    verify_resp = POST("/auth/verify", {
        "address":   buyer_pk,
        "nonce":     nonce,
        "signature": sig_b64,
    })
    token = verify_resp["token"]
    set_token(token)
    ok(f"JWT issued:   {token[:32]}…  valid {verify_resp['expires_in_seconds']//3600}h")
    return token

def step_prepare(amount: float, tier: int):
    hdr("6. Prepare Order (Unsigned Txns)")
    data = POST("/orders/prepare", {
        "seller_address": seller_pk,
        "amount_algo":    amount,
        "lock_days":      tier,
    })
    order_id = data["order_id"]
    ok(f"Order ID:       {order_id}")
    ok(f"Tier:           {data['details']['tier']}")
    ok(f"Est yield:      {data['details']['estimated_yield_algo']} ALGO")
    ok(f"Demo maturity:  {data['details']['demo_maturity_sec']}s")
    dim(f"Unsigned txns returned — buyer must sign both (Pera Wallet in production)")
    return data

def step_sign_and_submit(prepare: dict):
    hdr("7. Sign Txns + Submit (Demo: signing server-side with buyer key)")

    # In production this step happens in the Pera Wallet UI.
    # For the test we sign with the deployer private key directly.
    unsigned = prepare["unsigned_txns"]

    def decode_unsigned_txn(b64: str):
        """Decode a JS encodeUnsignedTransaction base64 string to a Python Transaction."""
        raw = base64.b64decode(b64)
        if msgpack:
            txn_dict = msgpack.unpackb(raw, raw=False)
            return txn_module.Transaction.undictify(txn_dict)
        # Fallback: algosdk internal
        return encoding.future_msgpack_decode(raw)  # type: ignore

    txns = [decode_unsigned_txn(t) for t in unsigned]

    signed_b64 = []
    for txn in txns:
        stxn     = txn.sign(buyer_sk)
        # encoding.msgpack_encode returns a base64 string of raw msgpack bytes
        # — exactly what the backend's Buffer.from(b64, "base64") expects
        signed_b64.append(encoding.msgpack_encode(stxn))

    data = POST("/orders/submit", {"signed_txns": signed_b64})
    ok(f"Submitted!  txid={data['txid']}")
    ok(f"Confirmed round: {data['confirmed_round']}")
    ok(f"Explorer: {data['next_steps']['explorer']}")
    return prepare["order_id"]

def step_monitor(order_id: int):
    hdr("8. Monitor Order Lifecycle")
    info(f"Polling GET /orders/{order_id} every {POLL_SECONDS}s …")
    info(f"Expected: PENDING → INVESTED → REDEEMED → COMPLETED\n")

    start   = time.time()
    last_st = None

    while time.time() - start < MAX_WAIT_SEC:
        try:
            data = GET(f"/orders/{order_id}")
        except SystemExit:
            time.sleep(POLL_SECONDS)
            continue

        status   = data["status"]
        elapsed  = int(time.time() - start)
        pos      = data.get("tbill_position")
        mat_left = pos["seconds_until_maturity"] if pos else None

        if status != last_st:
            print(f"\n  {G}[{elapsed:>4}s]{RST}  Status → {W}{status}{RST}")
            if status == "PENDING":
                info(f"Order locked. Amount: {data['amount_algo']} ALGO  Eligible: {data['invest_eligible']}")
            elif status == "INVESTED":
                info(f"T-bill position: {pos['tbill_label']}  Maturity: {pos['maturity_iso']}")
                info(f"Time until maturity: {mat_left}s")
            elif status == "REDEEMED":
                info(f"Yield earned: {data['yield_earned_algo']} ALGO")
                info(f"Completing…")
            elif status == "COMPLETED":
                elapsed_total = int(time.time() - start)
                print()
                ok(f"Order COMPLETED in {elapsed_total}s")
                ok(f"Seller received: {data['amount_algo']} ALGO")
                ok(f"Platform yield:  {data['yield_earned_algo']} ALGO")
                return data
            elif status in ("CANCELLED", "DISPUTED"):
                fail(f"Order ended in unexpected status: {status}")
            last_st = status
        else:
            dots = "." * ((elapsed // POLL_SECONDS) % 4 + 1)
            print(f"\r  {DIM}[{elapsed:>4}s]  {status}{dots}   {RST}", end="", flush=True)

        time.sleep(POLL_SECONDS)

    fail(f"Order {order_id} did not complete within {MAX_WAIT_SEC}s")

def step_final_check(order_id: int):
    hdr("9. Final Verification")

    # Order status
    order = GET(f"/orders/{order_id}")
    ok(f"Order {order_id}: {order['status']}")

    # Platform stats
    stats = GET("/platform/stats")
    ok(f"Total orders:    {stats['escrow']['total_orders']}")
    ok(f"Active orders:   {stats['escrow']['active_orders']}")
    ok(f"Total released:  {stats['escrow']['total_released_algo']:.4f} ALGO")
    ok(f"Total yield:     {stats['tbill']['total_yield_paid_algo']:.6f} ALGO")

    # Account order history
    history = GET(f"/account/{buyer_pk}/orders?role=buyer")
    ok(f"Buyer order history: {history['total_orders']} orders")
    completed = history["summary"]["by_status"].get("COMPLETED", 0)
    ok(f"Completed orders: {completed}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cadencia Treasury API E2E Test")
    parser.add_argument("--tier",   type=int,   default=1,  help="T-bill tier in days (1,3,7,14,30,60,90)")
    parser.add_argument("--amount", type=float, default=10, help="Amount in ALGO")
    args = parser.parse_args()

    print(f"\n{W}{'='*60}{RST}")
    print(f"{W}  Cadencia Treasury — Full API E2E Test{RST}")
    print(f"{W}  Buyer:  {buyer_pk[:20]}…{RST}")
    print(f"{W}  Seller: {seller_pk[:20]}…{RST}")
    print(f"{W}  Amount: {args.amount} ALGO  |  Tier: {args.tier}D{RST}")
    print(f"{W}{'='*60}{RST}")

    try:
        step_health()
        step_platform(args.tier)
        step_estimate(args.amount, args.tier)
        step_check_accounts()
        step_auth()
        prepare = step_prepare(args.amount, args.tier)
        order_id = step_sign_and_submit(prepare)
        step_monitor(order_id)
        step_final_check(order_id)

        print(f"\n{G}{'='*60}{RST}")
        print(f"{G}  ✓  ALL STEPS PASSED — Full lifecycle verified!{RST}")
        print(f"{G}{'='*60}{RST}\n")

    except KeyboardInterrupt:
        print(f"\n{Y}Test interrupted by user.{RST}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
