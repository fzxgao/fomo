import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from typing import Iterable
import numpy as np
import pexpect

# NumPy 1.24. Define it here for compatibility with newer versions *before*
# importing ``eulerangles`` so it can access the alias during module import.
if not hasattr(np, "float"):
    np.float = float
    
from eulerangles import convert_eulers

def _get_param(root: ET.Element, section: str, name: str, cast=float):
    """Helper to fetch numeric parameters from Warp settings XML."""
    node = root.find(f"./{section}/Param[@Name='{name}']")
    if node is None:
        raise KeyError(f"Missing parameter {name} in section {section}")
    return cast(node.get("Value"))


def _parse_warp_settings(settings: Path):
    """Return (pixel_size, dim_x, dim_z) from ``warp_tiltseries.settings``."""
    tree = ET.parse(settings)
    root = tree.getroot()
    raw_px = _get_param(root, "Import", "PixelSize", float)
    dim_x = _get_param(root, "Tomo", "DimensionsX", int)
    dim_z = _get_param(root, "Tomo", "DimensionsZ", int)
    return raw_px, dim_x, dim_z


def _iter_tomogram_dirs(root: Path) -> Iterable[Path]:
    tomo_root = root / "fomo_dynamo_catalogue" / "tomograms"
    if not tomo_root.is_dir():
        return []
    return [d for d in tomo_root.iterdir() if d.is_dir() and d.name.startswith("volume_")]


def export_relion_clean_stars(root_dir: Path | str = Path.cwd(), *, verbose: bool = False) -> None:
    """Generate ``*_clean.star`` files for all refined coordinates.

    Parameters
    ----------
    root_dir:
        Root directory containing ``fomo_dynamo_catalogue`` and
        ``warp_tiltseries.settings``.
    verbose:
        Emit progress information.
    """
    root_dir = Path(root_dir)
    settings_path = root_dir / "warp_tiltseries.settings"
    raw_px, raw_dim_x, raw_dim_z = _parse_warp_settings(settings_path)

    out_dir = root_dir / "warp_tiltseries" / "matching"
    out_dir.mkdir(parents=True, exist_ok=True)

    for tomo_dir in _iter_tomogram_dirs(root_dir):
        # parse tomogram name and pixel size from directory name
        name_part = "_".join(tomo_dir.name.split("_", 2)[2:])
        m = re.search(r"([0-9.]+)Apx", name_part)
        if not m:
            if verbose:
                print(f"[relion] could not determine pixel size for {tomo_dir.name}")
            continue
        tomo_px = float(m.group(1))
        scale = tomo_px / raw_px
        tomo_dim_xy = int(round(raw_dim_x / scale))
        tomo_dim_z = int(round(raw_dim_z / scale))

        # choose refined csv files (RANSAC preferred)
        csvs = sorted(tomo_dir.glob("refined_xyz_*.csv"))
        ransac_csvs = sorted(tomo_dir.glob("refined_RANSAC_xyz_*.csv"))
        if ransac_csvs:
            csvs = ransac_csvs
        rows: list[str] = []
        for csv in csvs:
            try:
                data = np.loadtxt(csv, delimiter=",", ndmin=2)
            except Exception:
                if verbose:
                    print(f"[relion] failed to read {csv}")
                continue
            if data.size == 0:
                continue
            coords = data[:, 3:6]  # refined coordinates
            eulers = data[:, 6:9]
            eulers = convert_eulers(eulers, source_meta="dynamo", target_meta="relion")
            norm_x = coords[:, 0] / tomo_dim_xy
            norm_y = coords[:, 1] / tomo_dim_xy
            norm_z = coords[:, 2] / tomo_dim_z
            for i in range(len(coords)):
                rows.append(
                    f" {norm_x[i]:.8f} {norm_y[i]:.8f} {norm_z[i]:.8f} "
                    f"{eulers[i,0]:.6f} {eulers[i,1]:.6f} {eulers[i,2]:.6f}"
                )
        if not rows:
            if verbose:
                print(f"[relion] no refined coordinates found for {tomo_dir.name}")
            continue
        micrograph_base = re.sub(r"_[0-9.]+Apx$", "", name_part)
        micrograph = f"{micrograph_base}.tomostar"
        star_path = out_dir / f"{name_part}_clean.star"
        with open(star_path, "w") as fh:
            fh.write("data_\n\nloop_\n")
            fh.write("\n".join([
                "_rlnCoordinateX #1",
                "_rlnCoordinateY #2",
                "_rlnCoordinateZ #3",
                "_rlnAngleRot #4",
                "_rlnAngleTilt #5",
                "_rlnAnglePsi #6",
                "_rlnMicrographName #7",
                "_rlnAutopickFigureOfMerit #8",
            ]) + "\n")
            for r in rows:
                fh.write(f"{r} {micrograph} 10\n")
        if verbose:
            print(f"[relion] wrote {star_path} ({len(rows)} particles)")

def export_relion(
    root_dir: Path | str = Path.cwd(),
    *,
    output_angpix: float = 4.0,
    warpbox: int = 128,
    warp_diameter: int = 220,
    verbose: bool = False,
) -> None:
    """Run WarpTools to export particles for RELION.
    This function creates ``*_clean.star`` files and then calls
    ``WarpTools ts_export_particles`` to generate ``matching.star`` and the
    corresponding particle stacks.
    """

    root = Path(root_dir)

    # Create *_clean.star files from refined coordinates
    export_relion_clean_stars(root, verbose=verbose)
    
    # Find WarpTools executable in common conda/mamba locations
    roots = ["micromamba", "mamba", "anaconda3", "miniconda3", ".local/share/micromamba"]
    warp_executable = "WarpTools"
    try:
        for env_root in roots:
            exe = Path.home() / env_root / "envs" / "warp" / "bin" / "WarpTools"
            if exe.exists():
                warp_executable = str(exe)
                break
    except FileNotFoundError:
        print(
            f"WarpTools not found in micromamba/mamba/conda/miniconda envs, assuming WarpTools is installed in the fomo environment. If not, please install Warp using your preferred python package and environment manager and try again."
        )
    # Ensure output directory exists
    (root / "relion").mkdir(parents=True, exist_ok=True)
    print(f"WarpTools executable: {warp_executable}")
    cmd = [
        warp_executable,
        "ts_export_particles",
        "--settings",
        "warp_tiltseries.settings",
        "--input_directory",
        "warp_tiltseries/matching",
        "--input_pattern",
        "*_clean.star",
        "--normalized_coords",
        "--output_star",
        "relion/matching.star",
        "--output_angpix",
        str(output_angpix),
        "--box",
        str(warpbox),
        "--diameter",
        str(warp_diameter),
        "--relative_output_paths",
        "--2d",
    ]

    child = pexpect.spawn(cmd[0], cmd[1:], cwd=str(root), encoding="utf-8")
    child.logfile = sys.stdout
    child.expect(pexpect.EOF, timeout=None)
    rc = child.wait()
    if rc:
        raise subprocess.CalledProcessError(rc, " ".join(cmd))

    if verbose:
       print("[relion] ran WarpTools ts_export_particles")
