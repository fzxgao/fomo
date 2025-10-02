import re
from pathlib import Path

import numpy as np
from emfile import write as write_em


def _write_em(volume: np.ndarray, path: Path) -> None:
    """Write a 3D numpy array to EM format.

    The ``emfile`` package handles writing the appropriate 512 byte header
    (including dimensions and data type) followed by the raw ``float32``
    volume data.
    """
    volume = np.asarray(volume, dtype=np.float32)
    write_em(path, volume, overwrite=True)


def extract_particles_on_exit(viewer, tomo_idx: int = None) -> None:
    """Extract particle subvolumes when leaving picking mode.

    Parameters
    ----------
    viewer : Viewer
        The main viewer instance that contains the loaded tomogram and
        picking panel parameters.
    """
    panel = getattr(viewer, "picking_panel", None)
    if panel is None:
        return
    box_size = int(getattr(panel.box_size, "value", lambda: 40)())

    # Tomogram index to operate on
    idx = viewer.idx if tomo_idx is None else int(tomo_idx)
    tomogram_path = Path(viewer.files[idx])
    tomogram_name = tomogram_path.stem

    root_dir = Path.cwd() / "fomo_dynamo_catalogue" / "tomograms"
    volume_dir = None
    tomogram_number = None
    for d in root_dir.iterdir():
        if d.is_dir() and d.name.endswith(tomogram_name):
            m = re.match(r"^volume_(\d+)_", d.name)
            if m:
                tomogram_number = int(m.group(1))
                volume_dir = d
                break
    if volume_dir is None or tomogram_number is None:
        return

    particles_dir = volume_dir / f"particles_volume_{tomogram_number}_{tomogram_name}"
    particles_dir.mkdir(parents=True, exist_ok=True)

    crop_path = particles_dir / "crop.tbl"

    # Load existing crop table (if any) keyed by all columns except the index
    existing = {}
    max_idx = 0
    if crop_path.exists():
        with crop_path.open() as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                cols = line.split()
                entry_idx = int(cols[0])
                key = " ".join(cols[1:])
                existing[key] = (entry_idx, line)
                max_idx = max(max_idx, entry_idx)

    # Safety: ensure tomogram index is valid and fetch volume
    if not (0 <= idx < len(getattr(viewer, "mrc_handles", []))):
        return
    volume = viewer.mrc_handles[idx].data  # (Z, Y, X)
    half = box_size // 2

    seen = set()
    new_entries = {}

    # Search recursively for raw.tbl files produced for each model
    # and merge all coordinates that fall within the tomogram bounds.
    for tbl in sorted(volume_dir.rglob("raw*.tbl")):
        with tbl.open() as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                cols = line.split()
                try:
                    x = float(cols[23])
                    y = float(cols[24])
                    z = float(cols[25])
                except (IndexError, ValueError):
                    continue
                xmin = int(round(x)) - half
                xmax = xmin + box_size
                ymin = int(round(y)) - half
                ymax = ymin + box_size
                zmin = int(round(z)) - half
                zmax = zmin + box_size
                if (
                    xmin < 0
                    or ymin < 0
                    or zmin < 0
                    or xmax > volume.shape[2]
                    or ymax > volume.shape[1]
                    or zmax > volume.shape[0]
                ):
                    print(f"{line} THIS LINE WAS SKIPPED DUE TO OUT OF BOUNDS")
                    continue

                key = " ".join(cols[1:])
                if key in existing:
                    # Coordinate already extracted
                    seen.add(key)
                    continue

                subvol = volume[zmin:zmax, ymin:ymax, xmin:xmax]
                max_idx += 1
                _write_em(subvol, particles_dir / f"particle_{max_idx:06d}.em")
                cols[0] = str(max_idx)
                new_entries[key] = (max_idx, " ".join(cols))
                seen.add(key)

    # Remove particles that are no longer present
    for key, (entry_idx, _) in list(existing.items()):
        if key not in seen:
            try:
                (particles_dir / f"particle_{entry_idx:06d}.em").unlink()
            except Exception:
                pass
            del existing[key]

    existing.update(new_entries)

    # Renumber sequentially to keep indices contiguous
    sorted_items = sorted(existing.values(), key=lambda x: x[0])
    lines = []
    for new_idx, (old_idx, line) in enumerate(sorted_items, start=1):
        if old_idx != new_idx:
            old_path = particles_dir / f"particle_{old_idx:06d}.em"
            new_path = particles_dir / f"particle_{new_idx:06d}.em"
            try:
                old_path.rename(new_path)
            except Exception:
                pass
            cols = line.split()
            cols[0] = str(new_idx)
            line = " ".join(cols)
        lines.append(line)

    if lines:
        with crop_path.open("w") as out:
            for l in lines:
                out.write(l + "\n")
    else:
        try:
            crop_path.unlink()
        except Exception:
            pass


