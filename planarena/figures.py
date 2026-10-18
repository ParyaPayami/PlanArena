"""Figures for the paper, drawn only from result files (like planarena/report.py for numbers).

Run:  python -I -m planarena.figures        -> docs/figures/*.png and *.svg
"""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from planarena.config import ROOT  # noqa: E402

RES = ROOT / "results" / "validation"
OUT = ROOT / "docs" / "figures"
INK, MUTED, A, B, C, D = "#1f2933", "#7b8794", "#2f6fb0", "#d9822b", "#3f8f5a", "#a33b3b"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK, "figure.dpi": 150})


def _load(name):
    f = RES / f"{name}.json"
    return json.loads(f.read_text()) if f.exists() else None


def _save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)
    return name


def integration():
    r = _load("integration_replay")
    if not r:
        return None
    names = list(r["rezonings"])
    keys = [("capacity", "Capacity", MUTED), ("capacity_prorated_to_2025", "Capacity pro-rated to 2025", B),
            ("likelihood_weighted", "Likelihood-weighted", A), ("observed", "Built by 2025", INK)]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(names))
    w = 0.2
    for k, (key, label, col) in enumerate(keys):
        v = [max(r["rezonings"][n]["homes_added_by_2025"][key], 1) for n in names]
        bars = ax.bar(x + (k - 1.5) * w, v, w, label=label, color=col)
        if key == "likelihood_weighted":
            lo = [r["rezonings"][n]["homes_added_by_2025"]["likelihood_weighted_95pct"][0] for n in names]
            hi = [r["rezonings"][n]["homes_added_by_2025"]["likelihood_weighted_95pct"][1] for n in names]
            ax.errorbar(x + (k - 1.5) * w, v, yerr=[np.maximum(np.array(v) - np.maximum(lo, 1), 0), np.array(hi) - np.array(v)],
                        fmt="none", ecolor=INK, elinewidth=0.8, capsize=2)
        for b_, val in zip(bars, v):
            ax.annotate(f"{val:,.0f}", (b_.get_x() + b_.get_width() / 2, val), ha="center", va="bottom", fontsize=6.5,
                        xytext=(0, 1), textcoords="offset points")
    ax.set_yscale("log")
    ax.set_xticks(x, names)
    ax.set_ylabel("Homes added on development sites")
    ax.legend(frameon=False, fontsize=7, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    ax.set_title("Projected and built homes after three Manhattan rezonings (bars: model 95% range)", fontsize=9, loc="left")
    return _save(fig, "integration_replay")


def rolling():
    r = _load("rolling_origin")
    if not r:
        return None
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.8))
    cols = {1: A, 3: B, 5: C}
    for h in (1, 3, 5):
        o = sorted([x for x in r["origins"] if x["horizon"] == h], key=lambda x: x["decision_year"])
        if not o:
            continue
        t = [x["decision_year"] for x in o]
        for ax, met, ci in ((axes[0], "auc", "auc_95ci"), (axes[1], "average_precision", "ap_95ci")):
            y = [x["lightgbm"][met] for x in o]
            lo = [x["lightgbm"][ci][0] for x in o]
            hi = [x["lightgbm"][ci][1] for x in o]
            ax.plot(t, y, marker="o", ms=3, color=cols[h], label=f"{h}-year")
            ax.fill_between(t, lo, hi, color=cols[h], alpha=0.15, lw=0)
        b = [max(v["auc"] for v in x["baselines"].values()) for x in o]
        axes[0].plot(t, b, ls="--", lw=0.8, color=cols[h])
    axes[0].set_ylabel("AUC (dashed: best simple baseline)")
    axes[1].set_ylabel("Average precision")
    for ax in axes:
        ax.set_xlabel("Decision year")
    axes[0].legend(frameon=False, fontsize=7, title="Horizon", title_fontsize=7)
    fig.suptitle("Redevelopment model tested forward in time (Manhattan, 2015-2025)", fontsize=9, x=0.01, ha="left")
    return _save(fig, "rolling_origin")


def crosscity():
    r = _load("crosscity_redevelopment")
    if not r:
        return None
    fig, ax = plt.subplots(figsize=(6.0, 2.6))
    rows, y = [], 0
    for city, t in r["tests"].items():
        for name, m in t["models"].items():
            rows.append((f"{city.title()}: {name}", m["auc"], m["auc_95ci"], y))
            y += 1
        b = t["baselines"][t["best_baseline"]]
        rows.append((f"{city.title()}: best baseline", b["auc"], [b["auc"], b["auc"]], y))
        y += 1.6
    for label, v, ci, yy in rows:
        col = MUTED if "baseline" in label else (B if "other city" in label else A)
        ax.errorbar(v, yy, xerr=[[v - ci[0]], [ci[1] - v]], fmt="o", ms=4, color=col, ecolor=col, capsize=2)
    ax.set_yticks([r_[3] for r_ in rows], [r_[0] for r_ in rows], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("AUC, new building within 3 years (95% tile bootstrap)")
    ax.set_title("Redevelopment model moved between cities", fontsize=9, loc="left")
    return _save(fig, "crosscity")


def tiers():
    names = sorted(p.stem[len("tier_a_vs_b_"):] for p in RES.glob("tier_a_vs_b_*.json"))
    if not names:
        return None
    t = {n: _load(f"tier_a_vs_b_{n}") for n in names}
    raw = [t[n]["floor_area_by_block"]["total_ratio"] for n in names]
    corr = [raw[i] / np.median([raw[j] for j in range(len(raw)) if j != i]) for i in range(len(raw))]
    acc = [t[n]["land_use"]["accuracy"] for n in names]
    maj = [t[n]["land_use"]["majority_class_accuracy"] for n in names]
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.6))
    x = np.arange(len(names))
    axes[0].bar(x - 0.2, raw, 0.4, color=MUTED, label="Footprint x floors")
    axes[0].bar(x + 0.2, corr, 0.4, color=A, label="Corrected (other cities)")
    axes[0].axhline(1, color=INK, lw=0.8)
    axes[0].set_ylabel("Tier A / records, floor area")
    axes[1].bar(x - 0.2, maj, 0.4, color=MUTED, label="Most common use")
    axes[1].bar(x + 0.2, acc, 0.4, color=C, label="Tier A rules")
    axes[1].set_ylabel("Land use accuracy, built lots")
    axes[1].set_ylim(0, 1)
    for ax in axes:
        ax.set_xticks(x, [n.title() for n in names], fontsize=7)
        ax.legend(frameon=False, fontsize=7)
    fig.suptitle("Tier A (national open data) scored against parcel records", fontsize=9, x=0.01, ha="left")
    return _save(fig, "tier_a_vs_b")


def main():
    made = [f() for f in (integration, rolling, crosscity, tiers)]
    print("written:", ", ".join(m for m in made if m))


if __name__ == "__main__":
    main()
