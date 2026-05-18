/**
 * Investor Worker - Detects PENDING eligible orders and invests into T-bills.
 */
import { OrderStatus } from "../types";
import * as escrow from "../services/escrow";
import * as tbill from "../services/tbill";
import * as logger from "../utils/logger";
import { withRetry } from "../utils/retry";
import { getYieldBackend } from "../services/yield-backend";

import * as algorand from "../services/algorand";

export async function investPendingOrders(): Promise<void> {
  const pendingOrders = await escrow.findOrdersByStatus(OrderStatus.PENDING);
  const eligible = pendingOrders.filter((o) => o.order.investEligible);

  if (eligible.length === 0) return;

  logger.info(`Found ${eligible.length} eligible PENDING order(s) to invest`);
  
  const currentRound = await algorand.getCurrentRound();
  const currentTs = await algorand.getCurrentBlockTimestamp();

  for (const { orderId, order } of eligible) {
    await withRetry(async () => {
      const lockDurationRounds = order.lockUntil - order.createdAt;
      const tbillType = tbill.selectTBillType(lockDurationRounds);
      await escrow.transferToTreasury(orderId);
      
      // Convert the order creation round to a Unix timestamp (~3.3s/block)
      // using the exact Algorand network timestamp to avoid AWS/node clock drift.
      const deltaSec = (currentRound - order.createdAt) * 3.3;
      const orderCreatedAtTimestamp = Math.floor(currentTs - deltaSec);

      // Pass orderCreatedAtTimestamp so the contract anchors maturity to order creation
      // time, not to the (later) investment time.
      await tbill.invest(orderId, order.amount, tbillType, orderCreatedAtTimestamp);

      // Yield backend hook — routes to DeFi on mainnet Phase 2, no-op for reserve
      const yb = getYieldBackend();
      if (yb.name() !== "on-chain-reserve") {
        await yb.deposit(orderId, order.amount, tbillType);
      }

      await escrow.markInvested(orderId);
      logger.info(
        `Invested order ${orderId}: ${order.amount / 1e6} ALGO -> ${tbill.tbillLabel(tbillType)} [backend=${yb.name()}]`
      );
    }, `invest(${orderId})`);
  }
}
