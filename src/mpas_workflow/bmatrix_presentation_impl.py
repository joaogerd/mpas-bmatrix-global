"""Compact presentation diagnostics for the JEDI-MPAS static B matrix."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib
import netCDF4
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.colors import PowerNorm, TwoSlopeNorm

matplotlib.use("Agg")

FG = "#1f2937"
MUTED = "#4b5563"
GRID = "#cbd5e1"
ACCENTS = ("#0099d7", "#00a98f", "#f17c0b", "#cf6ca7")
PAIRS = (
    ("stream_function-temperature", r"$T$ explicada por $\psi$"),
    ("stream_function-velocity_potential", r"$\chi$ explicada por $\psi$"),
    ("stream_function-surface_pressure", r"$p_s$ explicada por $\psi$"),
)
PROFILES = ("stream_function", "velocity_potential", "temperature", "spechum")
LABELS = {
    "stream_function": r"$\psi$",
    "velocity_potential": r"$\chi_u$",
    "temperature": r"$T_u$",
    "spechum": r"$q$",
}


def style() -> None:
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


def clean(values):
    array = np.ma.asarray(values, dtype=float).filled(np.nan)
    array = np.asarray(array, dtype=float)
    array[np.abs(array) > 1.0e30] = np.nan
    return array


def degrees(values):
    array = clean(values).ravel()
    finite = np.abs(array[np.isfinite(array)])
    if finite.size and np.nanmax(finite) <= 2.0 * np.pi + 0.1:
        array = np.degrees(array)
    return array


def finish(fig, output: Path, dpi: int) -> None:
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93) if fig._suptitle else None)
    fig.savefig(output, dpi=dpi, transparent=True, bbox_inches="tight")
    plt.close(fig)


def require(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"Required product not found: {path}")
    return path


def latitudes(vbal: Path):
    with netCDF4.Dataset(require(vbal / "VBAL/mpas_sampling.nc")) as ds:
        return degrees(ds.variables["lat_c2"][:])


def groups(group, prefix: str = ""):
    yield prefix, group
    for name, child in group.groups.items():
        child_prefix = f"{prefix}/{name}" if prefix else name
        yield from groups(child, child_prefix)


def group_variable(ds, group_name: str, prefix: str):
    for name, group in groups(ds):
        if name == group_name:
            for variable_name, variable in group.variables.items():
                if variable_name.startswith(prefix):
                    return variable_name, variable
    raise KeyError(f"No '{prefix}*' variable in group '{group_name}'")


def lat_level(values, lat):
    if values.ndim != 2:
        raise ValueError(f"Expected a 2-D product, got {values.shape}")
    if values.shape[1] == lat.size:
        return values
    if values.shape[0] == lat.size:
        return values.T
    raise ValueError(f"Latitude length {lat.size} is incompatible with {values.shape}")


def plot_explained(vbal: Path, output: Path, dpi: int) -> Path:
    style()
    lat = latitudes(vbal)
    order = np.argsort(lat)
    lat = lat[order]
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad(alpha=0.0)
    fig, axes = plt.subplots(1, 3, figsize=(15.6, 5.8))
    fig.suptitle("Matriz B — componente de variância explicada pelo balanço", fontsize=17)

    with netCDF4.Dataset(require(vbal / "VBAL/mpas_vbal.nc")) as ds:
        for axis, (pair, label) in zip(axes, PAIRS):
            name, variable = group_variable(ds, pair, "explained_var")
            values = lat_level(clean(variable[:]), lat)[..., order]
            if pair.endswith("surface_pressure"):
                valid = np.where(np.isfinite(values).any(axis=1))[0]
                if not valid.size:
                    raise ValueError("Surface-pressure explained variance has no finite values")
                row = valid[int(np.argmax(np.nanmean(np.abs(values[valid]), axis=1)))]
                profile = values[row]
                axis.plot(lat, profile, color=ACCENTS[0], linewidth=3.0)
                axis.fill_between(lat, 0.0, profile, color=ACCENTS[0], alpha=0.12)
                axis.set_ylim(0.0, 1.02)
                axis.set_ylabel("Fração da variância")
                axis.text(
                    0.03,
                    0.92,
                    f"campo de superfície (nível {row})",
                    transform=axis.transAxes,
                    ha="left",
                    va="top",
                    color=MUTED,
                    fontsize=9.5,
                )
                axis.grid(True)
            else:
                image = axis.imshow(
                    np.ma.masked_invalid(values),
                    origin="lower",
                    aspect="auto",
                    cmap=cmap,
                    interpolation="nearest",
                    norm=PowerNorm(gamma=0.55, vmin=0.0, vmax=1.0),
                    extent=(float(lat[0]), float(lat[-1]), 0, values.shape[0] - 1),
                )
                axis.set_ylabel("Nível vertical")
                colorbar = fig.colorbar(image, ax=axis, pad=0.015, fraction=0.046)
                colorbar.set_label("Fração da variância")
                plt.setp(colorbar.ax.get_yticklabels(), color=MUTED)
            axis.set_title(label)
            axis.set_xlabel("Latitude (°)")
    finish(fig, output, dpi)
    return output


def plot_regression(vbal: Path, output: Path, target_lat: float, dpi: int) -> Path:
    style()
    lat = latitudes(vbal)
    with netCDF4.Dataset(require(vbal / "VBAL/mpas_vbal.nc")) as ds:
        name, variable = group_variable(ds, "stream_function-temperature", "reg")
        values = clean(variable[:])
    index = int(np.nanargmin(np.abs(lat - target_lat)))
    matrix = values[:, :, index] if values.shape[-1] == lat.size else values[index]
    finite = np.abs(matrix[np.isfinite(matrix)])
    if not finite.size:
        raise ValueError("Selected regression matrix has no finite values")
    amplitude = float(np.nanpercentile(finite, 98.0)) or float(np.nanmax(finite))
    fig, axis = plt.subplots(figsize=(7.8, 6.8))
    image = axis.imshow(
        matrix,
        origin="lower",
        aspect="auto",
        cmap="coolwarm",
        interpolation="nearest",
        norm=TwoSlopeNorm(vcenter=0.0, vmin=-amplitude, vmax=amplitude),
    )
    axis.set_title(rf"Regressão vertical $T \leftarrow \psi$ — {lat[index]:.1f}°")
    axis.set_xlabel(r"Nível de $\psi$")
    axis.set_ylabel(r"Nível de $T$")
    colorbar = fig.colorbar(image, ax=axis, pad=0.025)
    colorbar.set_label("Coeficiente de regressão")
    plt.setp(colorbar.ax.get_yticklabels(), color=MUTED)
    finish(fig, output, dpi)
    return output


def profile(variable):
    values = clean(variable[:])
    dims = tuple(variable.dimensions)
    if "Time" in dims:
        values = np.take(values, 0, axis=dims.index("Time"))
        dims = tuple(dim for dim in dims if dim != "Time")
    if "nVertLevels" not in dims:
        return None
    values = np.moveaxis(values, dims.index("nVertLevels"), 0)
    return np.nanmean(values.reshape(values.shape[0], -1), axis=1)


def as_km(values, units: str):
    values = np.asarray(values, dtype=float)
    finite = np.abs(values[np.isfinite(values)])
    if "km" in (units or "").lower():
        return values
    if "m" in (units or "").lower() or (finite.size and np.nanmedian(finite) > 1e5):
        return values / 1000.0
    return values


def plot_profiles(hdiag: Path, output: Path, dpi: int) -> Path:
    style()
    sources = (
        (require(hdiag / "HDIAG/mpas.stddev.nc"), "Desvio-padrão", False),
        (require(hdiag / "HDIAG/mpas.cor_rh.nc"), "Escala horizontal", True),
        (require(hdiag / "HDIAG/mpas.cor_rv.nc"), "Escala vertical", True),
    )
    fig, axes = plt.subplots(1, 3, figsize=(16.2, 6.1), sharey=True)
    fig.suptitle("Matriz B — amplitude e escalas de correlação diagnosticadas", fontsize=17)
    for axis, (path, title, convert_km) in zip(axes, sources):
        with netCDF4.Dataset(path) as ds:
            for color, name in zip(ACCENTS, PROFILES):
                if name not in ds.variables:
                    continue
                values = profile(ds.variables[name])
                if values is None or not np.isfinite(values).any():
                    continue
                if convert_km:
                    values = as_km(values, getattr(ds.variables[name], "units", ""))
                axis.plot(values, np.arange(values.size), color=color, linewidth=2.8, label=LABELS[name])
        axis.set_title(title)
        axis.set_xlabel("km" if convert_km else "desvio-padrão")
        axis.grid(True)
        axis.legend(loc="best", fontsize=10)
    axes[0].set_ylabel("Nível vertical")
    finish(fig, output, dpi)
    return output


def readme_workspace(workspace: Path, label: str) -> Path | None:
    path = workspace / "README.md"
    if not path.is_file():
        return None
    match = re.search(rf"(?m)^{re.escape(label)}:\s*`([^`]+)`\s*$", path.read_text())
    return Path(match.group(1)) if match else None


def coordinate_files(workspace: Path, explicit: str | None):
    candidates = [Path(explicit)] if explicit else []
    roots = [workspace, workspace / "DIRAC"]
    hdiag = readme_workspace(workspace, "HDIAG workspace")
    if hdiag:
        roots += [hdiag, hdiag / "HDIAG"]
    if workspace.parent.name == "dirac":
        sibling = workspace.parent.parent / "hdiag" / workspace.name
        roots += [sibling, sibling / "HDIAG"]
    for root in roots:
        candidates += [root / "x1.10242.invariant.nc", root / "bg.nc", root / "mpas.dirac.nc"]
        candidates += sorted(root.glob("*invariant*.nc")) + sorted(root.glob("*.nc"))
    unique = []
    for path in candidates:
        if path not in unique:
            unique.append(path)
    return unique


def coordinates(workspace: Path, size: int, explicit: str | None):
    checked = []
    for path in coordinate_files(workspace, explicit):
        if not path.is_file():
            continue
        checked.append(str(path))
        try:
            with netCDF4.Dataset(path) as ds:
                if "latCell" not in ds.variables or "lonCell" not in ds.variables:
                    continue
                lat, lon = degrees(ds.variables["latCell"][:]), degrees(ds.variables["lonCell"][:])
        except OSError:
            continue
        if lat.size == size and lon.size == size:
            return ((lon + 180.0) % 360.0) - 180.0, lat, path
    raise KeyError("No compatible latCell/lonCell found. Checked: " + ", ".join(checked))


def field_level(variable, level: int):
    values = clean(variable[:])
    dims = tuple(variable.dimensions)
    if "Time" in dims:
        values = np.take(values, 0, axis=dims.index("Time"))
        dims = tuple(dim for dim in dims if dim != "Time")
    if "nVertLevels" not in dims or "nCells" not in dims:
        raise ValueError(f"Expected cell/vertical field, got {dims}")
    index = min(max(level, 0), values.shape[dims.index("nVertLevels")] - 1)
    values = np.take(values, index, axis=dims.index("nVertLevels"))
    dims = tuple(dim for dim in dims if dim != "nVertLevels")
    if dims.index("nCells") != 0:
        values = np.moveaxis(values, dims.index("nCells"), 0)
    return values.ravel(), index


def plot_dirac(dirac: Path, output: Path, level: int, dpi: int, explicit: str | None) -> Path:
    style()
    product = next((p for p in (dirac / "mpas.dirac.nc", dirac / "DIRAC/mpas.dirac.nc") if p.is_file()), None)
    if product is None:
        raise FileNotFoundError(f"mpas.dirac.nc is absent from {dirac}")
    with netCDF4.Dataset(product) as ds:
        variable = ds.variables["temperature"]
        center_field, center = field_level(variable, level)
        nlevels = variable.shape[variable.dimensions.index("nVertLevels")]
        levels = sorted(set((max(0, center - 5), center, min(nlevels - 1, center + 5))))
        fields = [field_level(variable, item)[0] for item in levels]
    lon, lat, source = coordinates(dirac, fields[0].size, explicit)
    peak = int(np.nanargmax(np.abs(fields[len(fields) // 2])))
    lon0, lat0 = float(lon[peak]), float(lat[peak])
    local_lon = ((lon - lon0 + 180.0) % 360.0) - 180.0
    maximum = max(float(np.nanmax(np.abs(field))) for field in fields)
    dlon, dlat = 24.0, 18.0
    local = (np.abs(local_lon) <= dlon) & (lat >= lat0 - dlat) & (lat <= lat0 + dlat)
    threshold = max(0.03 * maximum, np.finfo(float).eps)

    fig, axes = plt.subplots(1, len(levels), figsize=(15.6, 5.7), sharex=True, sharey=True)
    axes = np.atleast_1d(axes)
    fig.suptitle("Resposta espacial da B a um impulso em temperatura (DIRAC)", fontsize=17)
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-maximum, vmax=maximum)
    for axis, field, item in zip(axes, fields, levels):
        axis.scatter(local_lon[local], lat[local], s=6, color=GRID, alpha=0.22, linewidths=0, zorder=1)
        signal = local & np.isfinite(field) & (np.abs(field) >= threshold)
        artist = axis.scatter(local_lon[signal], lat[signal], c=field[signal], s=28, cmap="coolwarm", norm=norm, linewidths=0, zorder=2)
        axis.scatter([0.0], [lat0], marker="x", s=105, color=FG, linewidths=2.2, zorder=3)
        axis.set_title(f"Nível {item}")
        axis.set_xlabel("Longitude relativa ao impulso (°)")
        axis.set_xlim(-dlon, dlon)
        axis.set_ylim(lat0 - dlat, lat0 + dlat)
        axis.grid(True)
    axes[0].set_ylabel("Latitude (°)")
    colorbar = fig.colorbar(artist, ax=list(axes), pad=0.02, fraction=0.027)
    colorbar.set_label("Incremento de temperatura")
    plt.setp(colorbar.ax.get_yticklabels(), color=MUTED)
    fig.text(0.01, 0.01, f"Impulso: {lat0:.1f}°, {lon0:.1f}° | Coordenadas: {source.name}", fontsize=8, color=MUTED)
    finish(fig, output, dpi)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render presentation-ready JEDI-MPAS B-matrix figures")
    parser.add_argument("--vbal-workspace", required=True)
    parser.add_argument("--hdiag-workspace", required=True)
    parser.add_argument("--dirac-workspace")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--coordinates-file")
    parser.add_argument("--latitude", type=float, default=35.0)
    parser.add_argument("--level", type=int, default=15)
    parser.add_argument("--dpi", type=int, default=240)
    args = parser.parse_args(argv)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    figures = [
        plot_explained(Path(args.vbal_workspace), output / "01_bmatrix_balance_explained_variance.png", args.dpi),
        plot_regression(Path(args.vbal_workspace), output / "02_bmatrix_temperature_psi_regression.png", args.latitude, args.dpi),
        plot_profiles(Path(args.hdiag_workspace), output / "03_bmatrix_stddev_and_correlation_scales.png", args.dpi),
    ]
    if args.dirac_workspace:
        figures.append(plot_dirac(Path(args.dirac_workspace), output / "04_bmatrix_dirac_temperature_response.png", args.level, args.dpi, args.coordinates_file))
    (output / "README.md").write_text("# Figuras da matriz B\n\n" + "\n".join(f"- `{item.name}`" for item in figures) + "\n")
    for item in figures:
        print(f"FIGURE={item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
