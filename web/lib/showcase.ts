import type { Demo, Json } from "./types";

/**
 * Offline showcase records.
 *
 * These scenarios exist so the hackathon demo can show every meaningful state
 * when collectors or third-party services are unavailable. They are always
 * marked `synthetic` and every receipt says it is a fixture. Nothing here is
 * presented as a live fetch.
 */

const ASOF = "2026-07-19T10:40:00Z";

type ClaimState = "verified" | "unverified" | "contradicted" | "absent_but_expected";

interface ClaimSpec {
  id: string;
  type: string;
  text: string;
  state: ClaimState;
  source: string;
  finding: string;
  delta: number;
  expected?: boolean;
  material?: boolean;
}

function claim(spec: ClaimSpec): Json {
  const found = spec.state !== "absent_but_expected";
  const evidenceId = `evd_${spec.id}`;
  const sum = spec.state === "unverified" ? spec.delta : spec.delta;
  const posterior = spec.state === "verified" ? 0.93 : spec.state === "contradicted" ? 0.06 : spec.state === "unverified" ? 0.55 : null;
  const confidence = Math.abs(sum) >= 2 ? "high" : Math.abs(sum) >= 0.5 ? "medium" : "low";
  const evidence = {
    evidence_id: evidenceId,
    kind: found ? (spec.delta < 0 ? "refuting" : "corroborating") : "expected_absent",
    artifact_type: spec.source,
    found,
    expected: spec.expected ?? true,
    penalised: spec.state === "absent_but_expected",
    source_class: spec.source,
    source_url: found ? `https://${spec.source.replace(/_/g, "-")}.fixture.test/${spec.id}` : null,
    final_url: found ? `https://${spec.source.replace(/_/g, "-")}.fixture.test/${spec.id}` : null,
    http_status: found ? 200 : 404,
    fetched_at: ASOF,
    fetch_method: "offline_fixture",
    verifier: "showcase_fixture",
    excerpt: found ? `Fixture response for: ${spec.text}` : null,
    finding: spec.finding,
    log_odds_delta: spec.delta,
    interval_widen: found ? 0 : 3.5,
    provenance_class: "synthetic",
    findability_prior: { value: spec.expected === false ? 0.12 : 0.71, n: 28 },
  };

  return {
    claim_id: spec.id,
    claim_type: spec.type,
    claim_text: spec.text,
    state: spec.state,
    confidence_band: confidence,
    posterior_prob: posterior,
    is_material: spec.material ?? true,
    is_manifest_predicted: spec.state === "absent_but_expected",
    memo_blocked: spec.state === "unverified" && Math.abs(sum) < 0.5,
    evaluated_at: ASOF,
    asof: ASOF,
    n_evidence: { value: 1, n: 1 },
    log_odds: {
      terms: [{
        label: `${found ? "Offline fixture check" : "Expected artifact not found"} — ${spec.finding}`,
        source_class: spec.source,
        value: spec.delta,
        running_total: spec.delta,
        evidence_id: evidenceId,
        n: 1,
      }],
      sum,
      posterior_prob: posterior,
      arithmetic_string: `${spec.delta > 0 ? "+" : ""}${spec.delta.toFixed(1)} = ${spec.delta > 0 ? "+" : ""}${spec.delta.toFixed(1)}`,
      threshold_verified: 2,
      threshold_contradicted: -2,
      verdict_sentence:
        spec.state === "verified" ? "The fixture evidence clears the verification threshold." :
        spec.state === "contradicted" ? "The fixture evidence crosses the contradiction threshold." :
        spec.state === "absent_but_expected" ? "This artifact was expected but missing. It widens uncertainty rather than lowering the founder score." :
        "The available fixture evidence is not strong enough for a verdict, so the claim remains unverified.",
      n_terms: { value: 1, n: 1 },
      computed_by: "offline_showcase",
    },
    interval_widen_total: found ? 0 : 3.5,
    evidence: [evidence],
    receipt: {
      title: `${spec.type.replace(/_/g, " ")} — ${spec.text}`,
      left: {
        kind: "authored_showcase_claim",
        source_class: "synthetic",
        label: "Founder claim — offline showcase",
        observed_at: ASOF,
        excerpt: spec.text,
        provenance_class: "synthetic",
        caption: "Authored example used to demonstrate the workflow while external services are offline.",
      },
      right: found ? [{
        kind: "offline_fixture",
        label: spec.source.replace(/_/g, " "),
        verifier: "showcase_fixture",
        fetch_method: "offline_fixture",
        source_url: evidence.source_url,
        final_url: evidence.final_url,
        http_status: 200,
        fetched_at: ASOF,
        excerpt: evidence.excerpt,
        finding: spec.finding,
        provenance_class: "synthetic",
      }] : [],
    },
  };
}

