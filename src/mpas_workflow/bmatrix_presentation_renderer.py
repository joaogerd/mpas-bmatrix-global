"""Alternate renderer used by the presentation entry point."""
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
                if not valid.size:
                    raise ValueError("Surface-pressure explained variance has no finite values")
                row = valid[int(np.argmax(np.nanmean(np.abs(values[valid]), axis=1)))]
                profile = values[row]
                axis.plot(lat, profile, color=base.ACCENTS[0], linewidth=3.0)
                axis.fill_between(lat, 0.0, profile, color=base.ACCENTS[0], alpha=0.12)
                axis.set_ylim(0.0, 1.02)
                axis.set_ylabel("Fração da variância")
                axis.text(
                    0.03,
                    0.92,
                    f"campo de superfície (nível {row})",
                    transform=axis.transAxes,
                    color=base.MUTED,
                    fontsize=9.5,
                    ha="left",
                    va="top",
                )
                axis.grid(True)
            else:
                masked = np.ma.masked_invalid(values)
                filled = axis.contourf(
                    lat,
                    np.arange(values.shape[0]),
                    masked,
                    levels=levels_fill,
                    cmap="RdYlBu_r",
                    extend="neither",
                    antialiased=True,
                )
                lines = axis.contour(
                    lat,
                    np.arange(values.shape[0]),
                    masked,
                    levels=levels_line,
                    colors="#334155",
                    linewidths=0.55,
                    alpha=0.55,
                )
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


def plot_regression(vbal, output, target_lat, dpi):
    """Render the vertical regression with filled contours and a separate colorbar."""
    base.style()
    lat = base.latitudes(vbal)
    with base.netCDF4.Dataset(base.require(vbal / "VBAL/mpas_vbal.nc")) as ds:
        name, variable = base.group_variable(ds, "stream_function-temperature", "reg")
        values = base.clean(variable[:])

    if values.ndim != 3:
        raise ValueError(f"Expected a 3-D regression product, got {values.shape}")

    index = int(np.nanargmin(np.abs(lat - target_lat)))
    if values.shape[-1] == lat.size:
        matrix = values[:, :, index]
    elif values.shape[0] == lat.size:
        matrix = values[index, :, :]
    else:
        raise ValueError(f"Latitude length {lat.size} is incompatible with {values.shape}")

    finite = np.abs(matrix[np.isfinite(matrix)])
    if not finite.size:
        raise ValueError("Selected regression matrix has no finite values")
    amplitude = float(np.nanpercentile(finite, 98.0))
    if not np.isfinite(amplitude) or amplitude <= 0.0:
        amplitude = float(np.nanmax(finite))

    levels_fill = np.linspace(-amplitude, amplitude, 17)
    levels_line = np.linspace(-amplitude, amplitude, 9)
    fig = base.plt.figure(figsize=(8.8, 6.8))
    grid = fig.add_gridspec(
        1,
        2,
        width_ratios=[1.0, 0.055],
        wspace=0.08,
        left=0.10,
        right=0.93,
        bottom=0.10,
        top=0.86,
    )
    axis = fig.add_subplot(grid[0, 0])
    colorbar_axis = fig.add_subplot(grid[0, 1])
    fig.suptitle(rf"Regressão vertical $T \leftarrow \psi$ — {lat[index]:.1f}°", fontsize=17, y=0.94)

    x = np.arange(matrix.shape[1])
    y = np.arange(matrix.shape[0])
    filled = axis.contourf(
        x,
        y,
        matrix,
        levels=levels_fill,
        cmap="coolwarm",
        extend="both",
        antialiased=True,
    )
    contour_levels = levels_line[np.abs(levels_line) > max(amplitude * 0.05, np.finfo(float).eps)]
    lines = axis.contour(
        x,
        y,
        matrix,
        levels=contour_levels,
        colors="#334155",
        linewidths=0.45,
        alpha=0.45,
    )
    axis.clabel(lines, inline=True, fontsize=6, fmt="%.1e", colors="#475569")
    axis.contour(
        x,
        y,
        matrix,
        levels=[0.0],
        colors=base.FG,
        linewidths=1.0,
        alpha=0.75,
    )
    axis.set_xlabel(r"Nível de $\psi$")
    axis.set_ylabel(r"Nível de $T$")

    colorbar = fig.colorbar(filled, cax=colorbar_axis)
    colorbar.set_label("Coeficiente de regressão", labelpad=12)
    base.plt.setp(colorbar.ax.get_yticklabels(), color=base.MUTED)
    fig.savefig(output, dpi=dpi, transparent=True, bbox_inches="tight")
    base.plt.close(fig)
    return output


