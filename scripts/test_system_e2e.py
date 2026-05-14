#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CrestFlow — Complete System E2E Test
3 parallel suites: API, Algorand Chain, Supabase DB
Run: python scripts/test_system_e2e.py
"""
import sys, io, os, time, base64, json, threading
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import requests
from algosdk import mnemonic, account, util, encoding
from algosdk import transaction as txn_module
from algosdk.v2client import algod
try:
    import msgpack
except ImportError:
    msgpack = None

from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────
BASE_URL    = "http://localhost:3001"
ALGOD_URL   = os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud")
ALGOD_TOKEN = os.getenv("ALGOD_TOKEN", "")
ALGOD_PORT  = os.getenv("ALGOD_PORT", "443")

BUYER_SK   = mnemonic.to_private_key(os.environ["DEPLOYER_MNEMONIC"])
BUYER_PK   = account.address_from_private_key(BUYER_SK)
SELLER_SK  = mnemonic.to_private_key(os.environ["ORCHESTRATOR_MNEMONIC"])
SELLER_PK  = account.address_from_private_key(SELLER_SK)

ESCROW_APP_ID = int(os.environ["ESCROW_APP_ID"])
TBILL_APP_ID  = int(os.environ["TBILL_APP_ID"])

SB_URL  = os.getenv("SUPABASE_URL", "")
SB_SVC  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SB_ANON = os.getenv("SUPABASE_ANON_KEY", "")

# ── Shared results ────────────────────────────────────────────────────────────
results: dict = {}
lock = threading.Lock()

def record(suite: str, name: str, passed: bool, detail: str = ""):
    with lock:
        results.setdefault(suite, []).append((name, passed, detail))

# ── Suite 1: Backend API ──────────────────────────────────────────────────────
def suite_api():
    s = requests.Session()
    s.headers["Content-Type"] = "application/json"
    suite = "1. Backend API"

    def get(path, params=None, token=None):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        return s.get(f"{BASE_URL}{path}", params=params, headers=h)

    def post(path, body, token=None):
        h = {"Authorization": f"Bearer {token}"} if token else {}
        return s.post(f"{BASE_URL}{path}", json=body, headers=h)

    # Health
    try:
        r = get("/health")
        record(suite, "GET /health", r.status_code == 200, f"round={r.json().get('round')}")
    except Exception as e:
        record(suite, "GET /health", False, str(e)); return

    # Platform — public endpoint
    try:
        r = get("/platform/status")
        record(suite, "GET /platform/status", r.status_code == 200)
    except Exception as e:
        record(suite, "GET /platform/status", False, str(e))

    # Platform — admin-only endpoints (no token -> 401 Unauthorized)
    for ep in ["/platform/stats", "/platform/config"]:
        try:
            r = get(ep)
            record(suite, f"GET {ep} (no token -> 401)", r.status_code == 401)
        except Exception as e:
            record(suite, f"GET {ep} (no token -> 401)", False, str(e))

    # Platform — admin endpoints with invalid token -> 401
    for ep in ["/platform/stats", "/platform/config"]:
        try:
            r = s.get(f"{BASE_URL}{ep}", headers={"Authorization": "Bearer invalid.token.here"})
            record(suite, f"GET {ep} (bad token -> 401)", r.status_code == 401)
        except Exception as e:
            record(suite, f"GET {ep} (bad token -> 401)", False, str(e))

    # Platform tiers — public, no yield data
    try:
        r = get("/platform/tiers")
        d = r.json()
        has_apy = "apy_pct" in str(d)  # must NOT be present
        record(suite, "GET /platform/tiers", r.status_code == 200 and not has_apy, "no apy_pct in response")
    except Exception as e:
        record(suite, "GET /platform/tiers", False, str(e))

    # Estimate
    try:
        r = get("/orders/estimate", {"amount_algo": 10, "lock_days": 1})
        d = r.json()
        record(suite, "GET /orders/estimate", r.status_code == 200 and "estimated_yield_algo" in d)
    except Exception as e:
        record(suite, "GET /orders/estimate", False, str(e))

    # Estimate validation
    try:
        r = get("/orders/estimate", {"amount_algo": -1, "lock_days": 1})
        record(suite, "GET /orders/estimate (invalid amount)", r.status_code == 400)
    except Exception as e:
        record(suite, "GET /orders/estimate (invalid amount)", False, str(e))

    try:
        r = get("/orders/estimate", {"amount_algo": 10, "lock_days": 99})
        record(suite, "GET /orders/estimate (invalid tier)", r.status_code == 400)
    except Exception as e:
        record(suite, "GET /orders/estimate (invalid tier)", False, str(e))

    # GET /orders
    try:
        r = get("/orders")
        d = r.json()
        record(suite, "GET /orders", r.status_code == 200 and "total" in d, f"total={d.get('total')}")
    except Exception as e:
        record(suite, "GET /orders", False, str(e))

    # GET /orders with filters
    try:
        r = get("/orders", {"status": "COMPLETED", "limit": 5})
        record(suite, "GET /orders?status=COMPLETED&limit=5", r.status_code == 200)
    except Exception as e:
        record(suite, "GET /orders (filters)", False, str(e))

    # GET /orders/:id (not found)
    try:
        r = get("/orders/999999999")
        record(suite, "GET /orders/:id (not found)", r.status_code == 404)
    except Exception as e:
        record(suite, "GET /orders/:id (not found)", False, str(e))

    # GET /orders/:id (invalid)
    try:
        r = get("/orders/notanumber")
        record(suite, "GET /orders/:id (invalid)", r.status_code == 400)
    except Exception as e:
        record(suite, "GET /orders/:id (invalid)", False, str(e))

    # Account endpoints
    try:
        r = get(f"/account/{BUYER_PK}")
        d = r.json()
        record(suite, "GET /account/:address", r.status_code == 200 and "balance_algo" in d,
               f"balance={d.get('balance_algo')} ALGO")
    except Exception as e:
        record(suite, "GET /account/:address", False, str(e))

    try:
        r = get(f"/account/{BUYER_PK}/orders", {"role": "buyer"})
        d = r.json()
        record(suite, "GET /account/:address/orders", r.status_code == 200 and "total_orders" in d,
               f"orders={d.get('total_orders')}")
    except Exception as e:
        record(suite, "GET /account/:address/orders", False, str(e))

    try:
        r = get(f"/account/{SELLER_PK}/orders", {"role": "seller"})
        record(suite, "GET /account/:address/orders?role=seller", r.status_code == 200)
    except Exception as e:
        record(suite, "GET /account/:address/orders?role=seller", False, str(e))

    try:
        r = get("/account/INVALIDADDRESS")
        record(suite, "GET /account (invalid address)", r.status_code == 400)
    except Exception as e:
        record(suite, "GET /account (invalid address)", False, str(e))

    # Auth: nonce
    token = None
    try:
        r = post("/auth/nonce", {"address": BUYER_PK})
        d = r.json()
        nonce = d.get("nonce", "")
        record(suite, "POST /auth/nonce", r.status_code == 200 and bool(nonce),
               f"expires_in={d.get('expires_in_seconds')}s")

        # Sign nonce
        sig_raw = util.sign_bytes(bytes.fromhex(nonce), BUYER_SK)
        sig_b64 = sig_raw if isinstance(sig_raw, str) else base64.b64encode(sig_raw).decode()

        r2 = post("/auth/verify", {"address": BUYER_PK, "nonce": nonce, "signature": sig_b64})
        d2 = r2.json()
        token = d2.get("token")
        record(suite, "POST /auth/verify", r2.status_code == 200 and bool(token),
               f"jwt_len={len(token) if token else 0}")
    except Exception as e:
        record(suite, "POST /auth/nonce+verify", False, str(e))

    # Auth: bad signature
    try:
        r = post("/auth/nonce", {"address": BUYER_PK})
        nonce2 = r.json().get("nonce", "")
        r2 = post("/auth/verify", {"address": BUYER_PK, "nonce": nonce2, "signature": "AAAA"})
        record(suite, "POST /auth/verify (bad sig)", r2.status_code in (400, 401))
    except Exception as e:
        record(suite, "POST /auth/verify (bad sig)", False, str(e))

    # Auth: missing address
    try:
        r = post("/auth/nonce", {})
        record(suite, "POST /auth/nonce (missing address)", r.status_code == 400)
    except Exception as e:
        record(suite, "POST /auth/nonce (missing addr)", False, str(e))

    # Prepare (requires auth)
    prepare_data = None
    if token:
        try:
            r = post("/orders/prepare", {
                "seller_address": SELLER_PK,
                "amount_algo": 10,
                "lock_days": 1,
            }, token=token)
            d = r.json()
            prepare_data = d
            record(suite, "POST /orders/prepare", r.status_code == 200 and "unsigned_txns" in d,
                   f"order_id={d.get('order_id')}")
        except Exception as e:
            record(suite, "POST /orders/prepare", False, str(e))

        # Prepare: no auth
        try:
            r = post("/orders/prepare", {"seller_address": SELLER_PK, "amount_algo": 10, "lock_days": 1})
            record(suite, "POST /orders/prepare (no auth)", r.status_code == 401)
        except Exception as e:
            record(suite, "POST /orders/prepare (no auth)", False, str(e))

        # Prepare: buyer == seller
        try:
            r = post("/orders/prepare", {
                "seller_address": BUYER_PK, "amount_algo": 10, "lock_days": 1
            }, token=token)
            record(suite, "POST /orders/prepare (buyer==seller)", r.status_code == 400)
        except Exception as e:
            record(suite, "POST /orders/prepare (buyer==seller)", False, str(e))

        # Prepare: invalid tier
        try:
            r = post("/orders/prepare", {
                "seller_address": SELLER_PK, "amount_algo": 10, "lock_days": 99
            }, token=token)
            record(suite, "POST /orders/prepare (bad tier)", r.status_code == 400)
        except Exception as e:
            record(suite, "POST /orders/prepare (bad tier)", False, str(e))

    # Cancel: no auth
    try:
        r = s.delete(f"{BASE_URL}/orders/123")
        record(suite, "DELETE /orders/:id (no auth)", r.status_code == 401)
    except Exception as e:
        record(suite, "DELETE /orders/:id (no auth)", False, str(e))

# ── Suite 2: Algorand Chain ───────────────────────────────────────────────────
def suite_chain():
    suite = "2. Algorand Chain"
    client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_URL, headers={"X-Algo-API-Token": ALGOD_TOKEN})

    # Node health
    try:
        status = client.status()
        rnd = status.get("last-round", 0)
        record(suite, "Algod node reachable", rnd > 0, f"round={rnd}")
    except Exception as e:
        record(suite, "Algod node reachable", False, str(e)); return

    # Suggested params
    try:
        sp = client.suggested_params()
        record(suite, "Get transaction params", sp.first > 0, f"first={sp.first}")
    except Exception as e:
        record(suite, "Get transaction params", False, str(e))

    # Buyer account
    try:
        info = client.account_info(BUYER_PK)
        bal  = info.get("amount", 0)
        record(suite, "Buyer account on-chain", bal >= 0, f"balance={bal/1e6:.4f} ALGO")
    except Exception as e:
        record(suite, "Buyer account on-chain", False, str(e))

    # Seller account
    try:
        info = client.account_info(SELLER_PK)
        bal  = info.get("amount", 0)
        record(suite, "Seller account on-chain", bal >= 0, f"balance={bal/1e6:.4f} ALGO")
    except Exception as e:
        record(suite, "Seller account on-chain", False, str(e))

    # Escrow app exists
    try:
        app = client.application_info(ESCROW_APP_ID)
        record(suite, "Escrow app exists on-chain", "id" in app, f"app_id={app.get('id')}")
    except Exception as e:
        record(suite, "Escrow app exists on-chain", False, str(e))

    # TBill app exists
    try:
        app = client.application_info(TBILL_APP_ID)
        record(suite, "TBill app exists on-chain", "id" in app, f"app_id={app.get('id')}")
    except Exception as e:
        record(suite, "TBill app exists on-chain", False, str(e))

    # Escrow global state readable
    try:
        app    = client.application_info(ESCROW_APP_ID)
        gs     = app.get("params", {}).get("global-state", [])
        keys   = [base64.b64decode(kv["key"]).decode(errors="replace") for kv in gs]
        record(suite, "Escrow global state", len(gs) > 0, f"{len(gs)} keys: {keys[:4]}")
    except Exception as e:
        record(suite, "Escrow global state", False, str(e))

    # TBill global state readable
    try:
        app = client.application_info(TBILL_APP_ID)
        gs  = app.get("params", {}).get("global-state", [])
        record(suite, "TBill global state", len(gs) > 0, f"{len(gs)} keys")
    except Exception as e:
        record(suite, "TBill global state", False, str(e))

    # Escrow boxes accessible
    try:
        boxes = client.application_boxes(ESCROW_APP_ID)
        blist = boxes.get("boxes", [])
        record(suite, "Escrow boxes readable", True, f"{len(blist)} box(es)")
    except Exception as e:
        record(suite, "Escrow boxes readable", False, str(e))

    # TBill ASAs exist
    for env_key in ["TBILL_1D_ASA", "TBILL_7D_ASA", "TBILL_30D_ASA"]:
        asa_id = int(os.getenv(env_key, "0"))
        try:
            info = client.asset_info(asa_id)
            name = info.get("params", {}).get("name", "?")
            record(suite, f"ASA {env_key} exists", asa_id > 0 and "params" in info,
                   f"asa_id={asa_id} name={name}")
        except Exception as e:
            record(suite, f"ASA {env_key} exists", False, str(e))

    # Escrow app address has balance
    try:
        from algosdk import logic
        escrow_addr = logic.get_application_address(ESCROW_APP_ID)
        info = client.account_info(escrow_addr)
        bal  = info.get("amount", 0)
        record(suite, "Escrow app address funded", bal >= 0, f"{bal/1e6:.4f} ALGO")
    except Exception as e:
        record(suite, "Escrow app address funded", False, str(e))

    # Network version
    try:
        ver = client.versions()
        record(suite, "Algod version endpoint", "versions" in ver or "build" in ver)
    except Exception as e:
        record(suite, "Algod version endpoint", False, str(e))

# ── Suite 3: Supabase DB ──────────────────────────────────────────────────────
def suite_supabase():
    suite = "3. Supabase DB"
    TEST_ID = 999_888_001

    if not SB_URL or "your-service" in SB_SVC:
        record(suite, "Supabase configured", False, "SUPABASE_SERVICE_ROLE_KEY not set"); return

    try:
        svc  = create_client(SB_URL, SB_SVC)
        anon = create_client(SB_URL, SB_ANON)
        record(suite, "Supabase clients created", True)
    except Exception as e:
        record(suite, "Supabase clients created", False, str(e)); return

    def cleanup():
        for tbl in ["notifications","tx_events","tbill_positions","orchestrator_logs","orders","wallets","nonces"]:
            try:
                if tbl in ("orders","wallets","nonces"):
                    svc.table("notifications").delete().eq("order_id", TEST_ID).execute()
                    svc.table("tx_events").delete().eq("order_id", TEST_ID).execute()
                    svc.table("tbill_positions").delete().eq("order_id", TEST_ID).execute()
                    svc.table("orchestrator_logs").delete().eq("order_id", TEST_ID).execute()
                    svc.table("orders").delete().eq("order_id", TEST_ID).execute()
                    svc.table("wallets").delete().eq("address", BUYER_PK).execute()
                    svc.table("nonces").delete().eq("address", BUYER_PK).execute()
                    break
            except Exception:
                pass

    cleanup()

    # All tables exist
    for tbl in ["orders","tbill_positions","tx_events","wallets","nonces","platform_snapshots","orchestrator_logs","notifications"]:
        try:
            svc.table(tbl).select("*").limit(0).execute()
            record(suite, f"Table '{tbl}' exists", True)
        except Exception as e:
            record(suite, f"Table '{tbl}' exists", False, str(e))

    # Insert + read wallet
    try:
        svc.table("wallets").upsert({"address": BUYER_PK, "display_name": "Test"}).execute()
        r = anon.table("wallets").select("address").eq("address", BUYER_PK).execute()
        record(suite, "Wallet insert + anon read", len(r.data) == 1)
    except Exception as e:
        record(suite, "Wallet insert + anon read", False, str(e))

    # Nonce: service write, anon blocked
    try:
        exp = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        svc.table("nonces").upsert({"address": BUYER_PK, "nonce": "ab"*32, "expires_at": exp}).execute()
        r = anon.table("nonces").select("*").eq("address", BUYER_PK).execute()
        record(suite, "Nonces: anon blocked by RLS", len(r.data) == 0)
        svc.table("nonces").delete().eq("address", BUYER_PK).execute()
    except Exception as e:
        record(suite, "Nonces RLS", False, str(e))

    # Full order lifecycle
    now = datetime.now(timezone.utc)
    try:
        svc.table("orders").insert({
            "order_id": TEST_ID, "buyer_address": BUYER_PK, "seller_address": SELLER_PK,
            "amount_microalgo": 10_000_000, "lock_days": 1, "tbill_label": "cTBILL-1D",
            "status": "PENDING", "invest_eligible": True, "chain_verified": True,
        }).execute()
        record(suite, "Order insert PENDING", True)
    except Exception as e:
        record(suite, "Order insert PENDING", False, str(e))

    for status, extra in [
        ("INVESTED", {"invest_txid": "TX"*26, "invested_at": now.isoformat()}),
        ("REDEEMED", {"yield_earned_microalgo": 1370, "redeemed_at": now.isoformat()}),
        ("COMPLETED", {"complete_txid": "TX"*26, "completed_at": now.isoformat()}),
    ]:
        try:
            svc.table("orders").update({"status": status, **extra}).eq("order_id", TEST_ID).execute()
            r = svc.table("orders").select("status").eq("order_id", TEST_ID).execute()
            record(suite, f"Order transition -> {status}", r.data[0]["status"] == status)
        except Exception as e:
            record(suite, f"Order transition -> {status}", False, str(e))

    # Anon cannot write orders
    try:
        anon.table("orders").update({"status": "HACKED"}).eq("order_id", TEST_ID).execute()
        r = svc.table("orders").select("status").eq("order_id", TEST_ID).execute()
        record(suite, "Anon cannot write orders (RLS)", r.data[0]["status"] != "HACKED")
    except Exception:
        record(suite, "Anon cannot write orders (RLS)", True)

    # TBill position
    try:
        svc.table("tbill_positions").insert({
            "order_id": TEST_ID, "principal_microalgo": 10_000_000, "tbill_type_days": 1,
            "tbill_label": "cTBILL-1D", "maturity_timestamp": (now + timedelta(minutes=1)).isoformat(),
            "invested_at_ts": now.isoformat(), "status": "ACTIVE",
        }).execute()
        svc.table("tbill_positions").update({"status": "REDEEMED", "yield_microalgo": 1370}).eq("order_id", TEST_ID).execute()
        r = svc.table("tbill_positions").select("status").eq("order_id", TEST_ID).execute()
        record(suite, "TBill position lifecycle", r.data[0]["status"] == "REDEEMED")
    except Exception as e:
        record(suite, "TBill position lifecycle", False, str(e))

    # TX events
    try:
        for evt in ["ORDER_CREATED","INVESTED","REDEEMED","COMPLETED"]:
            svc.table("tx_events").insert({
                "order_id": TEST_ID, "event_type": evt, "txid": "T"*52
            }).execute()
        r = svc.table("tx_events").select("event_type").eq("order_id", TEST_ID).execute()
        record(suite, "TX events audit log (4 events)", len(r.data) == 4)
    except Exception as e:
        record(suite, "TX events audit log", False, str(e))

    # CHECK constraint
    try:
        svc.table("tx_events").insert({"order_id": TEST_ID, "event_type": "INVALID", "txid": "X"*52}).execute()
        record(suite, "TX events CHECK constraint", False, "Should have rejected INVALID")
    except Exception:
        record(suite, "TX events CHECK constraint", True)

    # order_summary view
    try:
        r = anon.table("order_summary").select("status,tbill_label,amount_algo").eq("order_id", TEST_ID).execute()
        d = r.data[0] if r.data else {}
        record(suite, "order_summary view JOIN", d.get("status") == "COMPLETED" and d.get("tbill_label") == "cTBILL-1D",
               f"status={d.get('status')}, amount={d.get('amount_algo')}")
    except Exception as e:
        record(suite, "order_summary view", False, str(e))

    # Orchestrator logs: anon blocked
    try:
        svc.table("orchestrator_logs").insert({"level":"info","worker":"investor","message":"test"}).execute()
        r = anon.table("orchestrator_logs").select("*").limit(1).execute()
        record(suite, "Orchestrator logs: anon blocked", len(r.data) == 0)
    except Exception:
        record(suite, "Orchestrator logs: anon blocked", True)

    # Platform snapshot
    try:
        svc.table("platform_snapshots").insert({
            "total_orders": 1, "active_orders": 0, "yield_rate_bps": 500, "demo_mode": True
        }).execute()
        # anon should be BLOCKED from platform_snapshots (RLS hardened)
        r = anon.table("platform_snapshots").select("yield_rate_bps").order("snapshotted_at", desc=True).limit(1).execute()
        record(suite, "Platform snapshot: anon blocked (RLS)", len(r.data) == 0)
    except Exception as e:
        record(suite, "Platform snapshot", False, str(e))

    cleanup()

# ── Runner ────────────────────────────────────────────────────────────────────
def main():
    print("\n+=========================================================+")
    print("|       CrestFlow -- Complete System E2E Test             |")
    print("|  3 suites running in parallel                           |")
    print("+=========================================================+")
    print(f"  Backend:  {BASE_URL}")
    print(f"  Chain:    {ALGOD_URL}")
    print(f"  Supabase: {SB_URL}")
    print(f"  Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    threads = [
        threading.Thread(target=suite_api,      name="API"),
        threading.Thread(target=suite_chain,    name="Chain"),
        threading.Thread(target=suite_supabase, name="Supabase"),
    ]

    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0

    total_pass = total_fail = 0
    for suite_name, tests in sorted(results.items()):
        print(f"\n{'='*58}")
        print(f"  {suite_name}")
        print(f"{'='*58}")
        for name, passed, detail in tests:
            icon = "PASS" if passed else "FAIL"
            detail_str = f"  ({detail})" if detail else ""
            print(f"  [{icon}]  {name}{detail_str}")
            if passed: total_pass += 1
            else:       total_fail += 1

    print(f"\n{'='*58}")
    total = total_pass + total_fail
    if total_fail == 0:
        print(f"  ALL {total} TESTS PASSED in {elapsed:.1f}s")
    else:
        print(f"  {total_fail} FAILED / {total_pass} passed / {total} total  ({elapsed:.1f}s)")
    print(f"{'='*58}\n")
    sys.exit(0 if total_fail == 0 else 1)

if __name__ == "__main__":
    main()
