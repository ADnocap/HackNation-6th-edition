/**
 * Types for the Counterproof demo contract.
 *
 * These are deliberately LOOSE. The frontend is a pure renderer over a
 * hand-authored (later worker-generated) demo.json that another agent owns.
 * Strict types here would turn a shape drift into a build failure, which is
 * exactly the hour-20 outcome this decoupling exists to prevent.
 *
 * Every accessor in lib/data.ts narrows at runtime instead.
 */

/** The pervasive {value, n} quantity. `n: null` is legal only with a `basis`. */
export interface Quantity {
  value: number | string | null;
  n?: number | null;
  basis?: string;
  ci?: [number, number] | null;
}

export type Json = any;

export type ClaimState =
  | "verified"
  | "unverified"
  | "contradicted"
  | "absent_but_expected";

export type ProvenanceClass = "live" | "fixture" | "synthetic";

export type TrendLabel =
  | "improving"
  | "declining"
  | "stable"
  | "insufficient_data";

export type Verdict =
  | "conditional"
  | "probe_further"
  | "pass"
  | "invest"
  | "decide_now";

export interface Demo {
  [key: string]: Json;
}
