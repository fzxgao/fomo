import numpy as np
from pathlib import Path
from typing import Tuple


def _normalize_coord(val: float) -> float:
    """Round and strip insignificant zeros from a coordinate value."""
    val = round(float(val), 3)
    if abs(val) < 1e-6:
        return 0.0
    if abs(val - round(val)) < 1e-6:
        return float(int(round(val)))
    return val

def import_refined_coordinates(input_dir: str, verbose: bool = False) -> Tuple[Path, Path]:
    """Parse a Dynamo catalogue and generate refined coordinate CSV files.

    Parameters
    ----------
    input_dir : str
        Path to the ``fomo_dynamo_catalogue`` directory.

    Returns
    -------
    Tuple[Path, Path]
        ``(path_to_tomograms, path_to_refined_tbl)``
    """
    root = Path(input_dir)
    path_to_tomograms = root / "tomograms"

    alignments_root = root / "alignments"
    alignment_dirs = [d for d in alignments_root.iterdir() if d.is_dir()]
    if not alignment_dirs:
        raise FileNotFoundError("No alignments directory found")

    def _dt_key(p: Path) -> str:
        parts = p.name.split("_", 2)
        return parts[0] + parts[1]

    latest_alignment = max(alignment_dirs, key=_dt_key)

    results_dir = latest_alignment / "results"
    ite_dirs = [d for d in results_dir.glob("ite_*") if (d / "averages").is_dir()]
    if not ite_dirs:
        raise FileNotFoundError("No iteration directories with averages found")

    def _ite_key(p: Path) -> int:
        try:
            return int(p.name.split("_")[-1])
        except Exception:
            return -1

    latest_ite = max(ite_dirs, key=_ite_key)
    averages_dir = latest_ite / "averages"
    refined_tables = list(averages_dir.glob("refined_table_ref_*_ite_*.tbl"))
    if not refined_tables:
        raise FileNotFoundError("No refined_table_ref_*.tbl file found")

    path_to_refined_tbl = refined_tables[0]

    # ``np.loadtxt`` fails if the table contains complex numbers in unused
    # columns (e.g. ``0+1.2074e-06i``).  Parse the file manually and only
    # convert the columns we care about.
    tomos = []
    xyz = []
    shifts = []
    eulers = []
    with open(path_to_refined_tbl) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            try:
                dx, dy, dz = map(float, parts[3:6])
                tdrot, tilt, narot = map(float, parts[6:9])
                tomo = int(float(parts[19]))
                x, y, z = map(float, parts[23:26])
            except (ValueError, IndexError):
                # Skip malformed rows rather than failing the entire import
                continue
            tomos.append(tomo)
            xyz.append((x, y, z))
            shifts.append((dx, dy, dz))
            eulers.append((tdrot, tilt, narot))

    tomo_numbers = np.array(tomos, dtype=int)
    xyz = np.array(xyz, dtype=float)
    if verbose:
        print(f"XYZ is ", xyz)
        for axiscoord in xyz:
            print(f"Axis coord: {axiscoord}")
    shifts = np.array(shifts, dtype=float)
    eulers = np.array(eulers, dtype=float)
    mod_xyz = xyz + shifts

    for tomo in np.unique(tomo_numbers):
        volume_dir = None
        for d in path_to_tomograms.iterdir():
            if d.is_dir() and d.name.startswith(f"volume_{tomo}_"):
                volume_dir = d
                break
        if volume_dir is None:
            continue
        idx = np.where(tomo_numbers == tomo)[0]
        vol_rows = np.hstack((xyz[idx], mod_xyz[idx], eulers[idx]))
        out_csv = volume_dir / f"refined_volume_{tomo}_xyz_abg.csv"
        np.savetxt(out_csv, vol_rows, fmt="%.6f", delimiter=",")

        # Map original coords to filament numbers using nested lookups
        mapping = {}
        for xyz_file in volume_dir.glob("xyz_*.csv"):
            filament = xyz_file.stem.split("_")[-1]
            if verbose:
                print(f"[refined] scanning {xyz_file}")
            try:
                pts = np.loadtxt(xyz_file, delimiter=",")
            except Exception:
                # Some xyz files are whitespace-delimited; fall back gracefully
                pts = np.loadtxt(xyz_file)
            pts = np.atleast_2d(pts)[:, :3]
            for p in pts:
                x_key, y_key, z_key = (_normalize_coord(c) for c in p)
                mapping.setdefault(x_key, {}).setdefault(y_key, {})[z_key] = filament

        per_filament = {}
        for i in idx:
            x_key, y_key, z_key = (_normalize_coord(c) for c in xyz[i])
            filament = (
                mapping.get(x_key, {})
                .get(y_key, {})
                .get(z_key)
            )
            if filament is None:
                if verbose:
                    print(f"[refined] no match for {(x_key, y_key, z_key)}")
                continue
            if verbose:
                print(
                    f"[refined] matched {(x_key, y_key, z_key)} to filament {filament}"
                )
            per_filament.setdefault(filament, []).append(
                np.concatenate((xyz[i], mod_xyz[i], eulers[i]))
            )
        for filament, rows in per_filament.items():
            out = volume_dir / f"refined_xyz_{filament}.csv"
            np.savetxt(out, np.array(rows), fmt="%.6f", delimiter=",")

    return path_to_tomograms, path_to_refined_tbl


def euler_to_vector(tdrot: float, tilt: float, narot: float) -> np.ndarray:
    """Return orientation vector of the new z-axis for given Euler angles."""
    rtd = np.deg2rad(tdrot)
    rtilt = np.deg2rad(tilt)
    rnar = np.deg2rad(narot)
    rz1 = np.array([[np.cos(rtd), -np.sin(rtd), 0],
                    [np.sin(rtd),  np.cos(rtd), 0],
                    [0,            0,           1]])
    rx = np.array([[1, 0, 0],
                   [0, np.cos(rtilt), -np.sin(rtilt)],
                   [0, np.sin(rtilt),  np.cos(rtilt)]])
    rz2 = np.array([[np.cos(rnar), -np.sin(rnar), 0],
                    [np.sin(rnar),  np.cos(rnar), 0],
                    [0,            0,           1]])
    R = rz2 @ rx @ rz1
    vec = R @ np.array([0.0, 0.0, 1.0])
    return vec