interface Scenario {
  id: string;
  personId: string;
  person: string;
  org: string;
  sector: string;
  channel: string;
  stage: string;
  verdict: string;
  verdictLabel: string;
  bindingAxis: string;
  nextAction: string;
  slaState: string;
  hoursRemaining: number;
  claims: ClaimSpec[];
}

const SCENARIOS: Scenario[] = [
  {
    id: "opp_ferrous", personId: "per_cq", person: "C. Q.", org: "Ferrous Devtools",
    sector: "devtools", channel: "hn_algolia", stage: "diligence",
    verdict: "probe_further", verdictLabel: "PROBE FURTHER", bindingAxis: "idea_vs_market",
    nextAction: "Request the deployment logs for the five named design partners.",
    slaState: "at_risk", hoursRemaining: 3.4,
    claims: [
      { id: "clm_ferrous_release", type: "product_release", text: "A working CLI has shipped publicly.", state: "verified", source: "github_release", finding: "Signed release, package checksum and install instructions exist.", delta: 2.7 },
      { id: "clm_ferrous_teams", type: "active_teams", text: "More than 500 engineering teams use the product weekly.", state: "contradicted", source: "public_telemetry", finding: "The authored telemetry fixture contains 74 weekly workspaces, not 500.", delta: -3.1 },
      { id: "clm_ferrous_soc2", type: "security", text: "SOC 2 Type II is in progress.", state: "unverified", source: "trust_center", finding: "A trust-center page exists but names no auditor or review window.", delta: 0.4 },
      { id: "clm_ferrous_dpa", type: "enterprise_readiness", text: "A standard DPA should exist for the claimed enterprise pilots.", state: "absent_but_expected", source: "legal_artifact", finding: "The fixture trust center has no DPA download.", delta: -0.2 },
    ],
  },
  {
    id: "opp_gantry", personId: "per_hs", person: "H. S.", org: "Gantry Labs",
    sector: "ai_infra", channel: "arxiv", stage: "screening",
    verdict: "invest", verdictLabel: "ADVANCE TO DILIGENCE", bindingAxis: "founder",
    nextAction: "Run a technical reference call on the claimed inference benchmark.",
    slaState: "met", hoursRemaining: 18.2,
    claims: [
      { id: "clm_gantry_paper", type: "technical_authorship", text: "The founder is first author of the inference-routing paper.", state: "verified", source: "arxiv_fixture", finding: "Authorship and submission history match the founder record.", delta: 2.5 },
      { id: "clm_gantry_benchmark", type: "performance", text: "Routing cuts inference cost by 38% on the published workload.", state: "verified", source: "benchmark_fixture", finding: "The included benchmark reproduces a 36–39% reduction across three runs.", delta: 2.3 },
      { id: "clm_gantry_pilot", type: "traction", text: "Two enterprise teams are running pilots.", state: "unverified", source: "customer_reference", finding: "One anonymized architecture diagram exists; customer identity is not independently checkable.", delta: 0.7 },
      { id: "clm_gantry_modelcard", type: "safety", text: "A model-card and failure-mode note should exist for the production pilot.", state: "absent_but_expected", source: "safety_artifact", finding: "No model-card was present in the fixture data room.", delta: -0.2 },
    ],
  },
  {
    id: "opp_marlin", personId: "per_jc", person: "J. C.", org: "Marlin Compliance",
    sector: "regtech", channel: "apply_form", stage: "decision",
    verdict: "conditional", verdictLabel: "CONDITIONAL $150K", bindingAxis: "founder",
    nextAction: "Hold allocation until the bank pilot and churn cohort are verified.",
    slaState: "met", hoursRemaining: 9.1,
    claims: [
      { id: "clm_marlin_pilot", type: "customer_pilot", text: "A regional bank signed a paid pilot.", state: "verified", source: "signed_contract", finding: "Fixture contract carries dates, scope and a redacted counterparty signature.", delta: 3.0 },
      { id: "clm_marlin_churn", type: "retention", text: "The company has had zero churn since launch.", state: "contradicted", source: "billing_export", finding: "Two of eleven fixture customers cancelled during the stated window.", delta: -2.8 },
      { id: "clm_marlin_arr", type: "revenue", text: "Annualized recurring revenue is €180K.", state: "unverified", source: "bank_export", finding: "Invoices support €142K annualized; one contract start date remains unclear.", delta: -0.7 },
      { id: "clm_marlin_pentest", type: "security", text: "A penetration test should exist before the bank production launch.", state: "absent_but_expected", source: "security_audit", finding: "No pentest report or scheduled vendor was included.", delta: -0.2 },
    ],
  },
  {
    id: "opp_kestrel", personId: "per_lf", person: "L. F.", org: "Kestrel Freight",
    sector: "logistics_infra", channel: "uspto_tm_1b", stage: "screening",
    verdict: "pass", verdictLabel: "PASS FOR NOW", bindingAxis: "market",
    nextAction: "Archive the record and reopen if a live carrier integration appears.",
    slaState: "met", hoursRemaining: 20.5,
    claims: [
      { id: "clm_kestrel_tm", type: "company_intent", text: "A self-filed intent-to-use trademark exists.", state: "verified", source: "uspto_fixture", finding: "The offline trademark fixture shows a 1(b) filing with no attorney of record.", delta: 2.4 },
      { id: "clm_kestrel_product", type: "product_state", text: "The freight reconciliation product is live.", state: "contradicted", source: "domain_probe_fixture", finding: "The fixture domain is a waitlist; no application or transaction endpoint exists.", delta: -2.6 },
      { id: "clm_kestrel_loi", type: "traction", text: "Three carriers signed letters of intent.", state: "unverified", source: "data_room", finding: "The letters were not present in the authored data room.", delta: 0 },
      { id: "clm_kestrel_api", type: "integration", text: "API documentation should exist for a live carrier integration.", state: "absent_but_expected", source: "developer_docs", finding: "No API reference or sandbox endpoint was found.", delta: -0.2 },
    ],
  },
];

