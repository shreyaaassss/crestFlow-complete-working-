/**
 * Platform Routes
 *
 * GET  /platform/stats   — live on-chain stats (escrow + tbill combined)
 * GET  /platform/config  — contract addresses, IDs, network info
 * GET  /platform/tiers   — all 7 T-bill tiers with APY, maturity, demo details
 */
import { Router, Request, Response } from "express";
import { getEscrowGlobalState, getTBillGlobalState } from "../services/chain";
import { algodClient, ESCROW_APP_ID, TBILL_APP_ID, PLATFORM_WALLET, VALID_TIERS } from "../config";

export const platformRouter = Router();

// ─── GET /platform/stats ────────────────────────────────────────────────────

platformRouter.get("/stats", async (_req: Request, res: Response) => {
  try {
    const [escrow, tbill] = await Promise.all([
      getEscrowGlobalState(),
      getTBillGlobalState(),
    ]);

    res.json({
      escrow: {
        total_locked_microalgo:   escrow.total_locked,
        total_locked_algo:        escrow.total_locked / 1e6,
        total_released_microalgo: escrow.total_released,
        total_released_algo:      escrow.total_released / 1e6,
        total_orders:             escrow.total_orders,
        active_orders:            escrow.active_orders,
        min_order_algo:           escrow.min_order_amount / 1e6,
        paused:                   escrow.paused,
      },
      tbill: {
        total_invested_microalgo:  tbill.total_invested,
        total_invested_algo:       tbill.total_invested / 1e6,
        total_yield_paid_microalgo: tbill.total_yield_paid,
        total_yield_paid_algo:     tbill.total_yield_paid / 1e6,
        active_positions:          tbill.active_positions,
        yield_rate_bps:            tbill.yield_rate_bps,
        yield_rate_pct:            tbill.yield_rate_pct,
        demo_mode:                 tbill.demo_mode,
        demo_multiplier_sec:       tbill.demo_multiplier,
        paused:                    tbill.paused,
      },
      platform: {
        platform_wallet:      PLATFORM_WALLET,
        total_yield_earned_algo: tbill.total_yield_paid / 1e6,
      },
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /platform/config ───────────────────────────────────────────────────

platformRouter.get("/config", async (_req: Request, res: Response) => {
  try {
    const [escrow, tbill, sp] = await Promise.all([
      getEscrowGlobalState(),
      getTBillGlobalState(),
      algodClient.getTransactionParams().do(),
    ]);

    const escrowAddr = require("algosdk").getApplicationAddress(ESCROW_APP_ID).toString();
    const tbillAddr  = require("algosdk").getApplicationAddress(TBILL_APP_ID).toString();

    res.json({
      network: "algorand-testnet",
      round:   Number((sp as any).firstRound),
      contracts: {
        escrow: {
          app_id:    ESCROW_APP_ID,
          address:   escrowAddr,
          admin:     escrow.admin,
          paused:    escrow.paused,
          explorer:  `https://testnet.explorer.perawallet.app/application/${ESCROW_APP_ID}`,
        },
        tbill: {
          app_id:       TBILL_APP_ID,
          address:      tbillAddr,
          admin:        tbill.admin,
          orchestrator: tbill.orchestrator,
          demo_mode:    tbill.demo_mode,
          paused:       tbill.paused,
          explorer:     `https://testnet.explorer.perawallet.app/application/${TBILL_APP_ID}`,
        },
      },
      platform_wallet:   PLATFORM_WALLET,
      min_order_algo:    escrow.min_order_amount / 1e6,
      valid_lock_days:   VALID_TIERS,
      asa_ids:           tbill.asa_ids,
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// ─── GET /platform/tiers ────────────────────────────────────────────────────

platformRouter.get("/tiers", async (_req: Request, res: Response) => {
  try {
    const tbill = await getTBillGlobalState();
    const apyPct = tbill.yield_rate_pct;

    const tiers = VALID_TIERS.map((days) => {
      const yieldPct    = apyPct * days / 365;
      const demoSec     = days * tbill.demo_multiplier;
      return {
        days,
        label:                  `cTBILL-${days}D`,
        apy_pct:                apyPct,
        yield_pct_for_period:   parseFloat(yieldPct.toFixed(4)),
        demo_maturity_seconds:  demoSec,
        demo_maturity_label:    demoSec < 3600
          ? `${demoSec}s (~${Math.round(demoSec / 60)}min)`
          : `${Math.round(demoSec / 60)}min`,
        production_maturity_days: days,
        example_yield_10_algo:  parseFloat((10 * apyPct / 100 * days / 365).toFixed(6)),
        asa_id: tbill.asa_ids[`${days}D` as keyof typeof tbill.asa_ids],
      };
    });

    res.json({
      yield_rate_bps: tbill.yield_rate_bps,
      apy_pct:        apyPct,
      demo_mode:      tbill.demo_mode,
      demo_note:      tbill.demo_mode
        ? `1 day = ${tbill.demo_multiplier}s in demo mode`
        : "Production: real calendar days",
      tiers,
    });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});
