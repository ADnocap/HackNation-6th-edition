import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Badge,
  EmptyState,
  KVTable,
  N,
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

  const contactStatus = pick(person, "contact_status");
  const channels = arr(pick(person, "channels", "discovery_channels"));

  // Opportunities this person appears in — the two-venture spine.
  const linked = getOpportunities(demo).filter((o) => o?.person_id === id);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-md border border-zinc-800 bg-zinc-950/70 px-4 py-3.5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-[18px] font-semibold tracking-tight text-zinc-50">
                {person.display_name ??
                  person.person_display_name ??
                  person.name ??
                  id}
              </h1>
              <Badge className="border-zinc-700 bg-zinc-900 font-mono text-zinc-400">
                {id}
              </Badge>
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
            <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-zinc-500">
              {contactStatus ? (
                <span title="Discovered is not the same as reachable. We print the difference.">
                  contact: {humanize(contactStatus)}
                </span>
              ) : null}
              {channels.length ? (
                <span>
                  channels:{" "}
                  {channels
                    .map((c: Json) => (typeof c === "string" ? c : c?.channel_id))
                    .filter(Boolean)
                    .join(", ")}
                </span>
              ) : null}
              {person.first_observed_at ? (
                <span className="font-mono">
                  first observed {fmtTs(person.first_observed_at)}
                </span>
              ) : null}
            </div>
          </div>

          {linked.length ? (
            <div className="flex flex-wrap gap-1.5">
              {linked.map((o: Json) => (
                <Link
                  key={o.opportunity_id}
                  href={`/opportunity/${o.opportunity_id}`}
                  className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-[11.5px] text-zinc-300 transition-colors hover:border-zinc-600 hover:text-white"
                >
                  {o.org_name ?? o.opportunity_id} →
                </Link>
              ))}
            </div>
          ) : null}
        </div>
      </div>

      {/* Axes disagree */}
      {person.axes_disagree && disagreeHeadline ? (
        <AxesDisagreeHeadline headline={disagreeHeadline} axes={axes} />
      ) : null}

      {/* Three axes */}
      <PanelBoundary label="axes">
        <Panel
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
            title="Cold-Start Bench"
            plain="This founder has no track record to score. So we say what we are actually scoring on, how much of the estimate is a prior rather than evidence, and exactly what would narrow the range."
          >
            <ColdStartBench bench={bench} />
          </Panel>
        </PanelBoundary>

        {/* Score history */}
        <PanelBoundary label="founder score history">
          <Panel
            title="Founder Score — full history, two ventures"
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

      {/* Manifest */}
      <PanelBoundary label="manifest">
        <Panel
          title="Expected-evidence manifest"
          plain="What we went looking for, what we found, and what was missing. Missing things that someone with this profile would plausibly not have are greyed out and cost nothing."
        >
          <ManifestChecklist manifest={manifest} />
        </Panel>
      </PanelBoundary>

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
              ]}
            />
          </div>
        </details>
      ) : null}
    </div>
  );
}
