/**
 * Completer Worker - Fallback: completes any REDEEMED orders not yet paid out.
 *
 * After the Issue 2 fix (2026-05-18) the redeemer worker calls completeOrder()
 * in the same cycle immediately after redemption, so this worker should rarely
 * find any orders to process under normal operation.
 *
 * It is kept as a safety net for:
 *   - Orders that were REDEEMED before the fix was deployed
 *   - Any edge case where redeemer's completeOrder call fails mid-cycle
 *     (withRetry in redeemer catches the full block, so this is the last resort)
 */
import { OrderStatus } from "../types";
import * as escrow from "../services/escrow";
import * as logger from "../utils/logger";
import { withRetry } from "../utils/retry";

export async function autoCompleteRedeemedOrders(): Promise<void> {
  const redeemedOrders = await escrow.findOrdersByStatus(OrderStatus.REDEEMED);

  if (redeemedOrders.length === 0) return;

  // Under normal operation this list should be empty — redeemer now completes
  // in the same cycle. Log a warning so we know something unexpected happened.
  logger.warn(`[completer] Found ${redeemedOrders.length} REDEEMED order(s) not yet completed — running fallback completion`);

  for (const { orderId, order } of redeemedOrders) {
    await withRetry(
      () => escrow.completeOrder(orderId, order.seller),
      `complete-fallback(${orderId})`
    ).then((result) => {
      if (result !== null)
        logger.info(
          `[completer] Fallback-completed order ${orderId}: ` +
          `${order.amount / 1e6} ALGO -> seller, ` +
          `${order.yieldEarned / 1e6} ALGO -> platform`
        );
    });
  }
}
