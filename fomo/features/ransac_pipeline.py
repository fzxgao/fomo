from __future__ import annotations
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional

Number = float
Coord = Tuple[Number, Number, Number]
FilSeg = Tuple[int, int]  # (filament_index, segment_index)

FLOAT_RE = re.compile(r'^([+-]?\d+(?:\.\d+)?)(?:[+\u2212-]\d+(?:\.\d+)?i)?$')

def _safe_float(token: str) -> float:
    """
    Convert tokens like '0', '-3.14', or '0+1.2e-6i' to a float (real part).
    """
    token = token.replace('\u2212', '-')  # fix unicode minus if present
    m = FLOAT_RE.match(token)
    if m:
        return float(m.group(1))
    # last resort
    try:
        return float(token)
    except Exception:
        # Dynamo tables sometimes sneak in exotic tokens — treat as 0.0
        return 0.0

def _normalize_coord(x: float, y: float, z: float, ndigits: int = 3) -> Coord:
    """
    Match the normalization you described: round to 3 decimals, strip trailing zeros
    (the 'strip' part is relevant when building string keys; here we keep as rounded floats).
    """
    return (round(x, ndigits), round(y, ndigits), round(z, ndigits))

def _parse_dynamo_tbl(tbl_path: Path) -> List[List[float]]:
    """
    Read a Dynamo-style .tbl (space-separated columns).
    Returns a list of rows as floats (real parts for any complex-looking tokens).
    """
    rows = []
    with tbl_path.open('r') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            parts = [p for p in line.split() if p]
            if not parts:
                continue
            rows.append([_safe_float(p) for p in parts])
    return rows

def _write_dynamo_tbl(rows: List[List[float]], out_path: Path) -> None:
    with out_path.open('w') as fh:
        for r in rows:
            # preserve a clean, space-separated format
            fh.write(' '.join(f'{v:g}' for v in r) + '\n')

def _scan_volume_raw_tbls(volume_dir: Path) -> Dict[Coord, FilSeg]:
    """
    For a single tomogram 'volume_*' directory, read all raw_###.tbl files.
    The index of the file (###) is the filament index. The row position (1-based)
    in that raw table is the segment index. We take original XYZ from cols 24..26
    (Dynamo convention you described).
    Returns mapping: normalized (x,y,z) -> (filament_index, segment_index).
    """
    mapping: Dict[Coord, FilSeg] = {}
    for raw_tbl in sorted(volume_dir.glob('raw_*.tbl')):
        # filament index from filename suffix
        m = re.search(r'raw_(\d+)\.tbl$', raw_tbl.name)
        if not m:
            continue
        filament_idx = int(m.group(1))
        rows = _parse_dynamo_tbl(raw_tbl)
        for seg_idx_0, row in enumerate(rows):
            if len(row) < 26:
                continue
            x, y, z = row[23], row[24], row[25]  # 24..26 in 1-based indexing
            key = _normalize_coord(x, y, z)
            # segment index should be 1-based
            mapping[key] = (filament_idx, seg_idx_0 + 1)
    return mapping

def _build_filament_segment_index(project_root: Path) -> Dict[Tuple[int, Coord], FilSeg]:
    """
    Walk all tomogram volumes and build a global mapping keyed by (tomo_idx, normXYZ) -> (fil, seg).
    The tomogram index is inferred from the directory name 'volume_<N>_*'.
    """
    tomos_root = project_root / 'fomo_dynamo_catalogue' / 'tomograms'
    global_map: Dict[Tuple[int, Coord], FilSeg] = {}
    for vol_dir in sorted(tomos_root.glob('volume_*')):
        # parse tomo index from 'volume_<N>_...' prefix
        m = re.match(r'volume_(\d+)_', vol_dir.name)
        if not m:
            continue
        tomo_idx = int(m.group(1))
        per_vol_map = _scan_volume_raw_tbls(vol_dir)
        for xyz, filseg in per_vol_map.items():
            global_map[(tomo_idx, xyz)] = filseg
    return global_map

def _write_indices_spi(order: List[Tuple[int, Coord]], mapping: Dict[Tuple[int, Coord], FilSeg], out_path: Path) -> None:
    """
    SPI indices file (non-fixed segments). Header + one line per subtomo:
    key nReg tomo filament segment
    First two integers are ignored by RANSAC, so we write zeros as requested.
    The order of entries MUST match the DOC order.
    """
    with out_path.open('w') as fh:
        fh.write('; tomogram/filament/segment indices for non-fixed segments (key and nReg are ignored)\n')
        for tomo_idx, norm_xyz in order:
            filseg = mapping.get((tomo_idx, norm_xyz))
            if filseg is None:
                raise KeyError(f'Could not find filament/segment for tomo={tomo_idx}, xyz={norm_xyz}')
            filament_idx, segment_idx = filseg
            fh.write(f'0 0 {tomo_idx} {filament_idx} {segment_idx}\n')

