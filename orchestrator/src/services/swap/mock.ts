/**
 * MockSwapService — Testnet stub for the swap backend.
 *
 * Returns a hardcoded simulated USDC quote without executing any real swap.
 * isSupported() returns true so it can be used safely on testnet.
 * Switch to TinymanSwapService on mainnet via SWAP_BACKEND=tinyman.
 */
import { SwapService } from "./interface";
import * as logger from "../../utils/logger";

// Hardcoded rate for testnet simulation: 1 ALGO = $0.18 USDC
const MOCK_ALGO_PRICE_USD = 0.18;

export class MockSwapService implements SwapService {
  async getQuote(microAlgoAmount: number): Promise<{ outputUsdc: number; priceImpact: number }> {
    const algoAmount = microAlgoAmount / 1_000_000;
    // USDC has 6 decimals, same as ALGO micro-units
    const outputUsdc = Math.floor(algoAmount * MOCK_ALGO_PRICE_USD * 1_000_000);
    logger.info(`[mock-swap] Quote: ${algoAmount} ALGO → ${outputUsdc / 1e6} USDC (simulated @ $${MOCK_ALGO_PRICE_USD})`);
    return { outputUsdc, priceImpact: 0 };
  }

  async swap(microAlgoAmount: number, swapperAddress: string): Promise<number> {
    const { outputUsdc } = await this.getQuote(microAlgoAmount);
    logger.info(
      `[mock-swap] Simulated swap: ${microAlgoAmount / 1e6} ALGO → ${outputUsdc / 1e6} USDC ` +
      `for ${swapperAddress} (no real transaction on testnet)`
    );
    return outputUsdc;
  }

  isSupported(): boolean {
    // Mock is always safe — no real funds moved
    return true;
  }

  name(): string {
    return "mock-swap";
  }
}
