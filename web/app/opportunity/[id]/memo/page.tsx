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
import { arr, humanize, isObj } from "@/lib/util";

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
  const decision = opp.decision ?? {};
  const conditions = arr(decision.conditions_to_close);

  return (
    <div>
      <OpportunityHeader opp={opp} active="memo" />

      <div className="space-y-4">
        <section className="decision-simple">
          <div className="decision-verdict">
            <span className="section-kicker">Recommendation</span>
            <h2>{decision.verdict_label ?? humanize(decision.verdict ?? "not decided")}</h2>
            <p>{decision.gate_sentence ?? "The record has not reached a final decision yet."}</p>
          </div>
          <div><span>Binding concern</span><strong>{humanize(decision.binding_axis ?? "not set")}</strong><small>{decision.binding_axis_reason ?? "No binding reason recorded."}</small></div>
          <div><span>What happens next</span><strong>{decision.next_action?.text ?? "Continue evidence review"}</strong><small>{decision.next_action?.owner ? `Owner: ${decision.next_action.owner}` : "No owner assigned"}</small></div>
          <div><span>Conditions</span><strong>{conditions.length}</strong><small>{conditions.length ? "must be resolved before closing" : "none currently required"}</small></div>
        </section>

        <details className="route-disclosure">
          <summary><span><strong>Full decision mechanics</strong><small>Intervals, axes, gate arithmetic and conditions</small></span></summary>
          <div className="disclosure-body"><PanelBoundary label="decision"><DecisionCard decision={decision} /></PanelBoundary></div>
        </details>

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
            <details className="route-disclosure">
              <summary><span><strong>Read the investment memo</strong><small>Company, hypotheses, product, traction and SWOT</small></span></summary>
              <div className="disclosure-body"><PanelBoundary label="memo body"><MemoBody memo={memo} oppId={opp.opportunity_id} /></PanelBoundary></div>
            </details>

            <details className="route-disclosure">
              <summary><span><strong>Risks, gaps and conflicts</strong><small>What could change the recommendation</small></span></summary>
              <div className="disclosure-body space-y-4">
                <PanelBoundary label="gaps block"><GapsBlock gaps={memo.gaps_block} oppId={opp.opportunity_id} /></PanelBoundary>
                <PanelBoundary label="bear case"><BearCase bear={memo.bear_case} oppId={opp.opportunity_id} /></PanelBoundary>
                {memo.portfolio_conflict_check ? <PanelBoundary label="portfolio conflict"><PortfolioConflictCheck check={memo.portfolio_conflict_check} /></PanelBoundary> : null}
              </div>
            </details>
          </>
        )}
      </div>
    </div>
  );
}