function opportunity(s: Scenario): Json {
  const builtClaims = s.claims.map(claim);
  const distribution = builtClaims.reduce((acc: Record<string, number>, c: Json) => {
    acc[c.state] = (acc[c.state] ?? 0) + 1;
    return acc;
  }, {});
  return {
    opportunity_id: s.id,
    org_name: s.org,
    person_id: s.personId,
    person_display_name: s.person,
    sector: s.sector,
    track: s.channel === "apply_form" ? "inbound" : "outbound",
    channel: s.channel,
    opened_by: "offline_showcase",
    provenance_class: "synthetic",
    demo_mode: "offline_showcase",
    first_signal_at: "2026-07-19T06:00:00Z",
    opened_at: "2026-07-19T06:04:00Z",
    sla: {
      state: s.slaState,
      hours_elapsed: { value: 5.6, n: null, basis: "authored showcase clock" },
      hours_remaining: { value: s.hoursRemaining, n: null, basis: "authored showcase clock" },
      blocked_on: s.slaState === "at_risk" ? "founder_artifact" : null,
      badge: `${s.org} is an authored offline scenario. Clock state demonstrates the product behavior.`,
    },
    stage_timeline: [
      { stage: "sourcing", entered_at: "2026-07-19T06:00:00Z", entered_by: "showcase_fixture", duration_minutes: 4, exited_reason: "advanced", wait_is_human: false, note: `Signal created from the ${s.channel.replace(/_/g, " ")} offline fixture.` },
      { stage: "screening", entered_at: "2026-07-19T06:04:00Z", entered_by: "system", duration_minutes: s.stage === "screening" ? null : 8, exited_reason: s.stage === "screening" ? null : "advanced", wait_is_human: false, note: "Deterministic screen applied to fixture observations." },
      ...(s.stage === "diligence" || s.stage === "decision" ? [{ stage: "diligence", entered_at: "2026-07-19T06:12:00Z", entered_by: "system", duration_minutes: s.stage === "decision" ? 22 : null, exited_reason: s.stage === "decision" ? "advanced" : null, wait_is_human: false, note: "Claims checked against authored receipts; no network call required." }] : []),
      ...(s.stage === "decision" ? [{ stage: "decision", entered_at: "2026-07-19T06:34:00Z", entered_by: "system", duration_minutes: null, exited_reason: null, wait_is_human: false, is_terminal: true }] : []),
    ],
    claim_distribution: {
      ...distribution,
      n: builtClaims.length,
      reconciliation: `${distribution.verified ?? 0} verified + ${distribution.unverified ?? 0} unverified + ${distribution.contradicted ?? 0} contradicted + ${distribution.absent_but_expected ?? 0} expected gaps = ${builtClaims.length}.`,
      plain_line: "Offline showcase data. The states and receipts are fully interactive; no external service response is being claimed.",
    },
    claims: builtClaims,
    claims_note: "AUTHORED SHOWCASE — these records demonstrate the complete claim workflow while external services are unavailable.",
    decision: {
      asof: ASOF,
      verdict: s.verdict,
      verdict_label: s.verdictLabel,
      binding_axis: s.bindingAxis,
      binding_axis_reason: `The ${s.bindingAxis.replace(/_/g, " ")} axis is the limiting read in this authored scenario.`,
      axes_disagree: s.verdict === "conditional",
      interval_low: s.verdict === "invest" ? 58 : s.verdict === "pass" ? 31 : 47,
      interval_width: { value: s.verdict === "pass" ? 34 : 24, n: builtClaims.length },
      max_interval_width: 30,
      conviction_threshold: 55,
      gate_passed: s.verdict === "invest" || s.verdict === "conditional",
      gate_rule_applied: "offline showcase decision ladder",
      gate_sentence: `${s.verdictLabel}. This outcome is derived from the visible fixture claims and exists to demonstrate product behavior offline.`,
      n_claims: { value: builtClaims.length, n: builtClaims.length },
      conditions_to_close: s.verdict === "conditional" ? [{ text: s.nextAction, resolves_claim_id: s.claims.find((c) => c.state !== "verified")?.id, owner: "analyst", due_at: "2026-07-21" }] : [],
      falsification_conditions_before_wire: [],
      next_action: { text: s.nextAction, owner: "analyst", due_at: "2026-07-20T12:00:00Z" },
      portfolio_conflict: "No conflicting position in the authored showcase portfolio.",
    },
    memo: null,
    memo_blocked_reason: s.stage === "decision" ? "Full memo generation is not enabled for authored showcase scenarios. The claim receipts and decision remain available." : `Memo waits until this opportunity reaches decision. Current stage: ${s.stage}.`,
    sourcing_origin: {
      title: `Discovered through ${s.channel.replace(/_/g, " ")}`,
      plain_line: "This is an offline fixture that mirrors the shape a live collector would write.",
      channel: s.channel,
      provenance_class: "synthetic",
      why_it_fired: `The fixture crossed the saved thesis threshold for ${s.sector.replace(/_/g, " ")}.`,
    },
  };
}

