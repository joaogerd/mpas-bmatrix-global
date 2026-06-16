from __future__ import annotations

import argparse
import re
from pathlib import Path


def safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "field"


def iter_group_variables(group, prefix: str = ""):
    for name, variable in group.variables.items():
        yield prefix, name, variable
    for name, child in group.groups.items():
        child_prefix = f"{prefix}/{name}" if prefix else name
        yield from iter_group_variables(child, child_prefix)


def finite(values):
    import numpy as np

    arr = np.ma.asarray(values, dtype=float).filled(np.nan)
    arr[np.abs(arr) > 1.0e30] = np.nan
    return arr


def load_lat_c2(workspace: Path):
    import netCDF4
    import numpy as np

    path = workspace / "VBAL" / "mpas_sampling.nc"
    with netCDF4.Dataset(path) as ds:
        lat = finite(ds.variables["lat_c2"][:])
    if lat.size and np.nanmax(np.abs(lat)) <= np.pi + 0.1:
        lat = np.degrees(lat)
    return lat


def diagonal_levels(values):
    import numpy as np

    arr = finite(values)
    if arr.ndim != 3 or arr.shape[0] != arr.shape[1]:
        return None
    diag = np.diagonal(arr, axis1=0, axis2=1)
    if diag.shape[0] == arr.shape[2]:
        diag = diag.T
    return diag


def plot_lat_level(values, lat, path: Path, title: str, label: str, dpi: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    order = np.argsort(lat)
    arr = arr[:, order]
    lat = lat[order]
    valid = arr[np.isfinite(arr)]
    if valid.size == 0:
        return
    cmap = "coolwarm" if np.nanmin(valid) < 0 and np.nanmax(valid) > 0 else "viridis"
    fig, ax = plt.subplots(figsize=(9, 5))
    image = ax.imshow(
        arr,
        origin="lower",
        aspect="auto",
        cmap=cmap,
        extent=[float(lat[0]), float(lat[-1]), 0, arr.shape[0] - 1],
    )
    ax.set_title(title)
    ax.set_xlabel("latitude")
    ax.set_ylabel("vertical level")
    fig.colorbar(image, ax=ax, label=label)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def plot_profile(values, path: Path, title: str, label: str, dpi: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = finite(values)
    profile = np.nanmean(arr, axis=1) if arr.ndim == 2 else arr
    fig, ax = plt.subplots(figsize=(5, 7))
    ax.plot(profile, np.arange(profile.size))
    ax.set_title(title)
    ax.set_xlabel(label)
    ax.set_ylabel("vertical level")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=dpi)
    plt.close(fig)


def plot_vbal_groups(workspace: str | Path, output_dir: str | Path | None = None, dpi: int = 150) -> list[Path]:
    import netCDF4

    workspace = Path(workspace)
    output = Path(output_dir) if output_dir else workspace / "VBAL" / "figures_vbal_groups"
    output.mkdir(parents=True, exist_ok=True)
    lat = load_lat_c2(workspace)
    vbal = workspace / "VBAL" / "mpas_vbal.nc"
    figures: list[Path] = []
    lines = ["# VBAL grouped diagnostics", "", f"Workspace: `{workspace}`", "", "| group | variable | shape |", "| --- | --- | --- |"]
    with netCDF4.Dataset(vbal) as ds:
        for group_name, variable_name, variable in iter_group_variables(ds):
            values = finite(variable[:])
            lines.append(f"| {group_name} | {variable_name} | `{values.shape}` |")
            stem = f"vbal_{safe_stem(group_name)}_{safe_stem(variable_name)}"
            if variable_name.startswith("explained_var") and values.ndim == 2:
                fig = output / f"{stem}_lat_level.png"
                plot_lat_level(values, lat, fig, f"{group_name} {variable_name}", variable_name, dpi)
                figures.append(fig)
                prof = output / f"{stem}_profile.png"
                plot_profile(values, prof, f"Mean profile {group_name} {variable_name}", variable_name, dpi)
                figures.append(prof)
            elif variable_name.startswith(("reg", "cov")) and values.ndim == 3:
                diag = diagonal_levels(values)
                if diag is not None:
                    fig = output / f"{stem}_diag_lat_level.png"
                    plot_lat_level(diag, lat, fig, f"Diagonal {group_name} {variable_name}", variable_name, dpi)
                    figures.append(fig)
                    prof = output / f"{stem}_diag_profile.png"
                    plot_profile(diag, prof, f"Mean diagonal profile {group_name} {variable_name}", variable_name, dpi)
                    figures.append(prof)
    report = output / "vbal_group_diagnostics.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"REPORT={report}")
    for figure in figures:
        print(f"FIGURE={figure}")
    return figures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plot grouped variables in VBAL/mpas_vbal.nc")
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args(argv)
    plot_vbal_groups(args.workspace, output_dir=args.output_dir, dpi=args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
