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


def extract_particles_on_exit(viewer) -> None:
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

    tomogram_path = Path(viewer.files[viewer.idx])
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
                idx = int(cols[0])
                key = " ".join(cols[1:])
                existing[key] = (idx, line)
                max_idx = max(max_idx, idx)

    volume = viewer.mrc_handles[viewer.idx].data  # (Z, Y, X)
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
    for key, (idx, _) in list(existing.items()):
        if key not in seen:
            try:
                (particles_dir / f"particle_{idx:06d}.em").unlink()
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
