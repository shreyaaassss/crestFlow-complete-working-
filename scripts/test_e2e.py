"""
Cadencia Treasury - Phase 4 E2E Test Script
Creates a test order and monitors it through the full T-bill lifecycle.

Usage:
  python scripts/test_e2e.py              # 7-day T-bill (7 min in demo)
  python scripts/test_e2e.py --tier 1     # 1-day T-bill (1 min in demo)
  python scripts/test_e2e.py --tier 30    # 30-day T-bill (30 min in demo)
  python scripts/test_e2e.py --amount 20  # 20 ALGO order (default: 10)

Prerequisites:
  Orchestrator must be running in a separate terminal:
    cd orchestrator && npx ts-node src/index.ts
"""

import os
import sys
import time
import base64
import argparse
from pathlib import Path

from dotenv import load_dotenv
from algosdk import mnemonic, account, encoding
from algosdk.v2client import algod
from algosdk.abi import Method as ABIMethod
from algosdk.transaction import PaymentTxn, SuggestedParams
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer, AccountTransactionSigner, TransactionWithSigner,
)

# ── Config ────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ALGOD_SERVER  = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
ALGOD_PORT    = os.getenv("ALGOD_PORT",   "443")
ALGOD_TOKEN   = os.getenv("ALGOD_TOKEN",  "")

DEPLOYER_MNEMONIC     = os.getenv("DEPLOYER_MNEMONIC", "")
ORCHESTRATOR_MNEMONIC = os.getenv("ORCHESTRATOR_MNEMONIC", "")
ESCROW_APP_ID         = int(os.getenv("ESCROW_APP_ID", "0"))
TBILL_APP_ID          = int(os.getenv("TBILL_APP_ID",  "0"))

# Lock rounds selected so selectTBillType() picks the correct tier
# (~3.3s per round → days = rounds * 3.3 / 86400)
TIER_TO_ROUNDS = {
    1:  500,         # 0.002 days → 1D
    3:  100_000,     # 3.8 days   → 3D
    7:  250_000,     # 9.5 days   → 7D
    14: 450_000,     # 17.2 days  → 14D
    30: 1_000_000,   # 38.1 days  → 30D
    60: 2_000_000,   # 76.2 days  → 60D
    90: 3_000_000,   # 114.3 days → 90D
}

DEMO_MATURITY_SECONDS = {
    1: 60, 3: 180, 7: 420, 14: 840, 30: 1800, 60: 3600, 90: 5400,
}

# ── Helpers ───────────────────────────────────────────────────

def client() -> algod.AlgodClient:
    return algod.AlgodClient(ALGOD_TOKEN, f"{ALGOD_SERVER}:{ALGOD_PORT}")

def get_deployer():
    sk = mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    return sk, account.address_from_private_key(sk)

def get_orchestrator_addr() -> str:
    sk = mnemonic.to_private_key(ORCHESTRATOR_MNEMONIC)
    return account.address_from_private_key(sk)

def app_address(app_id: int) -> str:
    return encoding.encode_address(
        encoding.checksum(b"appID" + app_id.to_bytes(8, "big"))
    )

def fresh_sp(c: algod.AlgodClient, fee: int = 1000) -> SuggestedParams:
    sp = c.suggested_params()
    sp.fee = fee
    sp.flat_fee = True
    return sp

def wait_confirmed(c: algod.AlgodClient, txid: str, rounds: int = 12) -> dict:
    last = dict(c.status())["last-round"]  # type: ignore[arg-type]
    for _ in range(rounds):
        info = dict(c.pending_transaction_info(txid))  # type: ignore[arg-type]
        if info.get("confirmed-round", 0) > 0:
            return info
        c.status_after_block(last + 1)
        last += 1
    raise Exception(f"Tx {txid} not confirmed after {rounds} rounds")

def abi_call(
    c: algod.AlgodClient,
    sk: str,
    addr: str,
    app_id: int,
    method_sig: str,
    args: list,
    fee: int = 2000,
    boxes: list | None = None,
):
    """Plain ABI call (no payment)."""
    method  = ABIMethod.from_signature(method_sig)
    signer  = AccountTransactionSigner(sk)
    atc     = AtomicTransactionComposer()
    sp      = fresh_sp(c, fee)
    atc.add_method_call(
        app_id=app_id, method=method, sender=addr, sp=sp,
        signer=signer, method_args=args,
        boxes=boxes or [],
    )
    result = atc.execute(c, 4)
    return result

