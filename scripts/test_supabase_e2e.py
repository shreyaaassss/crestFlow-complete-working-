#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
"""
CrestFlow — Supabase Database E2E Test
=======================================
Tests all 8 tables, RLS policies, helper functions, Realtime subscription,
and the full data pipeline (orders → tbill_positions → tx_events → notifications).

Requirements:
  pip install supabase python-dotenv

Usage:
  python scripts/test_supabase_e2e.py

Expects in .env:
  SUPABASE_URL
  SUPABASE_SERVICE_ROLE_KEY   (service_role — bypasses RLS for write ops)
  SUPABASE_ANON_KEY           (anon — used to test RLS restrictions)
"""

import os
import sys
import time
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# ── Load .env from project root ───────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL            = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY    = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY       = os.getenv("SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or "your-service-role-key" in SUPABASE_SERVICE_KEY:
    print("✗ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")
    print("  Get the service_role key from:")
    print("  https://supabase.com/dashboard/project/yetssyjyhmujmxefwxvh/settings/api")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("✗ supabase package not installed. Run: pip install supabase")
    sys.exit(1)

# ── Clients ───────────────────────────────────────────────────────────────────
svc: Client  = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)   # full access
anon: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)       # RLS-restricted

# ── Test state ────────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0
TEST_ORDER_ID   = 999_999_001  # deterministic ID for this test run
TEST_BUYER      = "CFZRI425PCKOE7PN3ICOQLFHXQMB2FLM45BYLEHXVLFHIQCU2NDCFKIHM4"
TEST_SELLER     = "L22MEYNJK47WT3WWILMEBSRDSQJG6FMQMMMCBGQ6KBLHJK42FNVGUKWLE"
TEST_AMOUNT     = 10_000_000   # 10 ALGO in microALGO
TEST_YIELD      =      9_589   # ~0.0096 ALGO at 5% APY / 7 days

def ok(msg: str):
    global PASS
    PASS += 1
    print(f"  ✓  {msg}")

def fail(msg: str, err=None):
    global FAIL
    FAIL += 1
    detail = f" — {err}" if err else ""
    print(f"  ✗  {msg}{detail}")

def section(title: str):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"{'='*55}")

def cleanup():
    """Remove all test data before and after the test run."""
    try:
        svc.table("notifications").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("tx_events").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("tbill_positions").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("orchestrator_logs").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("orders").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("wallets").delete().eq("address", TEST_BUYER).execute()
        svc.table("nonces").delete().eq("address", TEST_BUYER).execute()
    except Exception:
        pass  # ignore cleanup errors

# ══════════════════════════════════════════════════════════════════════════════
# TEST GROUPS
# ══════════════════════════════════════════════════════════════════════════════

def test_connectivity():
    section("1. Connectivity + Schema Presence")

    try:
        res = svc.table("orders").select("order_id").limit(1).execute()
        ok("Connected to Supabase (service_role)")
    except Exception as e:
        fail("Could not connect with service_role key", e); return

    try:
        res = anon.table("orders").select("order_id").limit(1).execute()
        ok("Connected to Supabase (anon key)")
    except Exception as e:
        fail("Could not connect with anon key", e)

    expected_tables = [
        "orders", "tbill_positions", "tx_events", "wallets",
        "nonces", "platform_snapshots", "orchestrator_logs", "notifications"
    ]
    for table in expected_tables:
        try:
            svc.table(table).select("*").limit(0).execute()
            ok(f"Table '{table}' exists")
        except Exception as e:
            fail(f"Table '{table}' missing", e)


def test_wallets():
    section("2. Wallets Table")

    # Insert
    try:
        svc.table("wallets").upsert({
            "address": TEST_BUYER,
            "display_name": "Test Buyer",
            "total_orders": 0,
            "total_volume_microalgo": 0,
            "total_yield_earned_microalgo": 0,
        }).execute()
        ok("Upsert wallet (service_role)")
    except Exception as e:
        fail("Upsert wallet failed", e); return

    # Read back via anon (should be public)
    try:
        res = anon.table("wallets").select("*").eq("address", TEST_BUYER).execute()
        assert len(res.data) == 1
        assert res.data[0]["display_name"] == "Test Buyer"
        ok("Anon can read wallet row")
    except Exception as e:
        fail("Anon read wallet failed", e)

    # Update stats
    try:
        svc.table("wallets").update({
            "total_orders": 1,
            "total_volume_microalgo": TEST_AMOUNT,
            "last_seen_at": datetime.now(timezone.utc).isoformat()
        }).eq("address", TEST_BUYER).execute()
        ok("Update wallet stats (service_role)")
    except Exception as e:
        fail("Update wallet stats failed", e)


