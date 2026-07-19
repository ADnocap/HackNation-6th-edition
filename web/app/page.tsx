import DiscoveryWorkspace from "@/components/DiscoveryWorkspace";
import { EmptyState, Panel } from "@/components/primitives";
import { at, getFunnel, getSignalRows, getThesis, loadDemo, pick } from "@/lib/data";
import type { Json } from "@/lib/types";


function getTrigger(demo: Json): Json {
  return at(demo, "signal_feed.trigger") ?? pick(demo, "trigger_banner", "trigger", "trigger_event") ?? null;
}

export default function Page() {
  const { demo, ok, error } = loadDemo();
  if (!ok) {
    return <Panel title="Discovery unavailable" plain="The evidence ledger is not on disk yet."><EmptyState detail={error} /></Panel>;
  }
  const { rows, derived } = getSignalRows(demo);
  return (
    <DiscoveryWorkspace
      rows={rows}
      funnel={getFunnel(demo)}
      trigger={getTrigger(demo)}
      compoundQuery={pick(demo, "compound_query") ?? null}
      thesis={getThesis(demo)}
      derived={derived}
    />
  );
}
