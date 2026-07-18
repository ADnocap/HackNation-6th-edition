import SignalFeed from "@/components/SignalFeed";
import { EmptyState, Panel, PanelBoundary } from "@/components/primitives";
import {
  AsofSlices,
  CompoundQueryPanel,
  MemoryPanel,
  PortfolioPanel,
  ScreenPanel,
  ThesisPanel,
} from "@/components/context";
import {
  at,
  getAsofSlices,
  getFunnel,
  getSignalRows,
  getThesis,
  loadDemo,
  pick,
} from "@/lib/data";
import type { Json } from "@/lib/types";

export const dynamic = "force-dynamic";

function getTrigger(demo: Json): Json {
  return (
    at(demo, "signal_feed.trigger") ??
    at(demo, "signal_feed.trigger_banner") ??
    pick(demo, "trigger_banner", "trigger", "trigger_event") ??
    null
  );
}

export default function Page() {
  const { demo, ok, error } = loadDemo();
  const { rows, derived } = getSignalRows(demo);
  const funnel = getFunnel(demo);
  const trigger = getTrigger(demo);
  const neutralizationNote =
    at<string>(demo, "signal_feed.neutralization_note") ??
    at<string>(demo, "signal_feed.residual_note") ??
    null;

  const thesis = getThesis(demo);
  const memory = pick(demo, "memory") ?? null;
  const compoundQuery = pick(demo, "compound_query") ?? null;
  const screen = pick(demo, "screen") ?? null;
  const portfolio = pick(demo, "portfolio") ?? null;
  const asofSlices = getAsofSlices(demo);

  if (!ok) {
    return (
      <Panel
        title="Signal feed"
        plain="The renderer reads one committed file and nothing else. That file is not on disk yet."
      >
        <EmptyState
          text="Reading the ledger at asof… nothing found."
          detail={error}
        />
      </Panel>
    );
  }

  return (
    <div className="space-y-4">
      <PanelBoundary label="signal feed">
        <SignalFeed
          rows={rows}
          funnel={funnel}
          trigger={trigger}
          derived={derived}
          neutralizationNote={neutralizationNote}
          meta={pick(demo, "signal_feed") ?? null}
        />
      </PanelBoundary>

      {/* The point-in-time control. Same code path at every asof. */}
      {asofSlices && Object.keys(asofSlices).length ? (
        <PanelBoundary label="asof slices">
          <Panel
            title="Point in time"
            plain="Every read filters on observed_at ≤ asof. Set asof to now and this is a live VC brain; set it to a past date and the identical code is a backtest. Nothing re-runs and nothing is recomputed by hand."
          >
            <AsofSlices slices={asofSlices} />
          </Panel>
        </PanelBoundary>
      ) : null}

      {/* Compound query — one pass, and the refusals are printed. */}
      {compoundQuery ? (
        <PanelBoundary label="compound query">
          <Panel
            title={
              (compoundQuery as Json)?.title ?? "Compound query — resolved in one pass"
            }
            plain={
              (compoundQuery as Json)?.plain_line ??
              "One natural-language query, parsed into filters against the ledger. Clauses we have no source for resolve to NO SOURCE rather than being quietly dropped."
            }
          >
            <CompoundQueryPanel cq={compoundQuery} />
          </Panel>
        </PanelBoundary>
      ) : null}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Thesis Engine — configurable, per the brief. */}
        <PanelBoundary label="thesis">
          <Panel
            title="Thesis Engine"
            plain="Configurable, not hardcoded to one fund. These are persisted fields; changing any of them re-ranks the board and can move an opportunity across the decision gate."
          >
            <ThesisPanel thesis={thesis} />
          </Panel>
        </PanelBoundary>

        {/* Memory — one append-only ledger. */}
        {memory ? (
          <PanelBoundary label="memory">
            <Panel
              title={(memory as Json)?.title ?? "Memory"}
              plain={
                (memory as Json)?.plain_line ??
                "Nothing in here is ever updated or deleted. Every score is a pure function of the rows."
              }
            >
              <MemoryPanel memory={memory} />
            </Panel>
          </PanelBoundary>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Screen — reversible by construction. */}
        {screen ? (
          <PanelBoundary label="screen">
            <Panel
              title={(screen as Json)?.title ?? "Screen"}
              plain={
                (screen as Json)?.plain_line ??
                "We remove clearly non-viable submissions with a stated reason. The row stays in the ledger."
              }
            >
              <ScreenPanel screen={screen} />
            </Panel>
          </PanelBoundary>
        ) : null}

        {/* Portfolio conflict check — part of the decision, not monitoring. */}
        {portfolio ? (
          <PanelBoundary label="portfolio">
            <Panel
              title={(portfolio as Json)?.title ?? "Portfolio conflict check"}
              plain={
                (portfolio as Json)?.plain_line ??
                "Before a decision we check the existing book for a conflicting position."
              }
            >
              <PortfolioPanel portfolio={portfolio} />
            </Panel>
          </PanelBoundary>
        ) : null}
      </div>
    </div>
  );
}
