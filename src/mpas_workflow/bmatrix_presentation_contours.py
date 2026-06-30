"""Contour renderer for the explained-variance presentation figure."""
from __future__ import annotations

import numpy as np
import mpas_workflow.bmatrix_presentation_impl as base


def plot_explained(vbal, output, dpi):
    base.style()
    lat_raw = base.latitudes(vbal)
    order = np.argsort(lat_raw)
    lat = lat_raw[order]
    levels_fill = np.linspace(0.0, 1.0, 11)
    levels_line = np.linspace(0.1, 0.9, 5)
    fig, axes = base.plt.subplots(1, 3, figsize=(15.8, 5.9), sharey=False)
    fig.suptitle("Matriz B — componente de variância explicada pelo balanço", fontsize=17)
    with base.netCDF4.Dataset(base.require(vbal / "VBAL/mpas_vbal.nc")) as ds:
        for axis, pair_data in zip(axes, base.PAIRS):
            pair, label = pair_data
            _, variable = base.group_variable(ds, pair, "explained_var")
            values = base.lat_level(base.clean(variable[:]), lat_raw)[:, order]
            if pair.endswith("surface_pressure"):
                valid = np.where(np.isfinite(values).any(axis=1))[0]
                row = valid[int(np.argmax(np.nanmean(np.abs(values[valid]), axis=1)))]
                profile = values[row]
                axis.plot(lat, profile, color=base.ACCENTS[0], linewidth=3.0)
                axis.fill_between(lat, 0.0, profile, color=base.ACCENTS[0], alpha=0.12)
                axis.set_ylim(0.0, 1.02)
                axis.set_ylabel("Fração da variância")
                axis.text(0.03, 0.92, f"campo de superfície (nível {row})", transform=axis.transAxes, color=base.MUTED, fontsize=9.5, ha="left", va="top")
                axis.grid(True)
            else:
                masked = np.ma.masked_invalid(values)
                filled = axis.contourf(lat, np.arange(values.shape[0]), masked, levels=levels_fill, cmap="RdYlBu_r", extend="neither", antialiased=True)
                lines = axis.contour(lat, np.arange(values.shape[0]), masked, levels=levels_line, colors="#334155", linewidths=0.55, alpha=0.55)
                axis.clabel(lines, inline=True, fontsize=7, fmt="%.1f", colors="#475569")
                axis.set_ylabel("Nível vertical")
                colorbar = fig.colorbar(filled, ax=axis, pad=0.015, fraction=0.046)
                colorbar.set_label("Fração da variância")
                colorbar.set_ticks(np.linspace(0.0, 1.0, 6))
                base.plt.setp(colorbar.ax.get_yticklabels(), color=base.MUTED)
            axis.set_title(label)
            axis.set_xlabel("Latitude (°)")
    base.finish(fig, output, dpi)
    return output


def main(argv=None):
    base.plot_explained = plot_explained
    return base.main(argv)