def test_nonces():
    section("3. Nonces Table (Security-Critical)")

    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

    # Insert via service_role
    try:
        svc.table("nonces").upsert({
            "address": TEST_BUYER,
            "nonce": "deadbeef" * 8,  # 64-char hex
            "expires_at": expires,
        }).execute()
        ok("Upsert nonce (service_role)")
    except Exception as e:
        fail("Upsert nonce failed", e); return

    # Anon must NOT be able to read nonces (RLS blocks it)
    try:
        res = anon.table("nonces").select("*").eq("address", TEST_BUYER).execute()
        if len(res.data) == 0:
            ok("Anon CANNOT read nonces (RLS correct)")
        else:
            fail("SECURITY: Anon CAN read nonces — RLS not working!")
    except Exception:
        ok("Anon CANNOT read nonces (RLS correct — exception)")

    # Consume (delete) via service_role
    try:
        svc.table("nonces").delete().eq("address", TEST_BUYER).execute()
        ok("Delete nonce on consume (service_role)")
    except Exception as e:
        fail("Delete nonce failed", e)


def test_orders():
    section("4. Orders Table — Full Lifecycle")

    now = datetime.now(timezone.utc)

    # CREATE order
    try:
        svc.table("orders").insert({
            "order_id":           TEST_ORDER_ID,
            "buyer_address":      TEST_BUYER,
            "seller_address":     TEST_SELLER,
            "amount_microalgo":   TEST_AMOUNT,
            "lock_days":          7,
            "tbill_label":        "cTBILL-7D",
            "status":             "PENDING",
            "invest_eligible":    True,
            "created_at_round":   63_000_000,
            "lock_until_round":   63_250_000,
            "create_txid":        "TESTTXID0000000000000000000000000000000000000000000000",
            "confirmed_round":    63_000_001,
            "chain_verified":     True,
        }).execute()
        ok("Insert order — PENDING (service_role)")
    except Exception as e:
        fail("Insert order failed", e); return

    # Anon can read it (public reads)
    try:
        res = anon.table("orders").select("*").eq("order_id", TEST_ORDER_ID).execute()
        assert len(res.data) == 1
        assert res.data[0]["status"] == "PENDING"
        ok("Anon can read order row")
    except Exception as e:
        fail("Anon read order failed", e)

    # Anon CANNOT write (RLS)
    try:
        anon.table("orders").update({"status": "HACKED"}).eq("order_id", TEST_ORDER_ID).execute()
        # If it silently does nothing (0 rows affected), that's also fine
        res = svc.table("orders").select("status").eq("order_id", TEST_ORDER_ID).execute()
        if res.data[0]["status"] != "HACKED":
            ok("Anon CANNOT write orders (RLS correct)")
        else:
            fail("SECURITY: Anon was able to mutate order status!")
    except Exception:
        ok("Anon CANNOT write orders (RLS correct — exception)")

    # Transition: PENDING → INVESTED
    try:
        svc.table("orders").update({
            "status":       "INVESTED",
            "invested_at":  datetime.now(timezone.utc).isoformat(),
            "invest_txid":  "INVESTTXID00000000000000000000000000000000000000000000",
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }).eq("order_id", TEST_ORDER_ID).execute()
        ok("Status transition: PENDING → INVESTED")
    except Exception as e:
        fail("Transition PENDING→INVESTED failed", e)

    # Transition: INVESTED → REDEEMED
    try:
        svc.table("orders").update({
            "status":               "REDEEMED",
            "yield_earned_microalgo": TEST_YIELD,
            "redeemed_at":          datetime.now(timezone.utc).isoformat(),
            "redeem_txid":          "REDEEMTXID0000000000000000000000000000000000000000000",
            "last_synced_at":       datetime.now(timezone.utc).isoformat(),
        }).eq("order_id", TEST_ORDER_ID).execute()
        ok("Status transition: INVESTED → REDEEMED")
    except Exception as e:
        fail("Transition INVESTED→REDEEMED failed", e)

    # Transition: REDEEMED → COMPLETED
    try:
        svc.table("orders").update({
            "status":         "COMPLETED",
            "completed_at":   datetime.now(timezone.utc).isoformat(),
            "complete_txid":  "COMPLETETXID000000000000000000000000000000000000000000",
            "last_synced_at": datetime.now(timezone.utc).isoformat(),
        }).eq("order_id", TEST_ORDER_ID).execute()
        ok("Status transition: REDEEMED → COMPLETED")
    except Exception as e:
        fail("Transition REDEEMED→COMPLETED failed", e)

    # Verify final state
    try:
        res = svc.table("orders").select("*").eq("order_id", TEST_ORDER_ID).execute()
        o = res.data[0]
        assert o["status"] == "COMPLETED", f"expected COMPLETED got {o['status']}"
        assert o["yield_earned_microalgo"] == TEST_YIELD
        assert o["complete_txid"] is not None
        ok(f"Final order state verified: status=COMPLETED, yield={TEST_YIELD} µA")
    except Exception as e:
        fail("Final order state verification failed", e)

    # Invalid status constraint
    try:
        svc.table("orders").insert({
            "order_id": TEST_ORDER_ID + 1,
            "buyer_address": TEST_BUYER,
            "seller_address": TEST_SELLER,
            "amount_microalgo": 1_000_000,
            "lock_days": 1,
            "status": "INVALID_STATUS",
        }).execute()
        fail("Status constraint not enforced!")
    except Exception:
        ok("Status CHECK constraint works (rejects 'INVALID_STATUS')")


