import {
  ChannelOutcomes,
  ConstraintsOnScreen,
  CouldNotValidate,
  DaysOfEdge,
  LatencyTable,
  NotCollected,
  RecognitionProbe,
  ReliabilityTable,
  ResearchDesign,
} from "@/components/honesty";
import {
  EmptyState,
  PageHead,
  Panel,
  PanelBoundary,
} from "@/components/primitives";
import { getHonesty, loadDemo } from "@/lib/data";

export const dynamic = "force-dynamic";

export default function HonestyPage() {
  const { demo, ok, error } = loadDemo();

  if (!ok) {
    return (
      <Panel title="Honesty" plain="The renderer has no ledger to read.">
        <EmptyState
          text="Reading the ledger at asof… nothing found."
          detail={error}
        />
      </Panel>
    );
  }

  const h = getHonesty(demo);
  const empty = !h || Object.keys(h).length === 0;

  return (
    <div className="space-y-4">
      <PageHead
        eyebrow="Limitations · stated by us, about us"
        title="Methods & limits"
        lede={
          h?.plain_line ??
          "How Counterproof searches, what it refuses to collect, how reliable each source is, and where the current evidence is too thin to support a conclusion."
        }
      />

      {empty ? (
        <Panel
          title="Honesty"
          plain="This page is the one part of the product that cannot be faked, so it renders nothing rather than something."
        >
          <EmptyState text="No honesty block at this asof." />
        </Panel>
      ) : (
        <>
          <PanelBoundary label="days of edge">
            <DaysOfEdge block={h.days_of_edge} />
          </PanelBoundary>

          <PanelBoundary label="reliability table">
            <ReliabilityTable block={h.reliability_table} />
          </PanelBoundary>

          <details className="route-disclosure" open>
            <summary><span><strong>Coverage and deliberate exclusions</strong><small>Channel outcomes, blind spots and data we chose not to collect</small></span></summary>
            <div className="disclosure-body space-y-4">
              <PanelBoundary label="channel outcomes"><ChannelOutcomes block={h.channel_outcomes} /></PanelBoundary>
              <PanelBoundary label="not collected"><NotCollected block={h.not_collected} /></PanelBoundary>
              <PanelBoundary label="recognition probe"><RecognitionProbe block={h.recognition_probe} /></PanelBoundary>
            </div>
          </details>

          <details className="route-disclosure">
            <summary><span><strong>Validation design and system performance</strong><small>Research protocol, latency and visible constraints</small></span></summary>
            <div className="disclosure-body space-y-4">
              <PanelBoundary label="research design"><ResearchDesign block={h.research_area_3_design} /></PanelBoundary>
              <PanelBoundary label="latency"><LatencyTable block={h.latency} /></PanelBoundary>
              <PanelBoundary label="constraints"><ConstraintsOnScreen items={h.constraints_on_screen} /></PanelBoundary>
            </div>
          </details>

          <PanelBoundary label="could not validate"><CouldNotValidate block={h.what_we_could_not_validate} /></PanelBoundary>
        </>
      )}

      <p className="t-display max-w-[52ch] border-t border-zinc-800 pt-4 pb-6 text-[16px] leading-[1.5] text-zinc-200">
        {h?.closing_line ??
          "Here is what we could not validate in twenty-one hours, and here is the experiment that would."}
      </p>
    </div>
  );
}
