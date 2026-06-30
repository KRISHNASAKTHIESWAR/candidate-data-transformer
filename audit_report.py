"""
audit_report.py

CLI tool that runs the pipeline and immediately renders a rich, human-readable
audit report explaining every decision the engine made — especially for the
edge cases baked into the sample data.

Usage
-----
    python audit_report.py                          # uses output.json
    python audit_report.py --output path/to/out.json
    python audit_report.py --filter noah            # name/email substring
    python audit_report.py --band LOW               # HIGH | MEDIUM | LOW
    python audit_report.py --flags-only             # only show flagged records
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from core.reasoner import generate_reasoning

console = Console()

# ── Colour helpers ─────────────────────────────────────────────────────────

BAND_COLOUR = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}


def _band_badge(band: str) -> str:
    c = BAND_COLOUR.get(band, "white")
    return f"[bold {c}]{band}[/bold {c}]"


# ── Summary table ──────────────────────────────────────────────────────────

def render_summary_table(candidates: list[dict], reasoning: list[dict]) -> None:
    table = Table(
        title="Pipeline Audit — Candidate Summary",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold cyan",
    )
    table.add_column("#",          style="dim",   width=4)
    table.add_column("Name",                      width=22)
    table.add_column("Email",                     width=28)
    table.add_column("Confidence", justify="center", width=12)
    table.add_column("Sources",   justify="center", width=9)
    table.add_column("Flags",     justify="center", width=7)
    table.add_column("Multi-src fields",           width=24)

    for i, (cand, r) in enumerate(zip(candidates, reasoning), 1):
        name  = (cand.get("name") or "(unknown)")[:22]
        email = (cand.get("primary_email") or "(none)")[:28]
        conf  = cand.get("overall_confidence", 0.0)
        band  = r["confidence_band"]

        provenance = cand.get("provenance") or []
        src_count  = len({p["source"] for p in provenance})

        flag_cell  = "[red]YES[/red]" if r["flags"] else "[dim]--[/dim]"
        multi_str  = ", ".join(r["multi_source"].keys()) or "[dim]none[/dim]"

        table.add_row(
            str(i),
            name,
            email,
            f"{_band_badge(band)} {conf:.2f}",
            str(src_count),
            flag_cell,
            multi_str,
        )

    console.print(table)


# ── Detail panel per candidate ─────────────────────────────────────────────

def render_candidate_detail(idx: int, cand: dict, r: dict) -> None:
    name  = cand.get("name") or "(unknown)"
    email = cand.get("primary_email") or "(no email)"
    band  = r["confidence_band"]
    colour = BAND_COLOUR.get(band, "white")

    title = Text()
    title.append(f"#{idx}  {name}", style="bold white")
    title.append(f"  <{email}>", style="dim")
    title.append(f"  [{band}]", style=f"bold {colour}")

    body_lines = []

    # Decisions
    if r["decisions"]:
        body_lines.append("[bold underline]Field Resolution Decisions[/bold underline]")
        for d in r["decisions"]:
            body_lines.append(f"  [cyan]+[/cyan] {d}")

    # Multi-source
    if r["multi_source"]:
        body_lines.append("\n[bold underline]Multi-Source Fields[/bold underline]")
        for field, srcs in r["multi_source"].items():
            body_lines.append(f"  [yellow]{field}[/yellow] <- [{', '.join(srcs)}]")

    # Missing fields
    if r["missing"]:
        body_lines.append("\n[bold underline]Missing Core Fields[/bold underline]")
        for m in r["missing"]:
            body_lines.append(f"  [red]![/red] '{m}' was not populated")

    # Flags / warnings
    if r["flags"]:
        body_lines.append("\n[bold underline]Flags & Warnings[/bold underline]")
        for f in r["flags"]:
            body_lines.append(f"  [red bold]FLAG[/red bold] {f}")

    body = "\n".join(body_lines) if body_lines else "[dim](no notable decisions recorded)[/dim]"
    console.print(Panel(body, title=title, border_style=colour, expand=False))


# ── Stats panel ────────────────────────────────────────────────────────────

def render_stats(candidates: list[dict], reasoning: list[dict]) -> None:
    total  = len(candidates)
    high   = sum(1 for r in reasoning if r["confidence_band"] == "HIGH")
    medium = sum(1 for r in reasoning if r["confidence_band"] == "MEDIUM")
    low    = sum(1 for r in reasoning if r["confidence_band"] == "LOW")
    flagged = sum(1 for r in reasoning if r["flags"])
    multi  = sum(1 for r in reasoning if r["multi_source"])

    console.print(Panel(
        f"[bold green]HIGH[/bold green]:   {high:>3} candidates\n"
        f"[bold yellow]MEDIUM[/bold yellow]: {medium:>3} candidates\n"
        f"[bold red]LOW[/bold red]:    {low:>3} candidates\n"
        f"\n"
        f"[yellow]Multi-source merges :[/yellow] {multi}\n"
        f"[red]Flagged records     :[/red] {flagged}\n"
        f"\n"
        f"[bold]Total processed     : {total}[/bold]",
        title="[bold cyan]Aggregate Statistics[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline audit & reasoning report")
    parser.add_argument("--output",     default="output.json",
                        help="Path to the pipeline output JSON (default: output.json)")
    parser.add_argument("--filter",     default="",
                        help="Show only candidates whose name/email contains this substring")
    parser.add_argument("--band",       default="",  choices=["HIGH", "MEDIUM", "LOW", ""],
                        help="Filter by confidence band")
    parser.add_argument("--flags-only", action="store_true",
                        help="Show only candidates that have flags/warnings")
    parser.add_argument("--summary-only", action="store_true",
                        help="Print only the summary table, skip detail panels")
    args = parser.parse_args()

    if not os.path.exists(args.output):
        console.print(f"[red]Output file not found: {args.output}[/red]")
        sys.exit(1)

    with open(args.output, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    all_reasoning = [generate_reasoning(c) for c in candidates]

    # Apply filters
    filtered = [
        (c, r) for c, r in zip(candidates, all_reasoning)
        if (not args.filter or
            args.filter.lower() in (c.get("name") or "").lower() or
            args.filter.lower() in (c.get("primary_email") or "").lower())
        and (not args.band or r["confidence_band"] == args.band)
        and (not args.flags_only or r["flags"])
    ]

    if not filtered:
        console.print("[yellow]No candidates matched the specified filters.[/yellow]")
        return

    f_candidates = [x[0] for x in filtered]
    f_reasoning  = [x[1] for x in filtered]

    console.rule("[bold blue]PIPELINE REASONING AUDIT[/bold blue]")
    render_stats(candidates, all_reasoning)       # always show global stats

    console.print()
    render_summary_table(f_candidates, f_reasoning)

    if not args.summary_only:
        console.print()
        console.rule("[bold blue]Candidate Detail[/bold blue]")
        for i, (cand, r) in enumerate(filtered, 1):
            render_candidate_detail(i, cand, r)
            console.print()


if __name__ == "__main__":
    main()