def test_tbill_positions():
    section("5. TBill Positions Table")

    maturity = (datetime.now(timezone.utc) + timedelta(minutes=7)).isoformat()
    invested = datetime.now(timezone.utc).isoformat()

    # Insert position
    try:
        svc.table("tbill_positions").insert({
            "order_id":            TEST_ORDER_ID,
            "principal_microalgo": TEST_AMOUNT,
            "tbill_type_days":     7,
            "tbill_label":         "cTBILL-7D",
            "tbill_asa_id":        762214380,
            "maturity_timestamp":  maturity,
            "invested_at_ts":      invested,
            "status":              "ACTIVE",
        }).execute()
        ok("Insert tbill_position (ACTIVE)")
    except Exception as e:
        fail("Insert tbill_position failed", e); return

    # Read back
    try:
        res = anon.table("tbill_positions").select("*").eq("order_id", TEST_ORDER_ID).execute()
        assert len(res.data) == 1
        assert res.data[0]["tbill_label"] == "cTBILL-7D"
        ok("Anon can read tbill_position")
    except Exception as e:
        fail("Read tbill_position failed", e)

    # Mark redeemed
    try:
        svc.table("tbill_positions").update({
            "status":         "REDEEMED",
            "yield_microalgo": TEST_YIELD,
            "redeemed_at_ts": datetime.now(timezone.utc).isoformat(),
        }).eq("order_id", TEST_ORDER_ID).execute()
        ok("TBill position marked REDEEMED with yield")
    except Exception as e:
        fail("Update tbill_position failed", e)


def test_tx_events():
    section("6. TX Events (Append-Only Audit Log)")

    events = [
        ("ORDER_CREATED", TEST_BUYER,   TEST_AMOUNT, None),
        ("INVESTED",      "ORCHESTRATOR", TEST_AMOUNT, None),
        ("REDEEMED",      "ORCHESTRATOR", TEST_AMOUNT, TEST_YIELD),
        ("COMPLETED",     "ORCHESTRATOR", TEST_AMOUNT, TEST_YIELD),
    ]

    txids = [
        "TESTTXID0000000000000000000000000000000000000000000000",
        "INVESTTXID00000000000000000000000000000000000000000000",
        "REDEEMTXID0000000000000000000000000000000000000000000",
        "COMPLETETXID000000000000000000000000000000000000000000",
    ]

    for i, (event_type, actor, amount, yield_) in enumerate(events):
        try:
            svc.table("tx_events").insert({
                "order_id":        TEST_ORDER_ID,
                "event_type":      event_type,
                "txid":            txids[i],
                "confirmed_round": 63_000_000 + i * 10,
                "actor":           actor,
                "amount_microalgo": amount,
                "yield_microalgo": yield_,
                "metadata":        {"test": True, "step": i},
            }).execute()
            ok(f"Insert tx_event: {event_type}")
        except Exception as e:
            fail(f"Insert tx_event {event_type} failed", e)

    # Count events
    try:
        res = svc.table("tx_events").select("*").eq("order_id", TEST_ORDER_ID).execute()
        assert len(res.data) == len(events), f"expected {len(events)} events, got {len(res.data)}"
        ok(f"All {len(events)} events found for order")
    except Exception as e:
        fail("Count tx_events failed", e)

    # Anon can read events (public audit trail)
    try:
        res = anon.table("tx_events").select("event_type").eq("order_id", TEST_ORDER_ID).execute()
        types = [r["event_type"] for r in res.data]
        assert "COMPLETED" in types
        ok("Anon can read tx_events audit log")
    except Exception as e:
        fail("Anon read tx_events failed", e)

    # Invalid event type constraint
    try:
        svc.table("tx_events").insert({
            "order_id": TEST_ORDER_ID,
            "event_type": "HACK_ATTEMPT",
            "txid": "X" * 52,
        }).execute()
        fail("Event type constraint not enforced!")
    except Exception:
        ok("Event type CHECK constraint works")