def abi_call_pay(
    c: algod.AlgodClient,
    sk: str,
    addr: str,
    app_id: int,
    method_sig: str,
    pay_amount: int,
    pay_receiver: str,
    extra_args: list,
    fee: int = 3000,
    boxes: list | None = None,
):
    """ABI call whose first argument is a grouped payment transaction."""
    method  = ABIMethod.from_signature(method_sig)
    signer  = AccountTransactionSigner(sk)
    atc     = AtomicTransactionComposer()

    # Payment txn — fee=0 (covered by app call fee)
    pay_txn = TransactionWithSigner(
        PaymentTxn(sender=addr, sp=fresh_sp(c, 0), receiver=pay_receiver, amt=pay_amount),
        signer,
    )

    sp = fresh_sp(c, fee)
    atc.add_method_call(
        app_id=app_id, method=method, sender=addr, sp=sp,
        signer=signer,
        method_args=[pay_txn] + extra_args,  # pay_txn must be first
        boxes=boxes or [],
    )
    result = atc.execute(c, 4)
    return result

def read_tbill_globals(c: algod.AlgodClient) -> dict:
    state = c.application_info(TBILL_APP_ID)["params"]["global-state"]  # type: ignore
    out: dict = {}
    for kv in state:
        key = base64.b64decode(kv["key"]).decode("utf-8", errors="ignore")
        val = kv["value"]
        out[key] = val.get("uint", 0) if val["type"] == 2 else val.get("bytes", "")
    return out

def read_escrow_globals(c: algod.AlgodClient) -> dict:
    state = c.application_info(ESCROW_APP_ID)["params"]["global-state"]  # type: ignore
    out: dict = {}
    for kv in state:
        key = base64.b64decode(kv["key"]).decode("utf-8", errors="ignore")
        val = kv["value"]
        out[key] = val.get("uint", 0) if val["type"] == 2 else val.get("bytes", "")
    return out

