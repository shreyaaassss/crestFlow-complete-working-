/**
 * Swap Service Factory
 *
 * Reads SWAP_BACKEND env var and returns the appropriate SwapService singleton.
 *
 * SWAP_BACKEND=mock     → MockSwapService    (default, testnet — no real swaps)
 * SWAP_BACKEND=tinyman  → TinymanSwapService (mainnet — real Tinyman v2 AMM)
 *
 * Switching only requires a .env change + orchestrator restart.
 * The factory guards on isSupported() so a stub cannot be accidentally activated.
 */
import { SwapService } from "./interface";
import { MockSwapService } from "./mock";
import { TinymanSwapService } from "./tinyman";

let _instance: SwapService | null = null;

export function getSwapService(): SwapService {
  if (_instance) return _instance;

  const backend = (process.env.SWAP_BACKEND || "mock").toLowerCase();

  switch (backend) {
    case "tinyman": {
      const svc = new TinymanSwapService();
      if (!svc.isSupported()) {
        throw new Error(
          "Tinyman swap backend not yet implemented. " +
          "Complete the TinymanSwapService SDK integration first, " +
          "flip isSupported() to true, then set SWAP_BACKEND=tinyman."
        );
      }
      _instance = svc;
      break;
    }
    default:
      // "mock" or any unrecognised value — always safe
      _instance = new MockSwapService();
  }

  return _instance;
}

/** Reset singleton — for testing only. */
export function _resetSwapService(): void {
  _instance = null;
}

export type { SwapService } from "./interface";
