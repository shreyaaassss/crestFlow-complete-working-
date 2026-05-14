/**
 * Orders Routes — Full CRUD + Non-Custodial Signing Flow
 *
 * GET  /orders              — list all orders (filters: status, buyer, seller, limit, offset)
 * GET  /orders/estimate     — estimate yield WITHOUT creating order (no auth)
 * GET  /orders/:id          — single order + T-bill position + estimated yield
 * POST /orders/prepare [JWT]— build unsigned grouped txns for buyer
 * POST /orders/submit  [JWT]— submit buyer-signed txns to Algorand
 * DELETE /orders/:id   [JWT]— cancel order (admin-signed, buyer or admin only)
 *
 * Non-Custodial Flow:
 *  1. POST /auth/nonce      → nonce to sign
 *  2. POST /auth/verify     → JWT (24h)
 *  3. POST /orders/estimate → preview yield/maturity before committing
 *  4. POST /orders/prepare  → {unsigned_txns: [pay_b64, call_b64], order_id}
 *  5. Client signs BOTH txns with Pera Wallet / algosdk.signTransaction
 *  6. POST /orders/submit   → {txid, confirmed_round}
 *  7. GET  /orders/:id      → monitor status as orchestrator processes it
 */
import { Router, Request, Response } from "express";
import algosdk from "algosdk";
import { requireAuth } from "../middleware/jwt";
import {
  algodClient, ESCROW_APP_ID, TBILL_APP_ID, VALID_TIERS, TIER_ROUNDS, PLATFORM_WALLET, EXPLORER_BASE,
} from "../config";
import {
  fetchOrder, fetchAllOrders, fetchPosition,
  orderBoxKey, decodeOrder,
} from "../services/chain";
import { getTBillGlobalState } from "../services/chain";

export const ordersRouter = Router();

// ── Helpers ──────────────────────────────────────────────────────────────────

function selectTier(lock_days: number): number {
  for (let i = VALID_TIERS.length - 1; i >= 0; i--) {
    if (lock_days >= VALID_TIERS[i]) return VALID_TIERS[i];
  }
  return 1;
}

function calcYield(principalMicro: number, apyPct: number, days: number): number {
  return principalMicro * (apyPct / 100) * days / 365;
}

function encodeUInt64(n: number): Uint8Array {
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(n));
  return buf;
}

// ── GET /orders ──────────────────────────────────────────────────────────────

