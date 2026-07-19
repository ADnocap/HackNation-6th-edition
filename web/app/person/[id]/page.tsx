import Link from "next/link";
import {
  Badge, EmptyState, KVTable, LacunaKey, PageHead, Panel, PanelBoundary, ProvenanceBadge,
} from "@/components/primitives";
import { ScoreHistoryChart } from "@/components/charts";
import { AxesDisagreeHeadline, AxisCard, ColdStartBench, ManifestChecklist, normalizeAxes } from "@/components/person";
import { EntityResolution, FounderMarketFit, FounderScorePanel, Milestones, ScoreDefinitionStrip } from "@/components/personDetail";
import { at, getClaims, getOpportunities, getPerson, getSignalRows, getThesis, loadDemo, pick } from "@/lib/data";
import type { Json } from "@/lib/types";
import { arr, fmtNum, fmtTs, humanize, isObj, qval } from "@/lib/util";



export function generateStaticParams() {
  return [{"id": "per_ks"}, {"id": "per_tl"}, {"id": "per_nb"}, {"id": "per_ry"}, {"id": "per_em"}, {"id": "per_jc"}, {"id": "per_sv"}, {"id": "per_dw"}, {"id": "per_pk"}, {"id": "per_hs"}, {"id": "per_aj"}, {"id": "per_lf"}, {"id": "per_bi"}, {"id": "per_gn"}, {"id": "per_cq"}, {"id": "per_ov"}, {"id": "per_yt"}, {"id": "per_zr"}, {"id": "per_mo"}, {"id": "per_dr"}];
}

const CHANNEL_EXPLANATIONS: Record<string, string> = {
  hn_algolia: "A technical discussion showed real building activity before a funding announcement. Followers and popularity were not used.",
  arxiv: "A new research paper created a technical-founder signal before the person had company or investor visibility.",
  uspto_tm_1b: "A self-filed intent-to-use trademark suggests someone is building before they have lawyers, funding, or a public launch.",
  domain_probe: "A young company domain showed an observable product surface, such as pricing, documentation, or checkout.",
  apply_form: "The founder submitted only a company name and deck. The system checks the important claims independently.",
  github_person: "Public code confirmed build cadence. GitHub was used as evidence, not as a popularity contest.",
};

function countManifest(manifest: Json) {
  const rows = Array.isArray(manifest?.rows) ? manifest.rows : [];
  return {
    found: rows.filter((r: Json) => r?.found === true).length,
    missing: rows.filter((r: Json) => r?.found === false && r?.expected === true).length,
    harmless: rows.filter((r: Json) => r?.found === false && r?.expected === false).length,
  };
}

