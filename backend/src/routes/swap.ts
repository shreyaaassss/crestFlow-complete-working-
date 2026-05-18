/**
 * Swap Router — GET /swap/quote
 *
 * Returns a simulated (mock) or real (tinyman) ALGO → USDC quote.
 * No authentication required — this is read-only price data.
 *
 * GET /swap/quote?microAlgo=5000000
 * → { outputUsdc, priceImpact, algoAmount, usdcAmount, backend, slippageBps, timestamp }
 */
import { Router } from "express";

const router = Router();

// Inline mock quote logic — backend doesn't import the orchestrator's swap service.
// The orchestrator service is the execution layer; the backend exposes quote data
// for the frontend widget using the same hardcoded rate as MockSwapService.
const MOCK_ALGO_PRICE_USD = 0.18;
const USDC_DECIMALS       = 1_000_000;

// Read SWAP_BACKEND so we can surface it in the response
const SWAP_BACKEND = (process.env.SWAP_BACKEND || "mock").toLowerCase();

/**
 * GET /swap/quote?microAlgo=<number>
 * Returns a quote for swapping the given microALGO amount to USDC.
 */
router.get("/quote", (req, res) => {
  try {
    const raw = req.query.microAlgo;
    if (!raw || isNaN(Number(raw))) {
      return res.status(400).json({
        error: "Missing or invalid query param: microAlgo (integer microALGO amount required)",
        example: "/swap/quote?microAlgo=5000000",
      });
    }

    const microAlgo = Math.floor(Number(raw));
    if (microAlgo <= 0) {
      return res.status(400).json({ error: "microAlgo must be a positive integer" });
    }

    const algoAmount = microAlgo / USDC_DECIMALS;

    let outputUsdc: number;
    let priceImpact: number;

    if (SWAP_BACKEND === "tinyman") {
      // Tinyman backend not yet implemented — return stub response clearly marked
      return res.status(501).json({
        error: "Tinyman live quotes not yet implemented. Set SWAP_BACKEND=mock to use simulated quotes.",
        backend: "tinyman-v2",
      });
    } else {
      // Mock: hardcoded $0.18/ALGO, no real pool state
      outputUsdc  = Math.floor(algoAmount * MOCK_ALGO_PRICE_USD * USDC_DECIMALS);
      priceImpact = 0;
    }

    return res.json({
      algoAmount:    algoAmount,              // human-readable
      microAlgo:     microAlgo,               // input
      outputUsdc:    outputUsdc,              // micro-USDC (6 decimals)
      usdcAmount:    outputUsdc / USDC_DECIMALS, // human-readable
      priceImpact:   priceImpact,             // fraction 0–1
      slippageBps:   parseInt(process.env.SWAP_SLIPPAGE_BPS || "50"),
      backend:       SWAP_BACKEND === "tinyman" ? "tinyman-v2" : "mock-swap",
      rateAlgoUsdc:  MOCK_ALGO_PRICE_USD,     // simulated rate
      timestamp:     new Date().toISOString(),
    });
  } catch (err: any) {
    return res.status(500).json({ error: err.message });
  }
});

export { router as swapRouter };
