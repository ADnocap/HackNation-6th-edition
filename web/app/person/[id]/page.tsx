import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Badge,
  EmptyState,
  KVTable,
  LacunaKey,
  N,
  PageHead,
  Panel,
  PanelBoundary,
  ProvenanceBadge,
  Refusal,
  Stat,
} from "@/components/primitives";
import { ScoreHistoryChart } from "@/components/charts";
import {
  AxesDisagreeHeadline,
  AxisCard,
  ColdStartBench,
  ManifestChecklist,
  normalizeAxes,
} from "@/components/person";
import {
  EntityResolution,
  FounderMarketFit,
  FounderScorePanel,
  Milestones,
  ScoreDefinitionStrip,
} from "@/components/personDetail";
import {
  at,
  getOpportunities,
  getPerson,
  getThesis,
  loadDemo,
  pick,
} from "@/lib/data";
import type { Json } from "@/lib/types";
import { arr, fmtTs, humanize, isObj, qval } from "@/lib/util";

export const dynamic = "force-dynamic";

export default async function PersonPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { demo, ok, error } = loadDemo();

  if (!ok) {
    return (
      <Panel title="Person" plain="The renderer has no ledger to read.">
        <EmptyState text="Reading the ledger at asof… nothing found." detail={error} />
      </Panel>
    );
  }

  const person = getPerson(demo, id);
  if (!person) {
    return (
      <Panel title={`Person ${id}`} plain="No such person at this asof.">
        <EmptyState
          text="No data at this asof. Move the point-in-time control forward."
          detail={`No entry for "${id}" in the people collection.`}
        />
      </Panel>
    );
  }

  const thesis = getThesis(demo);
  const convictionThreshold =
    qval(pick(thesis, "conviction_threshold")) ??
    qval(at(demo, "thesis.conviction_threshold")) ??
    null;

  const axes = normalizeAxes(person);
  const disagreeHeadline =
    person.axes_disagree_headline ??
    at(person, "axes_disagree.headline") ??
    (person.axes_disagree ? "Axes disagree." : null);

  const bench =
    pick(person, "cold_start_bench", "coldstart_bench", "bench", "cold_start") ??
    null;
  const manifest =
    pick(
      person,
      "expected_evidence_manifest",
      "evidence_manifest",
      "manifest",
      "manifest_checklist"
    ) ?? null;
  const history =
    pick(
      person,
      "founder_score_history",
      "score_history",
      "founder_score_versions"
    ) ?? null;

  const founderScore = pick(person, "founder_score") ?? null;
  const defStrip = pick(person, "score_definition_strip") ?? null;
  const fmf = pick(person, "founder_market_fit") ?? null;
  const entityRes = pick(person, "entity_resolution") ?? null;
  const milestones = pick(person, "milestones") ?? null;
  const benchBlocked = pick(person, "cold_start_bench_blocked_reason") ?? null;

  const contactStatus = pick(person, "contact_status");
  const channels = arr(pick(person, "channels", "discovery_channels"));

  // Opportunities this person appears in — the two-venture spine.
  const linked = getOpportunities(demo).filter((o) => o?.person_id === id);

  return (
    <div className="space-y-4">
      {/* Header */}
      <PageHead
        // The eyebrow and lede must be true of THIS person: one of these two
        // founders has a two-venture history and describing him as
        // track-record-less would be exactly the kind of unearned sentence
        // this product exists to refuse.
        eyebrow={bench ? "Founder record · cold-start bench" : "Founder record"}
        title={
          person.display_name ??
          person.person_display_name ??
          person.name ??
          id
        }
        lede="Everything we can say about this person, and how much of it is evidence rather than a prior. The Founder Score here belongs to the human rather than the company: it persists across ventures, and nothing resets it."
        meta={
          <>
            <span className="text-zinc-400">{id}</span>
            {contactStatus ? (
              <span title="Discovered is not the same as reachable. We print the difference.">
                contact {humanize(contactStatus)}
              </span>
            ) : null}
            {channels.length ? (
              <span>
                channels{" "}
                {channels
                  .map((c: Json) => (typeof c === "string" ? c : c?.channel_id))
                  .filter(Boolean)
                  .join(", ")}
              </span>
            ) : null}
            {person.first_observed_at ? (
              <span>first observed {fmtTs(person.first_observed_at)}</span>
            ) : null}
          </>
        }
        right={
          <div className="flex flex-col items-end gap-2">
            <div className="flex flex-wrap justify-end gap-1.5">
              <ProvenanceBadge value={person.provenance_class} />
              {person.pseudonymized || person.is_real_person ? (
                <Badge
                  className="border-sky-500/40 bg-sky-500/10 text-sky-300"
                  title="Real people are pseudonymized: initials + channel + signals only. The Refuter is disabled on real-person entities."
                >
                  pseudonymized
                </Badge>
              ) : null}
            </div>
            {linked.length ? (
              <div className="flex flex-wrap justify-end gap-1.5">
                {linked.map((o: Json) => (
                  <Link
                    key={o.opportunity_id}
                    href={`/opportunity/${o.opportunity_id}`}
                    className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11.5px] text-zinc-300 transition-colors hover:border-zinc-600 hover:text-zinc-50"
                  >
                    {o.org_name ?? o.opportunity_id} →
                  </Link>
                ))}
              </div>
            ) : null}
          </div>
        }
      />

      {/* Which "founder score" is which — stated before any number is shown. */}
      {defStrip ? <ScoreDefinitionStrip strip={defStrip} /> : null}

      {/* Founder Score — persistent, per person, never resets */}
      {founderScore ? (
        <PanelBoundary label="founder score">
          <Panel
            eyebrow="Memory · append-only · never resets"
            title="Founder Score — belongs to the person, not the company"
            plain="This is not the three-axis score. It lives in Memory, it persists across applications and companies, and there is no code path that resets it. Its two components are kept apart on purpose: a lie about revenue must not erase a real build record."
          >
            <FounderScorePanel
              score={founderScore}
              threshold={convictionThreshold}
            />
          </Panel>
        </PanelBoundary>
      ) : null}

      {/* Axes disagree */}
      {person.axes_disagree && disagreeHeadline ? (
        <AxesDisagreeHeadline headline={disagreeHeadline} axes={axes} />
      ) : null}

      {/* The detail behind the disagreement, when the author supplied it. */}
      {person.axes_disagree && person.axes_disagree_detail ? (
        <p className="px-1 text-[12.5px] leading-relaxed text-zinc-400">
          {person.axes_disagree_detail}
        </p>
      ) : null}

      {/* Three axes */}
      <PanelBoundary label="axes">
        <Panel
          eyebrow="Screening · founder / market / idea-vs-market"
          title="Three axes, never averaged"
          plain="Founder, Market and Idea-vs-Market are scored separately and stay separate. Market is a category, not a number, so there is nothing here that could be averaged even if we wanted to."
        >
          {axes.length ? (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              {axes.map(({ key, axis }) => (
                <AxisCard
                  key={key}
                  axisKey={key}
                  axis={axis}
                  threshold={convictionThreshold}
                />
              ))}
            </div>
          ) : (
            <EmptyState text="No axis scores for this person at this asof." />
          )}
        </Panel>
      </PanelBoundary>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Cold-Start Bench */}
        <PanelBoundary label="cold-start bench">
          <Panel
            eyebrow="No GitHub · no funding · no network"
            title="Cold-Start Bench"
            plain="This founder has no track record to score. So we say what we are actually scoring on, how much of the estimate is a prior rather than evidence, and exactly what would narrow the range."
          >
            <ColdStartBench bench={bench} blockedReason={benchBlocked} />
          </Panel>
        </PanelBoundary>

        {/* Score history */}
        <PanelBoundary label="founder score history">
          <Panel
            title={
              // Count the ventures actually plotted. The heading used to assert
              // "two ventures" for everyone, which was false on any founder with
              // a single one — a caption contradicting its own chart, on the page
              // the whole cold-start argument rests on.
              (() => {
                const names = Array.from(
                  new Set(
                    (Array.isArray(history) ? history : [])
                      .map((h: Json) => h?.org_name ?? h?.venture)
                      .filter(Boolean)
                      .map(String)
                  )
                );
                if (names.length > 1)
                  return `Founder Score — full history, ${names.length} ventures`;
                if (names.length === 1)
                  return `Founder Score — full history, one venture so far`;
                return "Founder Score — full history";
              })()
            }
            plain="The score belongs to the person, not the company. It is stored as append-only versions, so when the venture changes the line carries over instead of resetting. There is no code path that could reset it."
          >
            {history ? (
              <ScoreHistoryChart history={history} />
            ) : (
              <EmptyState text="No founder score history at this asof." />
            )}
          </Panel>
        </PanelBoundary>
      </div>

      {/* Manifest — the differentiator. Absence is catalogued here as
          carefully as presence, which is the whole argument of the product. */}
      <PanelBoundary label="manifest">
        <Panel
          eyebrow="The finding aid"
          title="Expected-evidence manifest"
          plain="We asked what artifacts should exist if this founder's claims were true, then went looking. This is the full list — what we found, what was missing, and what the missing things cost. Absences someone with this profile would plausibly not have cost nothing at all."
          right={<LacunaKey className="max-w-[30rem]" />}
        >
          <ManifestChecklist manifest={manifest} />
        </Panel>
      </PanelBoundary>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Founder–market fit */}
        {fmf ? (
          <PanelBoundary label="founder-market fit">
            <Panel
              title="Founder–market fit"
              plain="The brief asks for a soft-skill assessment that carries a prediction interval. This one is scored off lived-domain-exposure atoms in written answers, so it can be pointed at its evidence rather than asserted."
            >
              <FounderMarketFit fmf={fmf} />
            </Panel>
          </PanelBoundary>
        ) : null}

        {/* Entity resolution */}
        {entityRes ? (
          <PanelBoundary label="entity resolution">
            <Panel
              title="Two ventures, one person"
              plain="How we established that these are the same human across two companies — and what we deliberately refused to match on."
            >
              <EntityResolution er={entityRes} />
            </Panel>
          </PanelBoundary>
        ) : null}
      </div>

      {/* Milestones */}
      {milestones ? (
        <PanelBoundary label="milestones">
          <Panel
            title="Milestones"
            plain="Milestones are not a separate table. They are observations in the one append-only ledger, flagged as milestones, so they stay on the same clock as everything else."
          >
            <Milestones
              milestones={milestones}
              note={pick(person, "milestones_note")}
            />
          </Panel>
        </PanelBoundary>
      ) : null}

      {/* Anything else the integrator shipped that we did not model */}
      {isObj(person) ? (
        <details className="rounded-md border border-zinc-800 bg-zinc-950/70">
          <summary className="cursor-pointer px-4 py-2.5 text-[12px] text-zinc-400 hover:text-zinc-200">
            All other fields on this person record
          </summary>
          <div className="border-t border-zinc-800 p-4">
            <KVTable
              obj={person}
              exclude={[
                "axes",
                "axis_scores",
                "scores",
                "cold_start_bench",
                "coldstart_bench",
                "bench",
                "expected_evidence_manifest",
                "evidence_manifest",
                "manifest",
                "founder_score_history",
                "score_history",
                "founder_score_versions",
                "founder_score",
                "score_definition_strip",
                "founder_market_fit",
                "entity_resolution",
                "milestones",
                "milestones_note",
                "cold_start_bench_blocked_reason",
                "axes_disagree_detail",
              ]}
            />
          </div>
        </details>
      ) : null}
    </div>
  );
}