def _write_mltomo_doc(rows: List[List[float]],
                      filename_for_row,
                      out_path: Path) -> None:
    """
    Write an Xmipp MLTOMO DOC file with 12 values per entry line:
    key nReg  φ θ ψ  Xoff Yoff Zoff  Ref Wedge PmaxOverSumP LL
    The line with '; <filename>' precedes each entry.
    """
    with out_path.open('w') as fh:
        fh.write('; Headerinfo columns: rot (1), tilt (2), psi (3), Xoff (4), Yoff (5), Zoff (6), Ref (7), Wedge (8), Pmax/sumP (9), LL (10)\n')
        for i, row in enumerate(rows, start=1):
            # columns (1-based):
            # 4..6 = dx,dy,dz
            # 7..9 = tdrot,tilt,narot
            if len(row) < 9:
                raise ValueError('Row too short to contain Euler/shifts')
            dx, dy, dz = row[3], row[4], row[5]
            phi, theta, psi = row[6], row[7], row[8]
            # Compose entry
            fname = filename_for_row(i, row)
            fh.write(f'; {fname}\n')
            # key=i, nReg=10 (we provide 10 registers per line to mirror example doc)
            # extras: Ref, Wedge, Pmax/sumP, LL
            fh.write(f'{i:6d} 10  {phi:11.5f} {theta:11.5f} {psi:11.5f}  {dx:10.5f} {dy:10.5f} {dz:10.5f}  {1.0:8.5f} {1.0:8.5f} {1.0:10.5f} {0.0:12.5f}\n')

def _read_doc_euler_shifts(doc_path: Path) -> List[Tuple[float, float, float, float, float, float]]:
    """
    Read back the 6 values (φ,θ,ψ, Xoff,Yoff,Zoff) from a DOC file in the same order.
    """
    vals: List[Tuple[float, float, float, float, float, float]] = []
    with doc_path.open('r') as fh:
        for line in fh:
            line = line.rstrip('\n')
            if not line or line.lstrip().startswith(';'):
                continue
            # Expect: key nReg φ θ ψ X Y Z ...
            parts = [p for p in line.split() if p]
            if len(parts) < 8:
                continue
            # parts[0]=key, [1]=nReg
            phi, theta, psi = map(float, parts[2:5])
            X, Y, Z = map(float, parts[5:8])
            vals.append((phi, theta, psi, X, Y, Z))
    return vals

def _read_doc_with_filenames(doc_path: Path) -> List[Tuple[str, Tuple[float, float, float, float, float, float]]]:
    """Return list of (filename, (φ,θ,ψ,X,Y,Z)) tuples from a DOC file."""
    entries: List[Tuple[str, Tuple[float, float, float, float, float, float]]] = []
    current_name: Optional[str] = None
    with doc_path.open("r") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(";"):
                current_name = line[1:].strip()
                continue
            parts = [p for p in line.split() if p]
            if current_name and len(parts) >= 8:
                phi, theta, psi = map(float, parts[2:5])
                X, Y, Z = map(float, parts[5:8])
                entries.append((current_name, (phi, theta, psi, X, Y, Z)))
            current_name = None
    return entries

def _default_filename_for_row_factory(project_root: Path):
    """
    Provide a stable, human-readable filename to print after ';' in the DOC.
    If we can, point to the actual particle EM path (by tomo index + tag).
    Otherwise, synthesize a name.
    """
    tomos_root = project_root / 'fomo_dynamo_catalogue' / 'tomograms'
    # cache tomogram volume directories by index
    vol_dirs: Dict[int, Path] = {}
    for vol_dir in tomos_root.glob('volume_*'):
        m = re.match(r'volume_(\d+)_', vol_dir.name)
        if m:
            vol_dirs[int(m.group(1))] = vol_dir

    def filename_for_row(i: int, row: List[float]) -> str:
        # col 1 = tag, col 20 = tomo, cols 24..26 = original xyz
        tag = int(row[0]) if row and isinstance(row[0], (int, float)) else i
        tomo = int(row[19]) if len(row) >= 20 else 1
        if tomo in vol_dirs:
            # try to point to an actual particle EM file if it exists
            pdir_candidates = list(vol_dirs[tomo].glob('particles_*'))
            if pdir_candidates:
                em = pdir_candidates[0] / f'particle_{tag:06d}.em'
                return str(em)
        # fallback synthesized name
        return f'vol{tomo:03d}_particle_{tag:06d}.spi'
    return filename_for_row

