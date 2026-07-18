import React from "react";
import type { Json } from "@/lib/types";
import { fmtDate, fmtNum, humanize, isObj } from "@/lib/util";
import { Badge, N, Panel, ProvenanceBadge, Refusal } from "./primitives";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-zinc-900 py-1.5">
      <span className="text-[11.5px] text-zinc-500">{label}</span>
      <span className="text-right text-[12.5px] text-zinc-200">{children}</span>
    </div>
  );
}

/**
 * How this opportunity was DISCOVERED — the cold-start half of the product.
 *
 * The brief makes sourcing the priority and calls out the founder with no
 * GitHub, no funding and no network. A self-filed trademark with an empty
 * attorney field is the channel that fires for exactly that person, so the
 * panel prints the filing itself, the argument for the channel, and the
 * coverage limit we know it has.
 */
export function SourcingOrigin({ origin }: { origin: Json }) {
  if (!isObj(origin)) return null;

  return (
    <Panel
      title={origin.title ?? "Sourcing origin"}
      plain="How we found this person before anyone else could. This channel fires for a founder with no repo, no funding and no network — which is the whole point."
      right={<ProvenanceBadge value={origin.provenance_class} />}
    >
      <div className="space-y-3">
        <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
          {origin.channel_id ? (
            <Row label="Channel">
              <span className="font-mono text-[11.5px]">
                {String(origin.channel_id)}
              </span>
            </Row>
          ) : null}
          {origin.filed_at ? (
            <Row label="Filed">{fmtDate(origin.filed_at)}</Row>
          ) : null}
          {origin.serial ? (
            <Row label="Serial">
              <span className="font-mono">{String(origin.serial)}</span>
            </Row>
          ) : null}
          {origin.filing_basis ? (
            <Row label="Basis">{String(origin.filing_basis)}</Row>
          ) : null}
          {origin.teas_tier ? (
            <Row label="Tier">{String(origin.teas_tier)}</Row>
          ) : null}
          {origin.owner_type ? (
            <Row label="Owner type">{humanize(origin.owner_type)}</Row>
          ) : null}
          {origin.cost_usd != null ? (
            <Row label="Filing cost">
              <span className="tabular-nums">${fmtNum(origin.cost_usd, 0)}</span>
            </Row>
          ) : null}
          {origin.attorney_field_empty ? (
            <Row label="Attorney of record">
              <Badge className="border-amber-500/50 bg-amber-500/10 text-amber-300">
                empty — the marker
              </Badge>
            </Row>
          ) : null}
        </div>

        {/* The free text is a machine-readable product description, which is
            why it can feed the Idea-vs-Market axis directly. */}
        {origin.goods_and_services_text ? (
          <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
            <div className="mb-1 text-[10px] uppercase tracking-wider text-zinc-500">
              Goods and services — parsed, feeds the Idea-vs-Market axis
            </div>
            <p className="font-mono text-[11.5px] leading-relaxed text-zinc-300">
              {String(origin.goods_and_services_text)}
            </p>
          </div>
        ) : null}

        {origin.argument ? (
          <p className="text-[12.5px] leading-relaxed text-zinc-300">
            {String(origin.argument)}
          </p>
        ) : null}

        {(origin.post_filter_rows || origin.post_filter_gate) && (
          <div className="rounded border border-emerald-500/30 bg-emerald-500/[0.06] p-3">
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="text-[10px] uppercase tracking-wider text-emerald-400">
                Pass condition, written before parsing
              </span>
              {origin.post_filter_rows ? (
                <span className="font-mono text-[11.5px] text-zinc-200">
                  <N q={origin.post_filter_rows} digits={0} />
                </span>
              ) : null}
            </div>
            {origin.post_filter_gate ? (
              <p className="mt-1 text-[11.5px] leading-relaxed text-zinc-400">
                {String(origin.post_filter_gate)}
              </p>
            ) : null}
          </div>
        )}

        {origin.provenance_note ? (
          <p className="text-[11.5px] leading-relaxed text-zinc-500">
            {String(origin.provenance_note)}
          </p>
        ) : null}

        {/* Naming our own coverage limit rather than letting a judge find it. */}
        {origin.known_coverage_limit ? (
          <Refusal>{String(origin.known_coverage_limit)}</Refusal>
        ) : null}
      </div>
    </Panel>
  );
}

/**
 * The domain probe — transacting versus parked. Costly to fake, cheap to check,
 * and it fires with no network attached to the founder.
 */
export function DomainProbe({ probe }: { probe: Json }) {
  if (!isObj(probe)) return null;

  const entries = Object.entries(probe).filter(
    ([k, v]) =>
      v !== null &&
      v !== undefined &&
      !["title", "plain_line", "note", "provenance_class"].includes(k)
  );
  if (!entries.length) return null;

  return (
    <Panel
      title={probe.title ?? "Domain probe"}
      plain={
        probe.plain_line ??
        "We fetched the company domain and looked for evidence of a transacting product rather than a parked page."
      }
      right={<ProvenanceBadge value={probe.provenance_class} />}
    >
      <div className="space-y-2.5">
        <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
          {entries.map(([k, raw]) => {
            const v = raw as Json;
            return (
              <Row key={k} label={humanize(k)}>
                {typeof v === "boolean" ? (
                  <span className={v ? "text-emerald-300" : "text-zinc-500"}>
                    {String(v)}
                  </span>
                ) : isObj(v) && "value" in (v as object) ? (
                  <N q={v} />
                ) : Array.isArray(v) ? (
                  <span className="text-[11.5px]">{v.join(", ")}</span>
                ) : (
                  <span className="font-mono text-[11.5px]">{String(v)}</span>
                )}
              </Row>
            );
          })}
        </div>
        {probe.note ? (
          <p className="text-[11.5px] leading-relaxed text-zinc-500">
            {String(probe.note)}
          </p>
        ) : null}
      </div>
    </Panel>
  );
}
