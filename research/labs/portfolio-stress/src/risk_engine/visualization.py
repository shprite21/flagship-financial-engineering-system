"""Five headless research figures using common scales across comparable scenarios."""

from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator, StrMethodFormatter

from .risk_metrics import RiskReport


COLORS = ("#235789", "#c36a24", "#24816f", "#9b4866", "#7b69a4", "#545b62")


def _figure(title: str, context: str, size: tuple[float, float] = (8, 4.8)):
    fig = Figure(figsize=size, layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.set_title(f"{title}\n{context}", loc="left", pad=12, fontsize=13)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#d6dde3", linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax


def save_figures(
    directory: Path,
    reports: dict[str, RiskReport],
    baseline_paths: np.ndarray,
    label: str,
    currency: str,
) -> None:
    """Render baseline paths and values, scenario loss tails, risk estimates and drawdowns."""
    directory.mkdir(parents=True, exist_ok=True)
    initial = baseline_paths[0, 0]
    days = np.arange(baseline_paths.shape[1])
    context = f"{label}  |  {len(days) - 1} trading days"
    baseline = reports["Baseline"]
    with mpl.rc_context({"font.size": 9, "axes.labelsize": 10, "legend.frameon": False}):
        fig, ax = _figure("Portfolio wealth under the baseline model", context)
        q05, q50, q95 = np.quantile(baseline_paths, [0.05, 0.5, 0.95], axis=0)
        ax.fill_between(days, q05, q95, color="#c4dbe9", alpha=0.75, label="5th–95th percentile")
        n_display = min(35, len(baseline_paths))
        lines = ax.plot(days, baseline_paths[:n_display].T, color=COLORS[0], alpha=0.22, lw=0.65)
        lines[0].set_label(f"{n_display} individual paths")
        ax.plot(days, q50, color="#132f49", lw=2, label="Median")
        ax.yaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.set(xlabel="Trading day", ylabel=f"Portfolio value ({currency})", xlim=(0, days[-1]))
        ax.legend(loc="upper left")
        fig.savefig(directory / "equity_paths.png", dpi=180)

        fig, ax = _figure("Terminal portfolio value under the baseline model", context)
        ax.hist(baseline.terminal_values, bins=50, color=COLORS[0])
        ax.axvline(initial, color="#242c34", ls="--", lw=1.4, label="Initial capital")
        ax.set(xlabel=f"Terminal value ({currency})", ylabel="Paths per bin")
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.xaxis.set_major_locator(MaxNLocator(6))
        ax.legend()
        fig.savefig(directory / "terminal_value.png", dpi=180)

        outcomes = {
            "terminal_losses": ("Distribution of terminal losses", "Loss (% of initial capital)",
                                [100 * (initial - r.terminal_values) / initial for r in reports.values()]),
            "maximum_drawdowns": ("Distribution of maximum drawdowns", "Peak-to-trough decline (%)",
                                  [100 * r.max_drawdowns for r in reports.values()]),
        }
        for filename, (title, xlabel, series) in outcomes.items():
            fig, ax = _figure(title, context)
            bins = np.histogram_bin_edges(np.concatenate(series), bins=50)
            for i, (name, sample) in enumerate(zip(reports, series)):
                counts, _ = np.histogram(sample, bins=bins)
                ax.stairs(100 * counts / len(sample), bins, label=name, lw=1.7, color=COLORS[i % len(COLORS)])
            ax.set(xlabel=xlabel, ylabel="Share of paths per bin (%)")
            ax.legend()
            fig.savefig(directory / f"{filename}.png", dpi=180)

        levels = [row["confidence"] for row in baseline.tails]
        height = max(3, 1.4 + len(levels) * (1.0 + 0.3 * len(reports)))
        fig = Figure(figsize=(8.5, height), layout="constrained")
        FigureCanvasAgg(fig)
        fig.suptitle(f"Terminal tail risk by scenario\n{context}", x=0.01, ha="left", fontsize=13)
        positions = np.arange(len(reports))
        for k, (level, ax) in enumerate(zip(levels, fig.subplots(len(levels), 1, sharex=True, squeeze=False)[:, 0])):
            for offset, key, color, name in [
                (-0.18, "var_pct", COLORS[0], "VaR"), (0.18, "es_pct", COLORS[1], "Expected shortfall")
            ]:
                ax.barh(positions + offset, [r.tails[k][key] for r in reports.values()],
                        height=0.32, color=color, label=name)
            ax.set_yticks(positions, list(reports))
            ax.invert_yaxis()
            ax.set_title(f"{100 * level:g}% confidence", loc="left", fontsize=10)
            ax.spines[["top", "right"]].set_visible(False)
            ax.axvline(0, color="#545b62", lw=0.6)
            if k == 0:
                ax.legend(loc="lower right", bbox_to_anchor=(1, 1), ncols=2)
            if k == len(levels) - 1:
                ax.set_xlabel("Terminal loss (% of initial capital)")
        fig.savefig(directory / "tail_risk.png", dpi=180)