def plot_dirac(dirac, output, level, dpi, explicit):
    """Plot DIRAC response with a dedicated colorbar column outside the panels."""
    base.style()
    product = next(
        (path for path in (dirac / "mpas.dirac.nc", dirac / "DIRAC/mpas.dirac.nc") if path.is_file()),
        None,
    )
    if product is None:
        raise FileNotFoundError(f"mpas.dirac.nc is absent from {dirac}")

    with base.netCDF4.Dataset(product) as ds:
        variable = ds.variables["temperature"]
        _, center = base.field_level(variable, level)
        nlevels = variable.shape[variable.dimensions.index("nVertLevels")]
        levels = sorted(set((max(0, center - 5), center, min(nlevels - 1, center + 5))))
        fields = [base.field_level(variable, item)[0] for item in levels]

    lon, lat, source = base.coordinates(dirac, fields[0].size, explicit)
    peak = int(np.nanargmax(np.abs(fields[len(fields) // 2])))
    lon0 = float(lon[peak])
    lat0 = float(lat[peak])
    local_lon = ((lon - lon0 + 180.0) % 360.0) - 180.0

    maximum = max(float(np.nanmax(np.abs(field))) for field in fields)
    if not np.isfinite(maximum) or maximum <= 0.0:
        raise ValueError("DIRAC temperature response contains no finite nonzero value")

    dlon = 24.0
    dlat = 18.0
    local = (np.abs(local_lon) <= dlon) & (lat >= lat0 - dlat) & (lat <= lat0 + dlat)
    threshold = max(0.03 * maximum, np.finfo(float).eps)

    fig = base.plt.figure(figsize=(16.8, 5.9))
    grid = fig.add_gridspec(
        1,
        len(levels) + 1,
        width_ratios=[1.0] * len(levels) + [0.055],
        wspace=0.10,
        left=0.055,
        right=0.94,
        bottom=0.14,
        top=0.78,
    )
    axes = [fig.add_subplot(grid[0, index]) for index in range(len(levels))]
    colorbar_axis = fig.add_subplot(grid[0, -1])
    fig.suptitle("Resposta espacial da B a um impulso em temperatura (DIRAC)", fontsize=17, y=0.95)

    norm = base.TwoSlopeNorm(vcenter=0.0, vmin=-maximum, vmax=maximum)
    artist = None
    for axis, field, item in zip(axes, fields, levels):
        axis.scatter(
            local_lon[local],
            lat[local],
            s=6,
            color=base.GRID,
            alpha=0.22,
            linewidths=0,
            zorder=1,
        )
        signal = local & np.isfinite(field) & (np.abs(field) >= threshold)
        artist = axis.scatter(
            local_lon[signal],
            lat[signal],
            c=field[signal],
            s=28,
            cmap="coolwarm",
            norm=norm,
            linewidths=0,
            zorder=2,
        )
        axis.scatter(
            [0.0],
            [lat0],
            marker="x",
            s=105,
            color=base.FG,
            linewidths=2.2,
            zorder=3,
        )
        axis.set_title(f"Nível {item}")
        axis.set_xlabel("Longitude relativa ao impulso (°)")
        axis.set_xlim(-dlon, dlon)
        axis.set_ylim(lat0 - dlat, lat0 + dlat)
        axis.grid(True)

    axes[0].set_ylabel("Latitude (°)")
    colorbar = fig.colorbar(artist, cax=colorbar_axis)
    colorbar.set_label("Incremento de temperatura", labelpad=12)
    base.plt.setp(colorbar.ax.get_yticklabels(), color=base.MUTED)

    fig.text(
        0.01,
        0.035,
        f"Impulso: {lat0:.1f}°, {lon0:.1f}° | Coordenadas: {source.name}",
        fontsize=8,
        color=base.MUTED,
        ha="left",
        va="bottom",
    )
    fig.savefig(output, dpi=dpi, transparent=True, bbox_inches="tight")
    base.plt.close(fig)
    return output


def main(argv=None):
    base.plot_explained = plot_explained
    base.plot_regression = plot_regression
    base.plot_dirac = plot_dirac
    return base.main(argv)
