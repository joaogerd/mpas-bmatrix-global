from __future__ import annotations

from pathlib import Path

from .forecast import restart_file
from .shell import require_file, symlink_force, write_text


def pair_dir(config, valid_time):
    return Path(config["project"]["work_root"]) / "nmc_pairs" / f"nmc_{config['mesh']['name']}_valid_{valid_time.replace(':', '.')}"


def prepare_pair(config, old_init_time, new_init_time, valid_time, dt=None):
    dt = int(dt or config["runtime"]["config_dt"])
    f048 = restart_file(config, old_init_time, 48, dt)
    f024 = restart_file(config, new_init_time, 24, dt)
    require_file(f048, "forecast antigo f048")
    require_file(f024, "forecast novo f024")

    out = pair_dir(config, valid_time)
    out.mkdir(parents=True, exist_ok=True)
    symlink_force(f048, out / "f048.nc")
    symlink_force(f024, out / "f024.nc")

    env = f'''MESH_NAME={config["mesh"]["name"]}
CONFIG_DT={dt}
OLD_INIT_TIME={old_init_time}
NEW_INIT_TIME={new_init_time}
VALID_TIME={valid_time}
F048={out / "f048.nc"}
F024={out / "f024.nc"}
'''
    write_text(out / "pair.env", env)
    write_text(out / "README.md", f'''# Par NMC

- `f048.nc`: forecast antigo, iniciado em `{old_init_time}`
- `f024.nc`: forecast novo, iniciado em `{new_init_time}`
- horário válido comum: `{valid_time}`

Diferença NMC esperada: `f048 - f024`.
''')
    print(f"OK: par NMC montado: {out}")
    return out
