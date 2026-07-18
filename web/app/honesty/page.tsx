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
import { EmptyState, Panel, PanelBoundary } from "@/components/primitives";
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
      <header className="rounded-md border border-zinc-800 bg-zinc-950/70 px-4 py-3">
        <h1 className="text-[16px] font-semibold tracking-tight text-zinc-50">
          Honesty
        </h1>
        <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-zinc-300">
          {h?.plain_line ??
            "Everything on this page is a limitation we found in our own system and chose to show you."}
        </p>
      </header>

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

          <PanelBoundary label="channel outcomes">
            <ChannelOutcomes block={h.channel_outcomes} />
          </PanelBoundary>

          <PanelBoundary label="not collected">
            <NotCollected block={h.not_collected} />
          </PanelBoundary>

          <PanelBoundary label="recognition probe">
            <RecognitionProbe block={h.recognition_probe} />
          </PanelBoundary>

          <PanelBoundary label="reliability table">
            <ReliabilityTable block={h.reliability_table} />
          </PanelBoundary>

          <PanelBoundary label="research design">
            <ResearchDesign block={h.research_area_3_design} />
          </PanelBoundary>

          <PanelBoundary label="latency">
            <LatencyTable block={h.latency} />
          </PanelBoundary>

          <PanelBoundary label="constraints">
            <ConstraintsOnScreen items={h.constraints_on_screen} />
          </PanelBoundary>

          <PanelBoundary label="could not validate">
            <CouldNotValidate block={h.what_we_could_not_validate} />
          </PanelBoundary>
        </>
      )}

      <p className="px-1 pb-6 text-[13px] leading-relaxed text-zinc-400">
        {h?.closing_line ??
          "Here is what we could not validate in twenty-one hours, and here is the experiment that would."}
      </p>
    </div>
  );
}
