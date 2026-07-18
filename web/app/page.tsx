import SignalFeed from "@/components/SignalFeed";
import { EmptyState, Panel, PanelBoundary } from "@/components/primitives";
import { at, getFunnel, getSignalRows, loadDemo, pick } from "@/lib/data";
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
    <PanelBoundary label="signal feed">
      <SignalFeed
        rows={rows}
        funnel={funnel}
        trigger={trigger}
        derived={derived}
        neutralizationNote={neutralizationNote}
      />
    </PanelBoundary>
  );
}