ordersRouter.get("/", async (req: Request, res: Response) => {
  const {
    status, buyer, seller,
    limit  = "50",
    offset = "0",
  } = req.query as Record<string, string>;

  try {
    let orders = await fetchAllOrders();

    // Filters
    if (status)  orders = orders.filter((o) => o.order.status === status.toUpperCase());
    if (buyer)   orders = orders.filter((o) => o.order.buyer  === buyer);
    if (seller)  orders = orders.filter((o) => o.order.seller === seller);

    const total = orders.length;

    // Pagination
    const lim = Math.min(parseInt(limit) || 50, 200);
    const off = parseInt(offset) || 0;
    const page = orders.slice(off, off + lim);

    res.json({
      total,
      limit: lim,
      offset: off,
      has_more: off + lim < total,
      orders: page.map(({ orderId, order }) => ({
        order_id:    orderId,
        status:      order.status,
        buyer:       order.buyer,
        seller:      order.seller,
        amount_algo: order.amount_algo,
        lock_until:  order.lock_until,
        created_at:  order.created_at,
      })),
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /orders/estimate ─────────────────────────────────────────────────────

ordersRouter.get("/estimate", async (req: Request, res: Response) => {
  const { amount_algo, lock_days } = req.query as Record<string, string>;

  const amount = parseFloat(amount_algo);
  const days   = parseInt(lock_days);

  if (isNaN(amount) || amount <= 0) {
    res.status(400).json({ error: "amount_algo must be a positive number" });
    return;
  }
  if (isNaN(days) || !VALID_TIERS.includes(days)) {
    res.status(400).json({ error: `lock_days must be one of: ${VALID_TIERS.join(", ")}` });
    return;
  }

  try {
    const tbill  = await getTBillGlobalState();
    const tier   = selectTier(days);
    const amtMicro = Math.round(amount * 1e6);
    const yieldMicro = calcYield(amtMicro, tbill.yield_rate_pct, tier);
    const demoSec = tier * tbill.demo_multiplier;

    res.json({
      amount_algo:          amount,
      lock_days:            days,
      tier:                 `cTBILL-${tier}D`,
      tier_days:            tier,
      apy_pct:              tbill.yield_rate_pct,
      estimated_yield_algo: parseFloat((yieldMicro / 1e6).toFixed(6)),
      total_return_algo:    parseFloat(((amtMicro + yieldMicro) / 1e6).toFixed(6)),
      invest_eligible:      amtMicro >= 5_000_000,
      demo_maturity_sec:    demoSec,
      demo_maturity_label:  `${demoSec}s (~${Math.round(demoSec / 60)}min)`,
      seller_receives_algo: parseFloat((amtMicro / 1e6).toFixed(6)),
      platform_receives_algo: parseFloat((yieldMicro / 1e6).toFixed(6)),
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /orders/prepare ─────────────────────────────────────────────────────

ordersRouter.post("/prepare", requireAuth, async (req: Request, res: Response) => {
  const buyerAddress = req.user!.address;
  const { seller_address, amount_algo, lock_days } = req.body as {
    seller_address?: string;
    amount_algo?:    number;
    lock_days?:      number;
  };

  // Validate
  if (!seller_address || amount_algo == null || lock_days == null) {
    res.status(400).json({ error: "seller_address, amount_algo, and lock_days are required" });
    return;
  }
  try { algosdk.decodeAddress(seller_address); } catch {
    res.status(400).json({ error: "Invalid seller_address" });
    return;
  }
  if (seller_address === buyerAddress) {
    res.status(400).json({ error: "Buyer and seller must be different addresses" });
    return;
  }
  if (amount_algo < 1) {
    res.status(400).json({ error: "Minimum 1 ALGO" });
    return;
  }
  if (!VALID_TIERS.includes(lock_days)) {
    res.status(400).json({ error: `lock_days must be one of: ${VALID_TIERS.join(", ")}` });
    return;
  }

  const amountMicro = Math.round(amount_algo * 1e6);
  const tier        = selectTier(lock_days);
  const lockRounds  = TIER_ROUNDS[tier];
  const orderId     = Math.floor(Date.now() / 1000) % 1_000_000;
  const escrowAddr  = algosdk.getApplicationAddress(ESCROW_APP_ID).toString();

  try {
    const tbill = await getTBillGlobalState();
    const yieldMicro = calcYield(amountMicro, tbill.yield_rate_pct, tier);
    const demoSec    = tier * tbill.demo_multiplier;

    const sp = await algodClient.getTransactionParams().do();

    // Txn 1: Payment — buyer → Escrow
    const payTxn = algosdk.makePaymentTxnWithSuggestedParamsFromObject({
      from:     buyerAddress,
      to:       escrowAddr,
      amount:   amountMicro,
      suggestedParams: { ...sp, fee: 0, flatFee: true },
    });

    // Txn 2: create_order(pay, address, uint64, uint64)void
    // ABI: selector(4) + seller_pubkey(32) + order_id(8) + lock_rounds(8)
    // Force Uint8Array.from() — algosdk v2.6 getSelector() returns plain Array at runtime
    const method     = algosdk.ABIMethod.fromSignature("create_order(pay,address,uint64,uint64)void");
    const selector   = Uint8Array.from(method.getSelector());
    const sellerKey  = Uint8Array.from(algosdk.decodeAddress(seller_address).publicKey);
    const orderIdEnc = Uint8Array.from(encodeUInt64(orderId));
    const lockEnc    = Uint8Array.from(encodeUInt64(lockRounds));

    const appCallTxn = algosdk.makeApplicationNoOpTxnFromObject({
      from:     buyerAddress,
      appIndex: ESCROW_APP_ID,
      appArgs:  [selector, sellerKey, orderIdEnc, lockEnc],
      suggestedParams: { ...sp, fee: 3000, flatFee: true },
      boxes:    [{ appIndex: ESCROW_APP_ID, name: Uint8Array.from(orderBoxKey(orderId)) }],
    });

    algosdk.assignGroupID([payTxn, appCallTxn]);

    res.json({
      order_id:       orderId,
      unsigned_txns: [
        Buffer.from(algosdk.encodeUnsignedTransaction(payTxn)).toString("base64"),
        Buffer.from(algosdk.encodeUnsignedTransaction(appCallTxn)).toString("base64"),
      ],
      escrow_address: escrowAddr,
      details: {
        buyer:              buyerAddress,
        seller:             seller_address,
        amount_algo,
        amount_microalgo:   amountMicro,
        lock_days,
        tier:               `cTBILL-${tier}D`,
        tier_days:          tier,
        lock_rounds:        lockRounds,
        estimated_yield_algo: parseFloat((yieldMicro / 1e6).toFixed(6)),
        total_return_algo:  parseFloat(((amountMicro + yieldMicro) / 1e6).toFixed(6)),
        invest_eligible:    amountMicro >= 5_000_000,
        demo_maturity_sec:  demoSec,
        seller_receives_algo:   parseFloat((amountMicro / 1e6).toFixed(6)),
        platform_receives_algo: parseFloat((yieldMicro / 1e6).toFixed(6)),
      },
      signing_instructions: {
        step1: "Decode both unsigned_txns from base64",
        step2: "Sign BOTH with your wallet (they share a group ID)",
        step3: "POST /orders/submit with { signed_txns: [sig0_b64, sig1_b64] }",
        pera:  "Use peraWallet.signTransaction([[txn0, txn1]]) to sign as a group",
      },
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /orders/submit ──────────────────────────────────────────────────────

ordersRouter.post("/submit", requireAuth, async (req: Request, res: Response) => {
  const { signed_txns } = req.body as { signed_txns?: string[] };

  if (!Array.isArray(signed_txns) || signed_txns.length !== 2) {
    res.status(400).json({ error: "signed_txns must be an array of exactly 2 base64 strings" });
    return;
  }

  try {
    const decoded = signed_txns.map((b64) =>
      algosdk.decodeSignedTransaction(Buffer.from(b64, "base64"))
    );

    // Verify same group ID
    const gid0 = decoded[0].txn.group;
    const gid1 = decoded[1].txn.group;
    if (!gid0 || !gid1 || Buffer.from(gid0).toString("hex") !== Buffer.from(gid1).toString("hex")) {
      res.status(400).json({ error: "Transactions must share the same group ID (sign together)" });
      return;
    }

    const raw = signed_txns.map((b64) => Buffer.from(b64, "base64"));
    const { txId } = await algodClient.sendRawTransaction(raw).do();
    const result   = await algosdk.waitForConfirmation(algodClient, txId, 6);
    const confirmedRound = result["confirmed-round"] ?? result.confirmedRound ?? null;

    res.json({
      txid:            txId,
      confirmed_round: confirmedRound ? Number(confirmedRound) : null,
      message:         "Order created. Funds are now secured in escrow.",
      next_steps: {
        monitor:  `GET /orders/{order_id} to track status`,
        explorer: `${EXPLORER_BASE}/tx/${txId}`,
      },
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});

// ── GET /orders/:id ──────────────────────────────────────────────────────────

ordersRouter.get("/:id", async (req: Request, res: Response) => {
  const orderId = parseInt(req.params.id);
  if (isNaN(orderId)) { res.status(400).json({ error: "Invalid order ID" }); return; }

  try {
    const [order, position] = await Promise.all([
      fetchOrder(orderId),
      fetchPosition(orderId),
    ]);

    // Enrich with position data and computed fields
    const now = Math.floor(Date.now() / 1000);

    res.json({
      order_id:             orderId,
      status:               order.status,
      buyer:                order.buyer,
      seller:               order.seller,
      amount_algo:          order.amount_algo,
      lock_until:           order.lock_until,
      created_at:           order.created_at,
      // "maturity" is presented as an operational release date — not a financial instrument
      estimated_release_ts: position?.maturity_timestamp ?? null,
      lifecycle: {
        is_active:   ["PENDING","INVESTED","REDEEMED"].includes(order.status),
        is_complete: order.status === "COMPLETED" || order.status === "CANCELLED",
      },
      links: {
        buyer_explorer:  `${EXPLORER_BASE}/address/${order.buyer}`,
        seller_explorer: `${EXPLORER_BASE}/address/${order.seller}`,
        escrow_explorer: `${EXPLORER_BASE}/application/${ESCROW_APP_ID}`,
      },
    });
  } catch (err: any) {
    if (err.message?.includes("404") || err.message?.includes("not found")) {
      res.status(404).json({ error: `Order ${orderId} not found` });
    } else {
      res.status(500).json({ error: err.message });
    }
  }
});

// ── DELETE /orders/:id — Cancel (Admin-signed on behalf of buyer/admin) ──────

ordersRouter.delete("/:id", requireAuth, async (req: Request, res: Response) => {
  const orderId     = parseInt(req.params.id);
  const callerAddr  = req.user!.address;
  if (isNaN(orderId)) { res.status(400).json({ error: "Invalid order ID" }); return; }

  // Load admin mnemonic from env (only admin or buyer can cancel on-chain)
  const adminMnemonic = process.env.DEPLOYER_MNEMONIC;
  if (!adminMnemonic) {
    res.status(503).json({ error: "Admin key not configured on this server" });
    return;
  }

  try {
    // Fetch order to get buyer address (needed for inner payment refund)
    const order = await fetchOrder(orderId);

    // Only buyer or admin can cancel
    const adminSk   = algosdk.mnemonicToSecretKey(adminMnemonic);
    const adminAddr = adminSk.addr.toString();

    if (callerAddr !== order.buyer && callerAddr !== adminAddr) {
      res.status(403).json({ error: "Only the buyer or admin can cancel this order" });
      return;
    }

    if (!["PENDING", "REDEEMED"].includes(order.status)) {
      res.status(400).json({
        error: `Cannot cancel order in status ${order.status}. Only PENDING or REDEEMED orders can be cancelled.`,
      });
      return;
    }

    // Build + sign cancel_order call (signed by admin key)
    const sp = await algodClient.getTransactionParams().do();
    const method   = algosdk.ABIMethod.fromSignature("cancel_order(uint64)void");
    const atc      = new algosdk.AtomicTransactionComposer();
    const spWithFee = { ...sp, fee: 3000, flatFee: true };

    atc.addMethodCall({
      appID:    ESCROW_APP_ID,
      method,
      sender:   adminAddr,
      suggestedParams: spWithFee,
      signer:   algosdk.makeBasicAccountTransactionSigner(adminSk),
      methodArgs: [orderId],
      boxes:    [{ appIndex: ESCROW_APP_ID, name: Uint8Array.from(orderBoxKey(orderId)) }],
      appAccounts: [order.buyer, PLATFORM_WALLET],
    });

    const result = await atc.execute(algodClient, 6);

    res.json({
      order_id:        orderId,
      status:          "CANCELLED",
      txid:            result.txIDs[0],
      confirmed_round: result.confirmedRound,
      message:         `Order ${orderId} cancelled. ${order.amount_algo} ALGO refunded to buyer.`,
      buyer_refunded_algo: order.amount_algo,
    });
  } catch (err: any) {
    res.status(400).json({ error: err.message });
  }
});