export default async function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { demo, ok, error } = loadDemo();
  if (!ok) return <Panel title="Founder record unavailable" plain="The renderer has no ledger to read."><EmptyState detail={error} /></Panel>;

  const person = getPerson(demo, id);
  if (!person) return <Panel title={`Founder ${id}`} plain="No person exists at this snapshot."><EmptyState detail={`No entry for “${id}” in the people collection.`} /></Panel>;

  const thesis = getThesis(demo);
  const threshold = qval(pick(thesis, "conviction_threshold")) ?? qval(at(demo, "thesis.conviction_threshold"));
  const axes = normalizeAxes(person);
  const bench = pick(person, "cold_start_bench", "coldstart_bench", "bench", "cold_start") ?? null;
  const manifest = pick(person, "expected_evidence_manifest", "evidence_manifest", "manifest", "manifest_checklist") ?? null;
  const history = pick(person, "founder_score_history", "score_history", "founder_score_versions") ?? null;
  const founderScore = pick(person, "founder_score") ?? null;
  const defStrip = pick(person, "score_definition_strip") ?? null;
  const fmf = pick(person, "founder_market_fit") ?? null;
  const entityRes = pick(person, "entity_resolution") ?? null;
  const milestones = pick(person, "milestones") ?? null;
  const channels = arr(pick(person, "channels", "discovery_channels"));
  const linked = getOpportunities(demo).filter((o) => o?.person_id === id);
  const signal = getSignalRows(demo).rows.find((row: Json) => row?.person_id === id) ?? null;
  const primaryChannel = String(signal?.channel ?? channels[0] ?? "");
  const channelExplanation = CHANNEL_EXPLANATIONS[primaryChannel] ?? "The founder matched the saved thesis using observable evidence rather than network status.";
  const manifestCounts = countManifest(manifest);
  const linkedClaims = linked.flatMap((o: Json) => getClaims(o));
  const verifiedClaims = linkedClaims.filter((c: Json) => c?.state === "verified").length;
  const contradictedClaims = linkedClaims.filter((c: Json) => c?.state === "contradicted").length;
  const openClaims = linkedClaims.filter((c: Json) => c?.state === "unverified" || c?.state === "absent_but_expected").length;
  const credibility = founderScore?.credibility;
  const build = founderScore?.build_capability;
  const narrowing = Array.isArray(bench?.what_would_narrow_it) ? bench.what_would_narrow_it[0] : null;

  return (
    <div className="route-page space-y-4">
      <PageHead
        eyebrow="Founder intelligence · evidence weighted"
        title={person.display_name ?? person.person_display_name ?? person.name ?? id}
        lede="Why this founder surfaced, what the evidence supports today, and the next fact that would most reduce uncertainty."
        meta={<><span>{id}</span><span>contact {humanize(person.contact_status)}</span><span>first observed {fmtTs(person.first_observed_at)}</span></>}
        right={<div className="flex flex-col items-end gap-2"><div className="flex gap-2"><ProvenanceBadge value={person.provenance_class} />{person.pseudonymized || person.is_real_person ? <Badge className="border-sky-500/40 bg-sky-500/10 text-sky-300">pseudonymized</Badge> : null}</div>{linked.map((o: Json) => <Link className="route-link" key={o.opportunity_id} href={`/opportunity/${o.opportunity_id}`}>{o.org_name} →</Link>)}</div>}
      />

      <section className="founder-story">
        <header>
          <span className="section-kicker">The simple version</span>
          <h2>Why is this person worth attention?</h2>
          <p>{person?.note ?? signal?.note ?? channelExplanation}</p>
        </header>
        <div className="story-step">
          <span className="story-number">1</span>
          <div><strong>How we found them</strong><p>{channelExplanation}</p><small>{primaryChannel ? humanize(primaryChannel) : "observable signal"}</small></div>
        </div>
        <div className="story-step">
          <span className="story-number">2</span>
          <div><strong>What the evidence says</strong><p>{linkedClaims.length ? `${verifiedClaims} claims verified, ${contradictedClaims} contradicted, and ${openClaims} still need evidence.` : manifestCounts.found ? `${manifestCounts.found} expected artifacts found. ${manifestCounts.missing} meaningful gaps remain.` : `Founder signal ${fmtNum(signal?.score_neutralized ?? 0, 1)} after access advantages are removed. The evidence is still early.`}</p><small>{linkedClaims.length ? `${linkedClaims.length} claims checked` : "early-stage record"}</small></div>
        </div>
        <div className="story-step">
          <span className="story-number">3</span>
          <div><strong>What we do not know</strong><p>{manifestCounts.missing ? `${manifestCounts.missing} expected artifact${manifestCounts.missing === 1 ? " is" : "s are"} missing. This increases uncertainty; it does not automatically make the founder bad.` : contradictedClaims ? "Some claims conflict with the receipts. Read those contradictions before trusting the pitch." : "There is not enough direct evidence yet to be highly confident. A wide range is more honest than a low score."}</p><small>{manifestCounts.harmless ? `${manifestCounts.harmless} harmless absences were not penalized` : "uncertainty stays visible"}</small></div>
        </div>
        <div className="story-step next">
          <span className="story-number">4</span>
          <div><strong>Best next action</strong><p>{linked[0]?.decision?.next_action?.text ?? narrowing ?? (person.contact_status === "none" ? "Keep watching for a product artifact; no public contact channel exists yet." : "Contact the founder with one specific question about the highest-impact missing evidence.")}</p>{linked[0] ? <Link href={`/opportunity/${linked[0].opportunity_id}`}>Open claims and receipts →</Link> : <small>No opportunity opened yet</small>}</div>
        </div>
      </section>

      <section className="founder-score-strip">
        <div><span>Fair discovery signal</span><strong>{typeof signal?.score_neutralized === "number" ? fmtNum(signal.score_neutralized, 1) : "—"}</strong><small>access advantages removed</small></div>
        <div><span>Raw visibility signal</span><strong>{typeof signal?.score_raw === "number" ? fmtNum(signal.score_raw, 1) : "—"}</strong><small>before neutralization</small></div>
        <div><span>Credibility</span><strong>{typeof credibility?.point === "number" ? fmtNum(credibility.point, 1) : "early"}</strong><small>{Array.isArray(credibility?.interval) ? `range ${credibility.interval.join("–")}` : "not enough direct claims"}</small></div>
        <div><span>Build capability</span><strong>{typeof build?.point === "number" ? fmtNum(build.point, 1) : "early"}</strong><small>{Array.isArray(build?.interval) ? `range ${build.interval.join("–")}` : "not enough direct artifacts"}</small></div>
      </section>

      {manifest ? <details className="route-disclosure">
        <summary><span><strong>Evidence map</strong><small>What should exist if the founder’s story is true</small></span></summary>
        <div className="disclosure-body"><PanelBoundary label="manifest"><Panel eyebrow="Evidence map" title="Expected artifacts" plain="Found artifacts, meaningful gaps, and harmless absences are kept separate." right={<LacunaKey className="max-w-[29rem]" />}><ManifestChecklist manifest={manifest} /></Panel></PanelBoundary></div>
      </details> : null}

      {founderScore ? <details className="route-disclosure"><summary><span><strong>Detailed founder profile</strong><small>Credibility, build capability and persistent history</small></span></summary><div className="disclosure-body"><PanelBoundary label="founder score"><Panel eyebrow="Persistent founder memory" title="Founder evidence profile" plain="Credibility and build capability stay separate."><FounderScorePanel score={founderScore} threshold={threshold} /></Panel></PanelBoundary></div></details> : null}

      {person.axes_disagree && person.axes_disagree_headline ? <AxesDisagreeHeadline headline={person.axes_disagree_headline} axes={axes} /> : null}

      <details className="route-disclosure">
        <summary><span><strong>Decision axes</strong><small>Founder, market and idea-versus-market stay separate</small></span></summary>
        <div className="disclosure-body">
          {axes.length ? <div className="grid grid-cols-1 gap-3 md:grid-cols-3">{axes.map(({ key, axis }) => <AxisCard key={key} axisKey={key} axis={axis} threshold={threshold} />)}</div> : <EmptyState text="No axis scores at this snapshot." />}
        </div>
      </details>

      <details className="route-disclosure">
        <summary><span><strong>How the estimate was formed</strong><small>Cold-start prior, history and score definitions</small></span></summary>
        <div className="disclosure-body space-y-4">
          {defStrip ? <ScoreDefinitionStrip strip={defStrip} /> : null}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Panel title="Cold-start bench" plain="How much is direct evidence, how much is a reference-class prior, and what would narrow the range."><ColdStartBench bench={bench} blockedReason={pick(person, "cold_start_bench_blocked_reason")} /></Panel>
            <Panel title="Founder score history" plain="Append-only versions preserve the person’s record across ventures.">{history ? <ScoreHistoryChart history={history} /> : <EmptyState text="No score history at this snapshot." />}</Panel>
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {fmf ? <Panel title="Founder–market fit" plain="Domain-exposure evidence with an interval, not a personality guess."><FounderMarketFit fmf={fmf} /></Panel> : null}
            {entityRes ? <Panel title="Entity resolution" plain="Why separate venture records are believed to belong to the same human."><EntityResolution er={entityRes} /></Panel> : null}
          </div>
          {milestones ? <Panel title="Milestones" plain="Timestamped observations from the same ledger."><Milestones milestones={milestones} note={pick(person, "milestones_note")} /></Panel> : null}
        </div>
      </details>

      {isObj(person) ? <details className="route-disclosure"><summary><span><strong>Complete record</strong><small>Every remaining field, for auditability</small></span></summary><div className="disclosure-body"><KVTable obj={person} exclude={["axes","axis_scores","scores","cold_start_bench","coldstart_bench","bench","expected_evidence_manifest","evidence_manifest","manifest","founder_score_history","score_history","founder_score_versions","founder_score","score_definition_strip","founder_market_fit","entity_resolution","milestones","milestones_note"]} /></div></details> : null}
    </div>
  );
}