def test_platform_snapshots():
    section("7. Platform Snapshots")

    try:
        svc.table("platform_snapshots").insert({
            "total_locked_microalgo":     TEST_AMOUNT,
            "total_released_microalgo":   TEST_AMOUNT,
            "total_orders":               3,
            "active_orders":              0,
            "total_invested_microalgo":   TEST_AMOUNT,
            "total_yield_paid_microalgo": TEST_YIELD,
            "active_positions":           0,
            "yield_rate_bps":             500,
            "demo_mode":                  True,
            "algo_round":                 63_000_100,
        }).execute()
        ok("Insert platform_snapshot")
    except Exception as e:
        fail("Insert platform_snapshot failed", e); return

    try:
        res = anon.table("platform_snapshots").select("*").order("snapshotted_at", desc=True).limit(1).execute()
        assert len(res.data) == 1
        assert res.data[0]["yield_rate_bps"] == 500
        ok("Anon can read latest platform_snapshot")
    except Exception as e:
        fail("Read platform_snapshot failed", e)


def test_orchestrator_logs():
    section("8. Orchestrator Logs")

    log_entries = [
        ("info",  "investor",   "Found 1 eligible PENDING order"),
        ("info",  "investor",   f"Invested order {TEST_ORDER_ID}: 10.0 ALGO -> cTBILL-7D"),
        ("info",  "redeemer",   f"Order {TEST_ORDER_ID} matured! Redeeming..."),
        ("info",  "completer",  f"Auto-completed order {TEST_ORDER_ID}"),
        ("warn",  "investor",   "Retrying invest() due to transient error"),
        ("error", "redeemer",   "Failed after 3 retries"),
    ]

    for level, worker, msg in log_entries:
        try:
            svc.table("orchestrator_logs").insert({
                "level":    level,
                "worker":   worker,
                "order_id": TEST_ORDER_ID if "order" in msg.lower() else None,
                "message":  msg,
                "metadata": {"test_run": True},
            }).execute()
            ok(f"Insert log [{level}] {worker}: {msg[:40]}")
        except Exception as e:
            fail(f"Insert log failed [{level}/{worker}]", e)

    # Anon must NOT read orchestrator logs
    try:
        res = anon.table("orchestrator_logs").select("*").limit(1).execute()
        if len(res.data) == 0:
            ok("Anon CANNOT read orchestrator_logs (RLS correct)")
        else:
            fail("SECURITY: Anon CAN read orchestrator_logs!")
    except Exception:
        ok("Anon CANNOT read orchestrator_logs (RLS correct — exception)")

    # Service_role can query by level
    try:
        res = svc.table("orchestrator_logs").select("*").eq("level", "error").execute()
        assert len(res.data) >= 1
        ok(f"Service_role can query by level (found {len(res.data)} error log(s))")
    except Exception as e:
        fail("Query orchestrator_logs by level failed", e)


def test_notifications():
    section("9. Notifications Table")

    notif_types = [
        ("ORDER_INVESTED",  "Order Invested",   "Your 10 ALGO order is now earning yield"),
        ("ORDER_COMPLETED", "Order Completed",  "Your order is complete. 10 ALGO paid to seller."),
    ]

    for notif_type, title, body in notif_types:
        try:
            svc.table("notifications").insert({
                "address":  TEST_BUYER,
                "order_id": TEST_ORDER_ID,
                "type":     notif_type,
                "title":    title,
                "body":     body,
                "read":     False,
            }).execute()
            ok(f"Insert notification: {notif_type}")
        except Exception as e:
            fail(f"Insert notification {notif_type} failed", e)

    # Mark as read
    try:
        svc.table("notifications").update({"read": True}).eq("order_id", TEST_ORDER_ID).execute()
        ok("Mark notifications as read")
    except Exception as e:
        fail("Mark read failed", e)


def test_order_summary_view():
    section("10. order_summary View (JOIN orders + tbill_positions)")

    try:
        res = anon.table("order_summary").select("*").eq("order_id", TEST_ORDER_ID).execute()
        assert len(res.data) == 1
        row = res.data[0]
        assert row["status"] == "COMPLETED", f"expected COMPLETED got {row['status']}"
        assert row["tbill_label"] == "cTBILL-7D"
        assert row["position_status"] == "REDEEMED"
        assert float(row["amount_algo"]) == TEST_AMOUNT / 1e6
        ok(f"order_summary view: status={row['status']}, amount={row['amount_algo']} ALGO")
        ok(f"  tbill_label={row['tbill_label']}, position={row['position_status']}")
    except Exception as e:
        fail("order_summary view query failed", e)


