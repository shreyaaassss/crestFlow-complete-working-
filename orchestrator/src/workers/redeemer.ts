/**
 * Redeemer Worker - Detects matured T-bill positions and auto-redeems.
 * Uses Unix timestamp maturity (not round-based).
 *
 * Issue 2 fix (2026-05-18): redeem and completeOrder are now executed in a
 * single cycle rather than two separate cycles.  This eliminates the 30-50s
 * wait between redemption and payout that caused the 4-5 min lifecycle.
 */
import { OrderStatus } from "../types";
import * as escrow from "../services/escrow";
import * as tbill from "../services/tbill";
import * as logger from "../utils/logger";
import { withRetry } from "../utils/retry";
import { getYieldBackend } from "../services/yield-backend";
import * as algorand from "../services/algorand";

export async function redeemExpiredOrders(): Promise<void> {
  const investedOrders = await escrow.findOrdersByStatus(OrderStatus.INVESTED);

  if (investedOrders.length === 0) return;

  for (const { orderId, order } of investedOrders) {
    // Maturity check is cheap — no retry needed
    const matured = await tbill.isMatured(orderId).catch(() => false);
    if (!matured) {
      const maturityTs = await tbill.getMaturity(orderId).catch(() => 0);
      const { timestamp: currentTs }  = await algorand.getCurrentRoundAndTimestamp();
      const remaining  = maturityTs - currentTs;
      if (remaining > 0)
        logger.info(`Order ${orderId}: matures in ${remaining}s (${Math.ceil(remaining / 60)}min)`);
      continue;
    }

    logger.info(`Order ${orderId} matured! Redeeming and completing in single cycle...`);

    await withRetry(async () => {
      // Step 1: Yield backend hook — withdraw from DeFi (mainnet Phase 2, no-op for reserve)
      const yb = getYieldBackend();
      if (yb.name() !== "on-chain-reserve") {
        await yb.withdraw(orderId);
      }

      // Step 2: Redeem on-chain T-bill position
      const totalRedeemed = await tbill.redeem(orderId);
      const yieldEarned   = totalRedeemed > order.amount ? totalRedeemed - order.amount : 0;
      await escrow.receiveFromTreasury(orderId, totalRedeemed);
      await escrow.markRedeemed(orderId, yieldEarned);
      logger.info(
        `Redeemed order ${orderId}: principal=${order.amount / 1e6}, yield=${yieldEarned / 1e6} ALGO [backend=${yb.name()}]`
      );

      // Step 3: Immediately complete — pay seller + platform in same cycle.
      // This was previously done by a separate completer worker cycle, adding
      // 30-50s latency per order (Issue 2 fix).
      await escrow.completeOrder(orderId, order.seller);
      logger.info(
        `Completed order ${orderId}: ${order.amount / 1e6} ALGO -> seller, ${yieldEarned / 1e6} ALGO -> platform`
      );
    }, `redeem-complete(${orderId})`);
  }
}