# ── Main ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cadencia E2E Test")
    parser.add_argument("--tier",   type=int, default=7,  help="T-bill tier in days")
    parser.add_argument("--amount", type=int, default=10, help="Order amount in ALGO")
    cli = parser.parse_args()

    tier   = cli.tier
    amount = cli.amount

    if tier not in TIER_TO_ROUNDS:
        print(f"[ERROR] Invalid tier. Choose from: {sorted(TIER_TO_ROUNDS)}")
        sys.exit(1)

    lock_rounds  = TIER_TO_ROUNDS[tier]
    amount_micro = amount * 1_000_000
    maturity_sec = DEMO_MATURITY_SECONDS[tier]
    order_id     = int(time.time()) % 1_000_000
    # AlgoPy BoxMap key = attribute_name_bytes + arc4.UInt64(key) big-endian
    escrow_box_key = b"orders"    + order_id.to_bytes(8, "big")
    tbill_box_key  = b"positions" + order_id.to_bytes(8, "big")
    # Box refs: (app_index, key_bytes) — 0 = current app, explicit app_id for foreign
    escrow_box_ref = [(0, escrow_box_key)]
    tbill_box_ref  = [(TBILL_APP_ID, tbill_box_key)]
    escrow_addr  = app_address(ESCROW_APP_ID)

    print("=" * 60)
    print("  CADENCIA TREASURY  —  PHASE 4 E2E TEST")
    print("=" * 60)
    print(f"\n  T-Bill Tier:   cTBILL-{tier}D")
    print(f"  Amount:        {amount} ALGO")
    print(f"  Order ID:      {order_id}")
    print(f"  Lock Rounds:   {lock_rounds:,}  (~{lock_rounds*3.3/86400:.1f} days)")
    print(f"  Demo Maturity: {maturity_sec}s  ({maturity_sec//60} min)")
    yield_est = amount_micro * 500 * tier // 3_650_000
    print(f"  Est. Yield:    {yield_est:,} microALGO  ({yield_est/1e6:.6f} ALGO)")

    c = client()
    deployer_sk, deployer_addr = get_deployer()
    seller_addr = get_orchestrator_addr()  # must differ from buyer (deployer)
    bal = c.account_info(deployer_addr)["amount"] / 1e6  # type: ignore
    print(f"\n  Deployer (buyer): {deployer_addr}")
    print(f"  Seller:           {seller_addr}")
    print(f"  Balance:          {bal:.3f} ALGO")

    if bal < amount + 2:
        print(f"\n  [FAIL] Need at least {amount + 2} ALGO in deployer wallet")
        sys.exit(1)

    # ── Step 1: Create Order ───────────────────────────────────
    print("\n" + "-" * 60)
    print(f"  STEP 1: create_order  (order #{order_id})")
    print("-" * 60)
    try:
        result = abi_call_pay(
            c, deployer_sk, deployer_addr,
            ESCROW_APP_ID,
            "create_order(pay,address,uint64,uint64)void",
            pay_amount=amount_micro,
            pay_receiver=escrow_addr,
            extra_args=[seller_addr, order_id, lock_rounds],
            fee=3000,
            boxes=escrow_box_ref,
        )
        print(f"  OK — confirmed @ round {result.confirmed_round}")
        print(f"  https://testnet.explorer.perawallet.app/application/{ESCROW_APP_ID}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        sys.exit(1)

    # ── Step 2: Monitor ────────────────────────────────────────
    print("\n" + "-" * 60)
    print("  STEP 2: Monitoring  (Ctrl+C to skip to complete_order)")
    print(f"  Expected: ~30s PENDING->INVESTED, ~{maturity_sec+60}s INVESTED->REDEEMED")
    print("-" * 60)

    start = time.time()
    deadline = maturity_sec + 300

    try:
        while time.time() - start < deadline:
            elapsed = int(time.time() - start)
            try:
                gs  = read_tbill_globals(c)
                eg  = read_escrow_globals(c)
                print(
                    f"  [{elapsed:>4}s]  "
                    f"escrow.active_orders={eg.get('active_orders',0)}  "
                    f"tbill.active_positions={gs.get('active_positions',0)}  "
                    f"tbill.total_yield_paid={gs.get('total_yield_paid',0)} uA"
                )
                # Stop monitoring once position is redeemed
                if elapsed > maturity_sec + 30 and gs.get("active_positions", 1) == 0:
                    print("\n  Position redeemed by orchestrator.")
                    break
            except Exception as e:
                print(f"  [poll error] {e}")
            time.sleep(15)
    except KeyboardInterrupt:
        print("\n  Monitoring stopped.")

    # ── Step 3: Complete Order ─────────────────────────────────
    print("\n" + "-" * 60)
    print("  STEP 3: complete_order  (pays seller + yield to platform)")
    print("-" * 60)
    input("\n  Press ENTER to finalize the order...\n")

    try:
        result = abi_call(
            c, deployer_sk, deployer_addr,
            ESCROW_APP_ID,
            "complete_order(uint64)void",
            [order_id],
            fee=4000,
            boxes=escrow_box_ref,
        )
        print(f"  OK — confirmed @ round {result.confirmed_round}")
        print(f"  Seller ({seller_addr[:16]}...) received {amount} ALGO")
        print(f"  Platform received ~{yield_est/1e6:.6f} ALGO yield")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ── Final Stats ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  FINAL STATS")
    print("=" * 60)
    try:
        gs = read_tbill_globals(c)
        eg = read_escrow_globals(c)
        print(f"  TBill total_yield_paid:  {gs.get('total_yield_paid',0):,} microALGO")
        print(f"  TBill active_positions:  {gs.get('active_positions',0)}")
        print(f"  Escrow total_orders:     {eg.get('total_orders',0)}")
        print(f"  Escrow total_released:   {eg.get('total_released',0)/1e6:.3f} ALGO")
    except Exception as e:
        print(f"  [stats error] {e}")
    print(f"\n  Escrow:  https://testnet.explorer.perawallet.app/application/{ESCROW_APP_ID}")
    print(f"  TBill:   https://testnet.explorer.perawallet.app/application/{TBILL_APP_ID}")
    print("=" * 60)


if __name__ == "__main__":
    main()