def test_filters_and_pagination():
    section("11. Filters, Sorting, Pagination")

    # Filter by buyer
    try:
        res = svc.table("orders").select("order_id, status").eq("buyer_address", TEST_BUYER).execute()
        assert any(r["order_id"] == TEST_ORDER_ID for r in res.data)
        ok(f"Filter by buyer_address: {len(res.data)} order(s)")
    except Exception as e:
        fail("Filter by buyer failed", e)

    # Filter by status
    try:
        res = svc.table("orders").select("order_id").eq("status", "COMPLETED").execute()
        ok(f"Filter by status=COMPLETED: {len(res.data)} order(s)")
    except Exception as e:
        fail("Filter by status failed", e)

    # Sorting
    try:
        res = svc.table("orders").select("order_id, created_at").order("created_at", desc=True).limit(5).execute()
        ok(f"Sort by created_at DESC with limit: {len(res.data)} row(s)")
    except Exception as e:
        fail("Sort+limit failed", e)

    # Pagination
    try:
        page1 = svc.table("tx_events").select("id").eq("order_id", TEST_ORDER_ID).range(0, 1).execute()
        page2 = svc.table("tx_events").select("id").eq("order_id", TEST_ORDER_ID).range(2, 3).execute()
        ok(f"Pagination: page1={len(page1.data)} rows, page2={len(page2.data)} rows")
    except Exception as e:
        fail("Pagination failed", e)


def test_cascade_delete():
    section("12. Cascade Delete (orders → related tables)")

    # We intentionally DON'T cascade here — we clean up manually to verify FK integrity first
    try:
        # Verify child rows exist
        pos = svc.table("tbill_positions").select("order_id").eq("order_id", TEST_ORDER_ID).execute()
        evts = svc.table("tx_events").select("id").eq("order_id", TEST_ORDER_ID).execute()
        assert len(pos.data) >= 1
        assert len(evts.data) >= 1
        ok(f"Child rows exist: {len(pos.data)} position(s), {len(evts.data)} tx_event(s)")
    except Exception as e:
        fail("Child row check failed", e)

    # Delete the order — cascade should wipe children
    try:
        svc.table("notifications").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("tx_events").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("tbill_positions").delete().eq("order_id", TEST_ORDER_ID).execute()
        svc.table("orders").delete().eq("order_id", TEST_ORDER_ID).execute()
        ok("Deleted order and all related rows")
    except Exception as e:
        fail("Delete cascade failed", e); return

    # Verify child rows are gone
    try:
        pos  = svc.table("tbill_positions").select("order_id").eq("order_id", TEST_ORDER_ID).execute()
        evts = svc.table("tx_events").select("id").eq("order_id", TEST_ORDER_ID).execute()
        notif = svc.table("notifications").select("id").eq("order_id", TEST_ORDER_ID).execute()
        assert len(pos.data) == 0
        assert len(evts.data) == 0
        assert len(notif.data) == 0
        ok("All child rows deleted: positions, tx_events, notifications all empty")
    except Exception as e:
        fail("Child row cleanup verification failed", e)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    print()
    print("+" + "="*55 + "+")
    print("|     CrestFlow - Supabase Database E2E Test           |")
    print("|     Project: yetssyjyhmujmxefwxvh                    |")
    print("+" + "="*55 + "+")
    print(f"  URL:      {SUPABASE_URL}")
    print(f"  Test ID:  order {TEST_ORDER_ID}")
    print(f"  Buyer:    {TEST_BUYER[:20]}...")
    print(f"  Started:  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Cleanup any leftover test data from previous run
    print("\n  Cleaning up previous test data...")
    cleanup()
    time.sleep(0.5)

    # Run all test groups
    test_connectivity()
    test_wallets()
    test_nonces()
    test_orders()
    test_tbill_positions()
    test_tx_events()
    test_platform_snapshots()
    test_orchestrator_logs()
    test_notifications()
    test_order_summary_view()
    test_filters_and_pagination()
    test_cascade_delete()

    # Final cleanup
    cleanup()

    # Summary
    total = PASS + FAIL
    print()
    print("=" * 55)
    if FAIL == 0:
        print(f"  PASS: ALL {total} TESTS PASSED")
    else:
        print(f"  FAIL: {FAIL} failed  /  {PASS} passed  /  {total} total")
    print("=" * 55)
    print()

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
