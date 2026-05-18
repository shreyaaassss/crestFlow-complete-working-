/**
 * SwapService interface — ALGO → USDC swap backend abstraction.
 *
 * Follows the same env-flag-switch pattern as YieldBackend:
 *   SWAP_BACKEND=mock    → MockSwapService    (testnet default, no real swaps)
 *   SWAP_BACKEND=tinyman → TinymanSwapService (mainnet, real Tinyman v2 AMM)
 *
 * Both methods deal in micro-units:
 *   - ALGO amounts: microALGO  (1 ALGO = 1_000_000)
 *   - USDC amounts: micro-USDC (1 USDC = 1_000_000, 6 decimals)
 */

export interface SwapService {
  /**
   * Get a quote for swapping microAlgo → USDC without executing the swap.
   * Returns estimated USDC output (micro-USDC) and price impact (0–1 fraction).
   */
  getQuote(microAlgoAmount: number): Promise<{ outputUsdc: number; priceImpact: number }>;

  /**
   * Execute the swap and return the actual micro-USDC received.
   * swapperAddress is the Algorand account whose ALGO is being swapped.
   */
  swap(microAlgoAmount: number, swapperAddress: string): Promise<number>;

  /**
   * Whether this backend is fully implemented and safe to activate.
   * A stub must return false; flip to true only after full integration.
   */
  isSupported(): boolean;

  /** Unique name for logging and factory routing. */
  name(): string;
}
