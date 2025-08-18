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
    # Clean any existing particles/crop file so indices remain consistent
    if particles_dir.exists():
        for em in particles_dir.glob("particle_*.em"):
            try:
                em.unlink()
            except Exception:
                pass
        try:
            (particles_dir / "crop.tbl").unlink()
        except Exception:
            pass
    particles_dir.mkdir(parents=True, exist_ok=True)

    volume = viewer.mrc_handles[viewer.idx].data  # (Z, Y, X)
    half = box_size // 2
    particle_idx = 1
    merged_lines = []

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
                subvol = volume[zmin:zmax, ymin:ymax, xmin:xmax]
                _write_em(subvol, particles_dir / f"particle_{particle_idx:06d}.em")
                # Renumber first column sequentially across merged files
                cols[0] = str(particle_idx)
                merged_lines.append(" ".join(cols))
                particle_idx += 1

    if merged_lines:
        with (particles_dir / "crop.tbl").open("w") as out:
            for l in merged_lines:
                out.write(l + "\n")
