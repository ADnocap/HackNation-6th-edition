import {
  BearCase,
  DecisionCard,
  GapsBlock,
  MemoBody,
  PortfolioConflictCheck,
} from "@/components/memo";
import { OpportunityHeader } from "@/components/opportunity";
import { EmptyState, Panel, PanelBoundary, Refusal } from "@/components/primitives";
import { getOpportunity, loadDemo } from "@/lib/data";
import { isObj } from "@/lib/util";

export const dynamic = "force-dynamic";

export default async function MemoPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { demo, ok, error } = loadDemo();

  if (!ok) {
    return (
      <Panel title="Memo" plain="The renderer has no ledger to read.">
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
      <Panel title={`Memo ${id}`} plain="No such opportunity at this asof.">
        <EmptyState
          text="No data at this asof. Move the point-in-time control forward."
          detail={`No entry for "${id}" in the opportunities collection.`}
        />
      </Panel>
    );
  }

  const memo = opp.memo;
  const hasMemo = isObj(memo);

  return (
    <div>
      <OpportunityHeader opp={opp} active="memo" />

      <div className="space-y-4">
        {/*
          A blocked memo renders its reason. It never renders a placeholder
          memo — ui_rules.refusal_render_rule, applied to the largest object
          on the page.
        */}
        {!hasMemo ? (
          <Panel
            title="Investment memo"
            plain="There is no memo for this opportunity, and we will not render a placeholder one."
          >
            <Refusal>
              {opp.memo_blocked_reason ??
                "Not yet at decision stage. The memo route renders the empty state, not a placeholder memo."}
            </Refusal>
          </Panel>
        ) : (
          <>
            <PanelBoundary label="memo body">
              <MemoBody memo={memo} oppId={opp.opportunity_id} />
            </PanelBoundary>

            <PanelBoundary label="gaps block">
              <GapsBlock gaps={memo.gaps_block} oppId={opp.opportunity_id} />
            </PanelBoundary>

            <PanelBoundary label="bear case">
              <BearCase bear={memo.bear_case} oppId={opp.opportunity_id} />
            </PanelBoundary>

            {memo.portfolio_conflict_check ? (
              <PanelBoundary label="portfolio conflict">
                <PortfolioConflictCheck check={memo.portfolio_conflict_check} />
              </PanelBoundary>
            ) : null}
          </>
        )}

        <PanelBoundary label="decision">
          <DecisionCard decision={opp.decision} />
        </PanelBoundary>
      </div>
    </div>
  );
}
