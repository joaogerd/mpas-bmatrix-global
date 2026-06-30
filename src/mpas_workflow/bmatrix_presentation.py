"""Presentation-ready diagnostics for a JEDI-MPAS static B-matrix workspace.

The module renders a compact set of science-oriented figures from the VBAL,
HDIAG and (optionally) DIRAC products. PNGs are written with transparent
backgrounds so they can be placed directly on presentation slides.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable


PAIR_SPECS = (
    ("stream_function-temperature", r"T explained by $\psi$"),
    ("stream_function-velocity_potential", r"$\chi$ explained by $\psi$"),
    ("stream_function-surface_pressure", r"$p_s$ explained by $\psi$"),
)
PROFILE_VARIABLES = ("stream_function", "velocity_potential", "temperature", "spechum")
LINE_LABELS = {
    "stream_function": r"$\psi$",
    "velocity_potential": r"$\chi_u$",
    "temperature": r"$T_u$",
    "spechum": r"$q$",
}

FG = "#1f2937"
MUTED = "#4b5563"
GRID = "#cbd5e1"
ACCENTS = ("#0099d7", "#00a98f", "#f17c0b", "#cf6ca7")


def _imports():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import netCDF4
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm

    return plt, np, TwoSlopeNorm, netCDF4


def _style(plt) -> None:
    """Apply the transparent, slide-friendly visual style."""
    plt.rcParams.update(
        {
            "figure.facecolor": "none",
            "axes.facecolor": "none",
            "savefig.facecolor": "none",
            "savefig.edgecolor": "none",
            "savefig.transparent": True,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": FG,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "text.color": FG,
            "axes.titlecolor": FG,
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titleweight": "bold",
            "axes.titlepad": 12,
            "grid.color": GRID,
            "grid.alpha": 0.9,
            "grid.linestyle": ":",
            "grid.linewidth": 0.8,
            "legend.facecolor": "none",
            "legend.edgecolor": GRID,
            "legend.labelcolor": FG,
        }
    )


def _clean(values, np):
    arr = np.ma.asarray(values, dtype=float).filled(np.nan)
    arr = np.asarray(arr, dtype=float)
    arr[np.abs(arr) > 1.0e30] = np.nan
    return arr


def _degrees(values, np):
    values = _clean(values, np).ravel()
    if values.size and np.nanmax(np.abs(values)) <= np.pi + 0.1:
        values = np.degrees(values)
    return values


def _find_file(workspace: Path, relative: str) -> Path:
    path = workspace / relative
    if not path.is_file():
        raise FileNotFoundError(f"Required product not found: {path}")
    return path


def _resolve_dirac_product(workspace: Path) -> Path:
    """Accept either the DIRAC run directory or its parent workspace."""
    candidates = [workspace / "mpas.dirac.nc", workspace / "DIRAC" / "mpas.dirac.nc"]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "DIRAC product not found. Checked: " + ", ".join(str(path) for path in candidates)
    )


def _latitudes(vbal_workspace: Path, netCDF4, np):
    path = _find_file(vbal_workspace, "VBAL/mpas_sampling.nc")
    with netCDF4.Dataset(path) as ds:
        if "lat_c2" not in ds.variables:
            raise KeyError(f"lat_c2 is absent from {path}")
        return _degrees(ds.variables["lat_c2"][:], np)


def _walk_groups(group, prefix: str = ""):
    yield prefix, group
    for name, child in group.groups.items():
        child_prefix = f"{prefix}/{name}" if prefix else name
        yield from _walk_groups(child, child_prefix)


def _group_variable(ds, pair: str, startswith: str):
    for group_name, group in _walk_groups(ds):
        if group_name != pair:
            continue
        for name, variable in group.variables.items():
            if name.startswith(startswith):
                return name, variable
    raise KeyError(f"No '{startswith}*' product in VBAL group '{pair}'")


def _profile(variable, np):
    values = _clean(variable[:], np)
    dims = tuple(variable.dimensions)
    if "Time" in dims:
        axis = dims.index("Time")
        values = np.take(values, 0, axis=axis)
        dims = tuple(dim for dim in dims if dim != "Time")
    if "nVertLevels" not in dims:
        return None
    level_axis = dims.index("nVertLevels")
    values = np.moveaxis(values, level_axis, 0)
    return np.nanmean(values.reshape(values.shape[0], -1), axis=1)


def _km(values, units: str, np):
    lower = (units or "").lower()
    arr = np.asarray(values, dtype=float)
    if "km" in lower:
        return arr
    finite = np.abs(arr[np.isfinite(arr)])
    if "m" in lower or (finite.size and np.nanmedian(finite) > 1.0e5):
        return arr / 1000.0
    return arr


def _finish(fig, output: Path, dpi: int) -> None:
    if fig._suptitle is None:
        fig.tight_layout()
    else:
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(output, dpi=dpi, transparent=True, bbox_inches="tight")
    fig.clear()


def plot_explained_variance(vbal_workspace: Path, output: Path, dpi: int) -> Path:
    plt, np, _, netCDF4 = _imports()
    _style(plt)
    lat = _latitudes(vbal_workspace, netCDF4, np)
    path = _find_file(vbal_workspace, "VBAL/mpas_vbal.nc")
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.7), sharey=True)
    fig.suptitle("Matriz B — componente de variância explicada pelo balanço", fontsize=17)
    with netCDF4.Dataset(path) as ds:
        for axis, (pair, label) in zip(axes, PAIR_SPECS):
            name, variable = _group_variable(ds, pair, "explained_var")
            values = _clean(variable[:], np)
            if values.ndim != 2:
                raise ValueError(f"Expected 2-D '{name}' in {pair}; found {values.shape}")
            if values.shape[1] != lat.size and values.shape[0] == lat.size:
                values = values.T
            if values.shape[1] != lat.size:
                raise ValueError(f"Latitude length {lat.size} is incompatible with {pair}: {values.shape}")
            order = np.argsort(lat)
            image = axis.imshow(
                values[:, order],
                origin="lower",
                aspect="auto",
                cmap="viridis",
                vmin=0.0,
                vmax=1.0,
                extent=(float(lat[order][0]), float(lat[order][-1]), 0, values.shape[0] - 1),
            )
            axis.set_title(label)
            axis.set_xlabel("Latitude (°)")
            axis.grid(False)
            cbar = fig.colorbar(image, ax=axis, pad=0.015, fraction=0.046)
            cbar.set_label("Fração da variância")
            cbar.ax.yaxis.set_tick_params(color=MUTED)
            plt.setp(cbar.ax.get_yticklabels(), color=MUTED)
    axes[0].set_ylabel("Nível vertical")
    _finish(fig, output, dpi)
    return output


def plot_temperature_regression(
    vbal_workspace: Path,
    output: Path,
    latitude: float,
    dpi: int,
) -> Path:
    plt, np, TwoSlopeNorm, netCDF4 = _imports()
    _style(plt)
    lat = _latitudes(vbal_workspace, netCDF4, np)
    path = _find_file(vbal_workspace, "VBAL/mpas_vbal.nc")
    with netCDF4.Dataset(path) as ds:
        name, variable = _group_variable(ds, "stream_function-temperature", "reg")
        values = _clean(variable[:], np)
    if values.ndim != 3:
        raise ValueError(f"Expected 3-D '{name}', found {values.shape}")
    index = int(np.nanargmin(np.abs(lat - latitude)))
    if values.shape[-1] == lat.size:
        matrix = values[:, :, index]
    elif values.shape[0] == lat.size:
        matrix = values[index, :, :]
    else:
        raise ValueError(f"Latitude length {lat.size} is incompatible with regression shape {values.shape}")
    amplitude = float(np.nanmax(np.abs(matrix)))
    if not np.isfinite(amplitude) or amplitude == 0.0:
        raise ValueError("The selected temperature-balance matrix contains no finite nonzero value")
    fig, ax = plt.subplots(figsize=(7.4, 6.4))
    image = ax.imshow(
        matrix,
        origin="lower",
        aspect="auto",
        cmap="coolwarm",
        norm=TwoSlopeNorm(vcenter=0.0, vmin=-amplitude, vmax=amplitude),
    )
    ax.set_title(rf"Regressão vertical $T \leftarrow \psi$ — {float(lat[index]):.1f}°")
    ax.set_xlabel(r"Nível de $\psi$")
    ax.set_ylabel(r"Nível de $T$")
    cbar = fig.colorbar(image, ax=ax, pad=0.025)
    cbar.set_label("Coeficiente de regressão")
    cbar.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cbar.ax.get_yticklabels(), color=MUTED)
    _finish(fig, output, dpi)
    return output


def plot_hdiag_profiles(hdiag_workspace: Path, output: Path, dpi: int) -> Path:
    plt, np, _, netCDF4 = _imports()
    _style(plt)
    stddev_path = _find_file(hdiag_workspace, "HDIAG/mpas.stddev.nc")
    rh_path = _find_file(hdiag_workspace, "HDIAG/mpas.cor_rh.nc")
    rv_path = _find_file(hdiag_workspace, "HDIAG/mpas.cor_rv.nc")

    fig, axes = plt.subplots(1, 3, figsize=(16.2, 6.1), sharey=True)
    fig.suptitle("Matriz B — amplitude e escalas de correlação diagnosticadas", fontsize=17)
    inputs = (
        (stddev_path, "Desvio-padrão", None),
        (rh_path, "Escala horizontal", "km"),
        (rv_path, "Escala vertical", "km"),
    )
    for axis, (path, title, target_units) in zip(axes, inputs):
        count = 0
        with netCDF4.Dataset(path) as ds:
            for color, name in zip(ACCENTS, PROFILE_VARIABLES):
                if name not in ds.variables:
                    continue
                variable = ds.variables[name]
                profile = _profile(variable, np)
                if profile is None or not np.isfinite(profile).any():
                    continue
                if target_units == "km":
                    profile = _km(profile, getattr(variable, "units", ""), np)
                axis.plot(
                    profile,
                    np.arange(profile.size),
                    linewidth=2.8,
                    color=color,
                    label=LINE_LABELS[name],
                )
                count += 1
        if not count:
            raise KeyError(f"No usable vertical profiles found in {path}")
        axis.set_title(title)
        axis.set_xlabel("km" if target_units == "km" else "desvio-padrão")
        axis.grid(True)
        axis.legend(loc="best", fontsize=10)
    axes[0].set_ylabel("Nível vertical")
    _finish(fig, output, dpi)
    return output


def _workspace_from_readme(workspace: Path, label: str) -> Path | None:
    readme = workspace / "README.md"
    if not readme.is_file():
        return None
    match = re.search(
        rf"(?m)^{re.escape(label)}:\s*`([^`]+)`\s*$",
        readme.read_text(encoding="utf-8", errors="replace"),
    )
    return Path(match.group(1)) if match else None


def _append_candidate(candidates: list[Path], path: Path) -> None:
    if path not in candidates:
        candidates.append(path)


def _coordinate_candidates(workspace: Path, coordinates_file: str | None) -> list[Path]:
    candidates: list[Path] = []
    if coordinates_file:
        _append_candidate(candidates, Path(coordinates_file))

    roots = [workspace, workspace / "DIRAC"]
    hdiag_from_readme = _workspace_from_readme(workspace, "HDIAG workspace")
    if hdiag_from_readme is not None:
        roots.extend([hdiag_from_readme, hdiag_from_readme / "HDIAG"])

    # Standard pipeline layout: covariance/dirac/<name> and covariance/hdiag/<name>.
    if workspace.parent.name == "dirac":
        hdiag_sibling = workspace.parent.parent / "hdiag" / workspace.name
        roots.extend([hdiag_sibling, hdiag_sibling / "HDIAG"])

    unique_roots: list[Path] = []
    for root in roots:
        if root not in unique_roots:
            unique_roots.append(root)

    for root in unique_roots:
        for name in ("x1.10242.invariant.nc", "bg.nc", "mpas.dirac.nc"):
            _append_candidate(candidates, root / name)
        for path in sorted(root.glob("*invariant*.nc")):
            _append_candidate(candidates, path)
        for path in sorted(root.glob("*.nc")):
            _append_candidate(candidates, path)

    return candidates


def _coordinates(
    workspace: Path,
    netCDF4,
    np,
    expected_size: int,
    coordinates_file: str | None = None,
):
    """Find MPAS cell coordinates, including the linked HDIAG workspace fallback."""
    checked: list[str] = []
    for path in _coordinate_candidates(workspace, coordinates_file):
        if not path.is_file():
            continue
        checked.append(str(path))
        try:
            with netCDF4.Dataset(path) as ds:
                if "latCell" not in ds.variables or "lonCell" not in ds.variables:
                    continue
                lat = _degrees(ds.variables["latCell"][:], np)
                lon = _degrees(ds.variables["lonCell"][:], np)
        except OSError:
            continue
        if lat.size != expected_size or lon.size != expected_size:
            continue
        lon = ((lon + 180.0) % 360.0) - 180.0
        return lon, lat, path

    detail = ", ".join(checked) if checked else "no readable NetCDF candidate"
    raise KeyError(
        "latCell/lonCell compatible with the DIRAC field were not found. "
        f"Checked: {detail}. Use --coordinates-file to supply an MPAS invariant or background file."
    )


def _field_at_level(variable, level: int, np):
    values = _clean(variable[:], np)
    dims = tuple(variable.dimensions)
    if "Time" in dims:
        axis = dims.index("Time")
        values = np.take(values, 0, axis=axis)
        dims = tuple(dim for dim in dims if dim != "Time")
    if "nVertLevels" not in dims or "nCells" not in dims:
        raise ValueError(f"Expected a cell/vertical field, found dimensions {dims}")
    level_axis = dims.index("nVertLevels")
    nlevels = values.shape[level_axis]
    selected = min(max(level, 0), nlevels - 1)
    values = np.take(values, selected, axis=level_axis)
    dims = tuple(dim for dim in dims if dim != "nVertLevels")
    if "nCells" not in dims:
        raise ValueError("nCells disappeared after level selection")
    if dims.index("nCells") != 0:
        values = np.moveaxis(values, dims.index("nCells"), 0)
    return np.asarray(values, dtype=float).ravel(), selected, nlevels


def plot_dirac_temperature(
    dirac_workspace: Path,
    output: Path,
    level: int,
    dpi: int,
    coordinates_file: str | None = None,
) -> Path:
    plt, np, TwoSlopeNorm, netCDF4 = _imports()
    _style(plt)
    path = _resolve_dirac_product(dirac_workspace)
    with netCDF4.Dataset(path) as ds:
        if "temperature" not in ds.variables:
            raise KeyError(f"temperature is absent from {path}")
        variable = ds.variables["temperature"]
        _, center, nlevels = _field_at_level(variable, level, np)
        levels = sorted(set((max(0, center - 5), center, min(nlevels - 1, center + 5))))
        fields = [_field_at_level(variable, item, np)[0] for item in levels]

    expected_size = fields[0].size
    if any(field.size != expected_size for field in fields):
        raise ValueError("DIRAC temperature slices have inconsistent cell dimensions")
    lon, lat, coordinate_source = _coordinates(
        dirac_workspace,
        netCDF4,
        np,
        expected_size=expected_size,
        coordinates_file=coordinates_file,
    )
    maximum = max(float(np.nanmax(np.abs(field))) for field in fields)
    if not np.isfinite(maximum) or maximum == 0.0:
        raise ValueError("DIRAC temperature response contains no finite nonzero value")

    fig, axes = plt.subplots(1, len(levels), figsize=(15.5, 5.4), sharex=True, sharey=True)
    if len(levels) == 1:
        axes = [axes]
    fig.suptitle("Resposta espacial da B a um impulso em temperatura (DIRAC)", fontsize=17)
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-maximum, vmax=maximum)
    for axis, field, item in zip(axes, fields, levels):
        scatter = axis.scatter(lon, lat, c=field, s=8, cmap="coolwarm", norm=norm, linewidths=0)
        peak = int(np.nanargmax(np.abs(field)))
        axis.scatter([lon[peak]], [lat[peak]], marker="x", s=72, color=FG, linewidths=1.8, zorder=3)
        axis.set_title(f"Nível {item}")
        axis.set_xlabel("Longitude (°)")
        axis.grid(True)
    axes[0].set_ylabel("Latitude (°)")
    cbar = fig.colorbar(scatter, ax=list(axes), pad=0.02, fraction=0.027)
    cbar.set_label("Incremento de temperatura")
    cbar.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cbar.ax.get_yticklabels(), color=MUTED)
    fig.text(
        0.01,
        0.01,
        f"Coordenadas: {coordinate_source.name}",
        fontsize=8,
        color=MUTED,
        ha="left",
        va="bottom",
    )
    _finish(fig, output, dpi)
    return output


def _write_readme(
    output: Path,
    figures: Iterable[Path],
    vbal: Path,
    hdiag: Path,
    dirac: Path | None,
    coordinates_file: str | None,
) -> None:
    lines = [
        "# Figuras para apresentação — primeira matriz B",
        "",
        "Estas figuras são diagnósticos de uma matriz B de baseline/smoke. Elas não devem ser apresentadas como estatística final de produção.",
        "",
        f"- VBAL: `{vbal}`",
        f"- HDIAG: `{hdiag}`",
        f"- DIRAC: `{dirac}`" if dirac else "- DIRAC: não informado",
        f"- Arquivo de coordenadas explícito: `{coordinates_file}`" if coordinates_file else "- Arquivo de coordenadas explícito: não informado (busca automática)",
        "",
        "## Produtos",
        "",
    ]
    lines.extend(f"- `{figure.name}`" for figure in figures)
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render presentation-ready diagnostics for a JEDI-MPAS B-matrix"
    )
    parser.add_argument("--vbal-workspace", required=True)
    parser.add_argument("--hdiag-workspace", required=True)
    parser.add_argument("--dirac-workspace")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--coordinates-file",
        help="Optional MPAS NetCDF file containing latCell/lonCell; use this only if automatic discovery fails.",
    )
    parser.add_argument(
        "--latitude",
        type=float,
        default=35.0,
        help="Target latitude for the T<-psi regression figure",
    )
    parser.add_argument(
        "--level",
        type=int,
        default=15,
        help="Central vertical level for the DIRAC response",
    )
    parser.add_argument("--dpi", type=int, default=240)
    args = parser.parse_args(argv)

    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    vbal = Path(args.vbal_workspace)
    hdiag = Path(args.hdiag_workspace)
    dirac = Path(args.dirac_workspace) if args.dirac_workspace else None

    figures = [
        plot_explained_variance(vbal, output / "01_bmatrix_balance_explained_variance.png", args.dpi),
        plot_temperature_regression(
            vbal,
            output / "02_bmatrix_temperature_psi_regression.png",
            args.latitude,
            args.dpi,
        ),
        plot_hdiag_profiles(hdiag, output / "03_bmatrix_stddev_and_correlation_scales.png", args.dpi),
    ]
    if dirac:
        figures.append(
            plot_dirac_temperature(
                dirac,
                output / "04_bmatrix_dirac_temperature_response.png",
                args.level,
                args.dpi,
                coordinates_file=args.coordinates_file,
            )
        )
    _write_readme(output, figures, vbal, hdiag, dirac, args.coordinates_file)
    for figure in figures:
        print(f"FIGURE={figure}")
    print(f"README={output / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
