/**
 * SwapWidget — ALGO → USDC swap preference selector.
 *
 * Lets users choose how their yield (and optionally principal) is returned:
 *   "none"       → receive ALGO (default, current behaviour)
 *   "yield-only" → yield converted to USDC; principal stays ALGO
 *   "full"       → entire redemption converted to USDC
 *
 * Shows a live quote from /swap/quote for the entered amount.
 * Uses the CrestFlow design system (demo-card, badge, input-text, btn-primary classes).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getSwapQuote, type SwapQuoteResponse } from "../lib/api";

export type SwapMode = "none" | "yield-only" | "full";

interface Props {
  /** ALGO amount in whole units (e.g. 10 for 10 ALGO) */
  algoAmount: number;
  /** Estimated yield in whole ALGO units */
  estimatedYieldAlgo?: number;
  /** Called when the user changes their swap preference */
  onChange?: (mode: SwapMode) => void;
  /** Initial mode */
  defaultMode?: SwapMode;
}

function formatUsdc(micro: number): string {
  return (micro / 1_000_000).toFixed(4);
}

export function SwapWidget({ algoAmount, estimatedYieldAlgo = 0, onChange, defaultMode = "none" }: Props) {
  const [mode, setMode]           = useState<SwapMode>(defaultMode);
  const [quote, setQuote]         = useState<SwapQuoteResponse | null>(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const debounceRef               = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch a quote whenever mode or algoAmount changes (and mode isn't "none")
  const fetchQuote = useCallback(async (swapMode: SwapMode, algoWhole: number) => {
    if (swapMode === "none" || algoWhole <= 0) {
      setQuote(null);
      setError(null);
      return;
    }

    const swapAlgo = swapMode === "full"
      ? algoWhole
      : estimatedYieldAlgo > 0 ? estimatedYieldAlgo : algoWhole * 0.05; // fallback: ~5% yield

    if (swapAlgo <= 0) {
      setQuote(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const q = await getSwapQuote(Math.floor(swapAlgo * 1_000_000));
      setQuote(q);
    } catch (e: any) {
      setError(e?.message ?? "Quote fetch failed");
      setQuote(null);
    } finally {
      setLoading(false);
    }
  }, [estimatedYieldAlgo]);

  // Debounce quote refresh on input changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchQuote(mode, algoAmount), 500);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [mode, algoAmount, fetchQuote]);

  const handleModeChange = (next: SwapMode) => {
    setMode(next);
    onChange?.(next);
  };

  const MODES: { value: SwapMode; label: string; description: string }[] = [
    {
      value: "none",
      label: "Receive ALGO",
      description: "Principal and yield returned in ALGO (default)",
    },
    {
      value: "yield-only",
      label: "Swap yield → USDC",
      description: "Only yield is converted; principal stays in ALGO",
    },
    {
      value: "full",
      label: "Swap all → USDC",
      description: "Entire redemption (principal + yield) converted to USDC",
    },
  ];

  return (
    <div className="demo-card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <p style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", margin: 0 }}>
            Payout Currency
          </p>
          <p style={{ fontSize: 12, color: "var(--muted)", margin: "2px 0 0" }}>
            Choose how you receive funds at maturity
          </p>
        </div>
        {/* Backend badge */}
        <span className="badge" style={{ fontSize: 11 }}>
          <span
            className="badge-dot"
            style={{ background: quote?.backend === "tinyman-v2" ? "var(--success-border)" : "var(--signature-mustard)" }}
          />
          {quote?.backend === "tinyman-v2" ? "Tinyman live" : "Simulated rate"}
        </span>
      </div>

      {/* Mode selector */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {MODES.map((m) => {
          const selected = mode === m.value;
          return (
            <button
              key={m.value}
              id={`swap-mode-${m.value}`}
              onClick={() => handleModeChange(m.value)}
              style={{
                display:         "flex",
                alignItems:      "flex-start",
                gap:             10,
                padding:         "12px 14px",
                borderRadius:    8,
                border:          `1.5px solid ${selected ? "var(--ink)" : "var(--hairline)"}`,
                background:      selected ? "var(--surface-soft)" : "var(--canvas)",
                cursor:          "pointer",
                textAlign:       "left",
                transition:      "border-color 120ms, background 120ms",
              }}
            >
              {/* Radio indicator */}
              <span
                style={{
                  width:        16,
                  height:       16,
                  borderRadius: "50%",
                  border:       `2px solid ${selected ? "var(--ink)" : "var(--hairline)"}`,
                  background:   selected ? "var(--ink)" : "transparent",
                  flexShrink:   0,
                  marginTop:    2,
                  boxShadow:    selected ? "inset 0 0 0 3px var(--canvas)" : "none",
                  transition:   "background 120ms, border-color 120ms",
                }}
              />
              <div>
                <p style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", margin: 0 }}>
                  {m.label}
                </p>
                <p style={{ fontSize: 12, color: "var(--muted)", margin: "2px 0 0" }}>
                  {m.description}
                </p>
              </div>
            </button>
          );
        })}
      </div>

      {/* Quote panel — shown when a swap mode is selected */}
      {mode !== "none" && (
        <div
          style={{
            borderRadius: 8,
            border:       "1px solid var(--hairline)",
            background:   "var(--surface-soft)",
            padding:      "12px 14px",
            minHeight:    56,
          }}
        >
          {loading && (
            <p style={{ fontSize: 12, color: "var(--muted)", margin: 0 }}>
              Fetching quote…
            </p>
          )}
          {error && !loading && (
            <p style={{ fontSize: 12, color: "var(--signature-coral)", margin: 0 }}>
              ⚠ {error}
            </p>
          )}
          {quote && !loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {/* Main quote line */}
              <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
                <span style={{ fontSize: 20, fontWeight: 600, color: "var(--ink)", letterSpacing: "-0.5px" }}>
                  ≈ {formatUsdc(quote.outputUsdc)} USDC
                </span>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>
                  for {quote.algoAmount.toFixed(4)} ALGO
                </span>
              </div>

              {/* Meta row */}
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 11, color: "var(--muted)" }}>
                  Rate: ${quote.rateAlgoUsdc}/ALGO
                </span>
                {quote.priceImpact > 0 && (
                  <span style={{ fontSize: 11, color: "var(--muted)" }}>
                    Price impact: {(quote.priceImpact * 100).toFixed(2)}%
                  </span>
                )}
                <span style={{ fontSize: 11, color: "var(--muted)" }}>
                  Slippage: {quote.slippageBps / 100}%
                </span>
              </div>

              {/* Disclaimer for mock */}
              {quote.backend === "mock-swap" && (
                <p style={{ fontSize: 11, color: "var(--muted)", margin: "4px 0 0", fontStyle: "italic" }}>
                  Simulated quote — actual rate will use live Tinyman pool on mainnet
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