export function withShowcaseData(input: Demo): Demo {
  const demo: Demo = { ...input };
  const baseOpps = input.opportunities && typeof input.opportunities === "object" ? input.opportunities : {};
  const added = Object.fromEntries(SCENARIOS.map((s) => [s.id, opportunity(s)]));
  demo.opportunities = { ...baseOpps, ...added };

  const scenarioByPerson = new Map(SCENARIOS.map((s) => [s.personId, s]));
  const feed = input.signal_feed && typeof input.signal_feed === "object" ? input.signal_feed : {};
  demo.signal_feed = {
    ...feed,
    rows: Array.isArray(feed.rows) ? feed.rows.map((row: Json) => {
      const s = scenarioByPerson.get(row?.person_id);
      if (!s) return row;
      return {
        ...row,
        opportunity_id: s.id,
        stage: s.stage,
        verdict: s.verdict,
        verdict_label: s.verdictLabel,
        binding_axis: s.bindingAxis,
        n_claims: { value: s.claims.length, n: s.claims.length },
        sla: {
          state: s.slaState,
          hours_remaining: { value: s.hoursRemaining, n: null, basis: "authored showcase clock" },
          hours_elapsed: { value: 5.6, n: null, basis: "authored showcase clock" },
          blocked_on: s.slaState === "at_risk" ? "founder_artifact" : null,
        },
      };
    }) : feed.rows,
  };

  demo.meta = {
    ...(input.meta ?? {}),
    showcase_mode: true,
    showcase_note: "Four authored offline opportunities are layered onto the worker export. They are marked AUTHORED everywhere and make the full workflow testable without third-party services.",
    showcase_opportunity_ids: SCENARIOS.map((s) => s.id),
  };
  return demo;
}
