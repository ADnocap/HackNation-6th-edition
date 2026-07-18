import ClaimList from "@/components/ClaimList";
import {
  OpportunityHeader,
  SlaStrip,
  SourceArtifact,
  StageTimeline,
} from "@/components/opportunity";
import { DomainProbe, SourcingOrigin } from "@/components/sourcing";
import {
  EmptyState,
  Panel,
  PanelBoundary,
} from "@/components/primitives";
import { getClaims, getOpportunity, loadDemo } from "@/lib/data";
import type { Json } from "@/lib/types";
import { arr } from "@/lib/util";

export const dynamic = "force-dynamic";

/**
 * Pick the claim whose receipt should be one click away when the page opens.
 * The demo wants the contradicted MRR claim; we prefer the most damaging
 * claim that actually has a receipt, rather than hardcoding an id that may
 * not survive a regeneration of demo.json.
 */
function heroClaimId(claims: Json[]): string | null {
  const withReceipt = arr(claims).filter(
    (c: Json) => c?.receipt && typeof c.receipt === "object"
  );
  if (!withReceipt.length) return null;
  const contradicted = withReceipt.find(
    (c: Json) => c?.state === "contradicted" && c?.is_material
  );
  const anyContradicted = withReceipt.find(
    (c: Json) => c?.state === "contradicted"
  );
  return (
    (contradicted ?? anyContradicted ?? withReceipt[0])?.claim_id ?? null
  );
}

export default async function OpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { demo, ok, error } = loadDemo();

  if (!ok) {
    return (
      <Panel title="Opportunity" plain="The renderer has no ledger to read.">
        <EmptyState
          text="Reading the ledger at asof… nothing found."
          detail={error}
        />
      </Panel>
    );
  }

  const opp = getOpportunity(demo, id);
  if (!opp) {
    return (
      <Panel
        title={`Opportunity ${id}`}
        plain="No such opportunity at this asof."
      >
        <EmptyState
          text="No data at this asof. Move the point-in-time control forward."
          detail={`No entry for "${id}" in the opportunities collection.`}
        />
      </Panel>
    );
  }

  const claims = getClaims(opp);
  const distribution =
    opp.claim_distribution ??
    // Derive rather than fabricate: count the states we actually have.
    (claims.length
      ? claims.reduce(
          (acc: Record<string, number>, c: Json) => {
            const s = String(c?.state ?? "");
            if (s) acc[s] = (acc[s] ?? 0) + 1;
            acc.n = claims.length;
            return acc;
          },
          {} as Record<string, number>
        )
      : null);

  return (
    <div>
      <OpportunityHeader opp={opp} active="claims" />

      <div className="space-y-4">
        <PanelBoundary label="sla">
          <SlaStrip sla={opp.sla} />
        </PanelBoundary>

        {/* How this person was discovered. Sourcing is the priority in the
            brief, and the cold-start channel is the part worth showing. */}
        {opp.sourcing_origin ? (
          <PanelBoundary label="sourcing origin">
            <SourcingOrigin origin={opp.sourcing_origin} />
          </PanelBoundary>
        ) : null}

        {opp.domain_probe ? (
          <PanelBoundary label="domain probe">
            <DomainProbe probe={opp.domain_probe} />
          </PanelBoundary>
        ) : null}

        <PanelBoundary label="claims">
          {claims.length ? (
            <ClaimList
              claims={claims}
              distribution={distribution}
              note={opp.claims_note}
              openClaimId={heroClaimId(claims)}
            />
          ) : (
            <Panel
              title="Claims"
              plain="Trust is per claim, not per company. There are no claims on this opportunity yet."
            >
              <EmptyState text="No claims at this asof. Move the point-in-time control forward." />
            </Panel>
          )}
        </PanelBoundary>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <PanelBoundary label="source artifact">
            <SourceArtifact opp={opp} />
          </PanelBoundary>
          <PanelBoundary label="stage timeline">
            <StageTimeline timeline={opp.stage_timeline} />
          </PanelBoundary>
        </div>
      </div>
    </div>
  );
}
