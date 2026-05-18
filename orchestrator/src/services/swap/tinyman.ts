/**
 * TinymanSwapService — Mainnet Phase 3 Stub
 *
 * Will execute real ALGO → USDC swaps via Tinyman v2 AMM on Algorand mainnet.
 * NOT YET IMPLEMENTED. isSupported() returns false to prevent accidental activation.
 *
 * To implement (Mainnet Phase 3):
 *   1. npm install @tinymanorg/tinyman-js-sdk --save  (in orchestrator/)
 *   2. Import { Tinyman } or equivalent from "@tinymanorg/tinyman-js-sdk"
 *   3. Fetch pool info for ALGO/USDC pair using TINYMAN_APP_ID + USDC_ASA_ID
 *   4. Build swap txn group via Tinyman SDK (AtomicTransactionComposer)
 *   5. Sign with orchestratorAccount and submit to algodClient
 *   6. Parse inner txn logs to get actual USDC received
 *   7. Flip isSupported() to true
 *   8. Set SWAP_BACKEND=tinyman in mainnet .env
 *
 * Testnet note: Tinyman v2 is deployed on testnet but USDC (ASA 31566704) is
 * mainnet-only. Use a testnet mock USDC ASA for integration testing.
 */
import { SwapService } from "./interface";
import * as logger from "../../utils/logger";

const TINYMAN_APP_ID  = parseInt(process.env.TINYMAN_APP_ID  || "0");
const USDC_ASA_ID     = parseInt(process.env.USDC_ASA_ID     || "31566704");
const SLIPPAGE_BPS    = parseInt(process.env.SWAP_SLIPPAGE_BPS || "50"); // 0.5%

export class TinymanSwapService implements SwapService {
  async getQuote(microAlgoAmount: number): Promise<{ outputUsdc: number; priceImpact: number }> {
    // TODO (Mainnet Phase 3):
    // 1. import { Tinyman } from "@tinymanorg/tinyman-js-sdk"
    // 2. const pool = await Tinyman.getPool(algodClient, TINYMAN_APP_ID, 0, USDC_ASA_ID)
    // 3. const quote = pool.getFixedInputSwapQuote({ assetIn: ALGO, amount: microAlgoAmount, slippage: SLIPPAGE_BPS/10000 })
    // 4. return { outputUsdc: Number(quote.assetOutAmount), priceImpact: quote.priceImpact }
    logger.warn(`TinymanSwapService.getQuote() not yet implemented — set SWAP_BACKEND=mock`);
    throw new Error("Tinyman swap backend not yet implemented — set SWAP_BACKEND=mock");
  }

  async swap(microAlgoAmount: number, swapperAddress: string): Promise<number> {
    // TODO (Mainnet Phase 3):
    // 1. Get quote with slippage applied (minOutput = outputUsdc * (1 - SLIPPAGE_BPS/10000))
    // 2. Build Tinyman v2 fixed-input swap txn group via AtomicTransactionComposer
    // 3. Sign all txns with orchestratorAccount (or swapperAddress if user-initiated)
    // 4. Submit group and wait for confirmation
    // 5. Decode inner txn asset transfer log to get actual USDC received
    // 6. Return actual USDC received as micro-USDC
    logger.warn(`TinymanSwapService.swap() not yet implemented for ${swapperAddress} — set SWAP_BACKEND=mock`);
    throw new Error("Tinyman swap backend not yet implemented — set SWAP_BACKEND=mock");
  }

  isSupported(): boolean {
    // Flip to true only after full SDK integration is complete and tested
    return false;
  }

  name(): string {
    return "tinyman-v2";
  }
}