def extract_particles_from_subboxed_csv(
    viewer,
    tomo_idx: int = None,
    pattern: str = "subboxed_xyz_*.csv",
) -> None:
    """Extract particles from ``subboxed*.csv`` files and write a Dynamo crop table.

    This mirrors the logic of :func:`extract_particles_on_exit`, but instead of
    reading ``raw_*.tbl`` files it parses ``subboxed*.csv`` files containing
    ``x,y,z,x,y,z,phi,tilt,psi`` per row (nine comma-separated values).

    It crops subvolumes from the loaded tomogram into the corresponding
    ``particles_*`` folder and creates/updates a ``crop.tbl`` that can be used by
    ``daverage`` and ``dcp``.
    """
    panel = getattr(viewer, "picking_panel", None)
    if panel is None:
        return
    box_size = int(getattr(panel.box_size, "value", lambda: 40)())

    # Tomogram index to operate on
    idx = viewer.idx if tomo_idx is None else int(tomo_idx)
    tomogram_path = Path(viewer.files[idx])
    tomogram_name = tomogram_path.stem

    root_dir = Path.cwd() / "fomo_dynamo_catalogue" / "tomograms"
    volume_dir = None
    tomogram_number = None
    for d in root_dir.iterdir():
        if d.is_dir() and d.name.endswith(tomogram_name):
            m = re.match(r"^volume_(\d+)_", d.name)
            if m:
                tomogram_number = int(m.group(1))
                volume_dir = d
                break
    if volume_dir is None or tomogram_number is None:
        return

    particles_dir = volume_dir / f"particles_volume_{tomogram_number}_{tomogram_name}"
    particles_dir.mkdir(parents=True, exist_ok=True)

    crop_path = particles_dir / "crop.tbl"

    # Load existing crop table (if any) keyed by all columns except the index
    existing = {}
    max_idx = 0
    if crop_path.exists():
        with crop_path.open() as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                cols = line.split()
                entry_idx = int(cols[0])
                key = " ".join(cols[1:])
                existing[key] = (entry_idx, line)
                max_idx = max(max_idx, entry_idx)

    # Safety: ensure tomogram index is valid and fetch volume
    if not (0 <= idx < len(getattr(viewer, "mrc_handles", []))):
        return
    volume = viewer.mrc_handles[idx].data  # (Z, Y, X)
    half = box_size // 2

    # Try to find a raw tbl line to use as a template for column layout
    template_cols = None
    for tbl in sorted(volume_dir.glob("raw_*.tbl")):
        try:
            with tbl.open() as fh:
                first = fh.readline().strip()
            cols = first.split()
            if len(cols) >= 35:
                template_cols = cols
                break
        except Exception:
            pass

    # Fallback minimal template (35 columns) if no raw table is available
    if template_cols is None:
        template_cols = [
            "0",  # 1: index (will be overwritten)
            "1",  # 2
            "1",  # 3
            "0", "0", "0",  # 4-6: placeholder
            "0", "0", "0",  # 7-9: phi, tilt, psi (overwritten)
            "0", "0", "0",  # 10-12
            "1",              # 13
            "-60", "60", "-60", "60",  # 14-17
            "0", "0",       # 18-19
            str(tomogram_number),  # 20: tomogram number
            "0", "0", "0",  # 21-23
            "0", "0", "0",  # 24-26: x,y,z (overwritten)
            "0", "0", "0",  # 27-29
            "0", "0", "1",  # 30-32
            "0", "0", "0",  # 33-35
        ]

    seen = set()
    new_entries = {}

    # Iterate through all matching CSV files
    for csv_path in sorted(volume_dir.glob(pattern)):
        with csv_path.open() as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                parts = [p.strip() for p in raw.split(",")]
                if len(parts) < 9:
                    continue
                try:
                    # CSV format: x,y,z, x,y,z, phi, tilt, psi
                    x = float(parts[0])
                    y = float(parts[1])
                    z = float(parts[2])
                    phi = float(parts[6])
                    tilt = float(parts[7])
                    psi = float(parts[8])
                except ValueError:
                    continue

                xmin = int(round(x)) - half
                xmax = xmin + box_size
                ymin = int(round(y)) - half
                ymax = ymin + box_size
                zmin = int(round(z)) - half
                zmax = zmin + box_size
                if (
                    xmin < 0
                    or ymin < 0
                    or zmin < 0
                    or xmax > volume.shape[2]
                    or ymax > volume.shape[1]
                    or zmax > volume.shape[0]
                ):
                    print(f"{raw} THIS LINE WAS SKIPPED DUE TO OUT OF BOUNDS")
                    continue

                cols = list(template_cols)  # shallow copy
                # Update angles (1-based positions 7-9 => 0-based 6-8)
                cols[6] = f"{phi:g}"
                cols[7] = f"{tilt:g}"
                cols[8] = f"{psi:g}"
                # Update coordinates (1-based positions 24-26 => 0-based 23-25)
                cols[23] = f"{x:g}"
                cols[24] = f"{y:g}"
                cols[25] = f"{z:g}"

                key = " ".join(cols[1:])
                if key in existing:
                    seen.add(key)
                    continue

                subvol = volume[zmin:zmax, ymin:ymax, xmin:xmax]
                max_idx += 1
                _write_em(subvol, particles_dir / f"particle_{max_idx:06d}.em")
                cols[0] = str(max_idx)
                line = " ".join(cols)
                new_entries[key] = (max_idx, line)
                seen.add(key)

    # Remove particles that are no longer present
    for key, (entry_idx, _) in list(existing.items()):
        if key not in seen:
            try:
                (particles_dir / f"particle_{entry_idx:06d}.em").unlink()
            except Exception:
                pass
            del existing[key]

    existing.update(new_entries)

    # Renumber sequentially to keep indices contiguous
    sorted_items = sorted(existing.values(), key=lambda x: x[0])
    lines = []
    for new_idx, (old_idx, line) in enumerate(sorted_items, start=1):
        if old_idx != new_idx:
            old_path = particles_dir / f"particle_{old_idx:06d}.em"
            new_path = particles_dir / f"particle_{new_idx:06d}.em"
            try:
                old_path.rename(new_path)
            except Exception:
                pass
            cols = line.split()
            cols[0] = str(new_idx)
            line = " ".join(cols)
        lines.append(line)

    if lines:
        with crop_path.open("w") as out:
            for l in lines:
                out.write(l + "\n")
    else:
        try:
            crop_path.unlink()
        except Exception:
            pass