def run_ransac_pipeline(
    project_root: Path,
    refined_tbl_path: Path,
    out_prefix: Path,
    ransac_bin: Optional[Path] = None,
    extra_ransac_args: Optional[List[str]] = ["-d", "6"],
) -> Tuple[Path, Path, Path, Path]:
    """
    End-to-end:
      1) read refined Dynamo table,
      2) build (tomo, xyz)->(fil,seg) map from raw_###.tbl files,
      3) write DOC and SPI,
      4) run RANSAC with -S (non-fixed segments),
      5) write updated ``*_RANSAC.tbl`` containing only inlier rows.

    Returns: (doc_in, spi_indices, doc_out, tbl_out)
    """
    out_prefix = Path(out_prefix)
    base_prefix = out_prefix.with_suffix("") if out_prefix.suffix else out_prefix
    base_prefix.parent.mkdir(parents=True, exist_ok=True)

    rows = _parse_dynamo_tbl(refined_tbl_path)

    # Build global mapping using your raw tables (filament inferred from raw_###.tbl name,
    # segment = row order within that raw table).
    global_map = _build_filament_segment_index(project_root)

    # Build the order list to emit SPI & DOC in the same order as the refined table:
    # normalized original xyz from cols 24..26, and tomo index from col 20.
    order: List[Tuple[int, Coord]] = []
    for r in rows:
        if len(r) < 26:
            raise ValueError('Refined table rows must contain original XYZ (cols 24..26).')
        tomo = int(r[19])
        xyz = _normalize_coord(r[23], r[24], r[25])
        order.append((tomo, xyz))

    # Write SPI indices
    spi_path = base_prefix.with_suffix('.indices.spi')
    _write_indices_spi(order, global_map, spi_path)

    # Write input DOC
    doc_in = base_prefix.with_suffix('.doc')
    filename_for_row = _default_filename_for_row_factory(project_root)
    _write_mltomo_doc(rows, filename_for_row, doc_in)

    # Run RANSAC (if executable provided or available on PATH)
    doc_out = base_prefix.with_name(base_prefix.name + '_RANSAC').with_suffix('.doc')
    log_path = base_prefix.with_name(base_prefix.name + '_RANSAC.log')

    if ransac_bin is None:
        # infer RANSAC binary relative to packaged tutorial doc
        tutorial_doc = Path(__file__).resolve().parent.parent / "RANSAC" / "tutorial" / "mltomo_bb1000.doc"
        ransac_bin = tutorial_doc.parent.parent / "bin" / "ransac"

    bin_dir = Path(ransac_bin).resolve().parent
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}{os.pathsep}" + env.get("PATH", "")

    cmd = [str(ransac_bin), '-v', '-l', str(log_path), '-S', str(spi_path)]
    if extra_ransac_args:
        cmd.extend(extra_ransac_args)
    cmd.extend([str(doc_in), str(doc_out)])

    try:
        subprocess.run(cmd, check=True, env=env)
    except FileNotFoundError:
        # Allow caller to run later; we still return paths
        print(f"[WARN] RANSAC executable not found: {cmd[0]}. Skipping execution.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"RANSAC failed with exit code {e.returncode}: {' '.join(cmd)}") from e

    # If we produced an output doc, read it and update the refined table columns
    if doc_out.exists():
        entries = _read_doc_with_filenames(doc_out)
        updated: List[List[float]] = []
        for fname, (phi, theta, psi, X, Y, Z) in entries:
            orig = fname_map.get(fname)
            if orig is None:
                continue
            r2 = list(orig)
            r2[3], r2[4], r2[5] = X, Y, Z
            r2[6], r2[7], r2[8] = phi, theta, psi
            updated.append(r2)
        tbl_out = base_prefix.with_name(base_prefix.name + '_RANSAC').with_suffix('.tbl')
        _write_dynamo_tbl(updated, tbl_out)
    else:
        tbl_out = out_prefix.with_name(out_prefix.name + '_pending').with_suffix('.tbl')
        tbl_out = base_prefix.with_name(base_prefix.name + '_RANSAC_pending').with_suffix('.tbl')
        # No changes because RANSAC wasn't run; write an untouched copy
        _write_dynamo_tbl(rows, tbl_out)

    return doc_in, spi_path, doc_out, tbl_out