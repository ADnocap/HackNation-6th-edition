"use client";

import React from "react";

/**
 * Per-panel error boundary.
 *
 * This lives in its own client module deliberately. React class components do
 * not exist in the React Server Components bundle (`React.Component` is
 * literally undefined under the `react-server` condition), so an error boundary
 * defined alongside server components fails the build rather than the request.
 *
 * It also deliberately does NOT import from ./primitives: primitives re-exports
 * this component, and the resulting import cycle initializes to undefined at
 * module load. The small amount of duplicated markup below is the price of not
 * having a cycle in the one component whose job is to survive failure.
 */
export class PanelBoundary extends React.Component<
  { children: React.ReactNode; label?: string },
  { failed: boolean; msg: string }
> {
  constructor(props: { children: React.ReactNode; label?: string }) {
    super(props);
    this.state = { failed: false, msg: "" };
  }

  static getDerivedStateFromError(e: unknown) {
    return { failed: true, msg: e instanceof Error ? e.message : String(e) };
  }

  render() {
    if (this.state.failed) {
      const detail = `${this.props.label ? this.props.label + ": " : ""}${
        this.state.msg
      }`;
      return (
        <div className="rounded border border-rose-500/40 bg-rose-500/5 px-4 py-3">
          <p className="text-[13px] text-rose-300">
            This panel could not render. The rest of the page is unaffected.
          </p>
          <p className="mt-1 font-mono text-[11px] text-rose-400/70">{detail}</p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default PanelBoundary;
