from pathlib import Path
import shutil
from typing import List


def merge_crop_tables_and_particles(root: Path) -> None:
    """Merge per-tomogram particle stacks and crop tables.

    Parameters
    ----------
    root : Path
        Project root containing ``fomo_dynamo_catalogue``.
    """
    catalogue = root / "fomo_dynamo_catalogue" / "tomograms"
    if not catalogue.exists():
        return

    merged_dir = catalogue / "merged"
    merged_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous merged particles and table
    for em in merged_dir.glob("particle_*.em"):
        try:
            em.unlink()
        except Exception:
            pass
    try:
        (merged_dir / "merged_crop.tbl").unlink()
    except Exception:
        pass

    next_idx = 1
    merged_lines: List[str] = []

    for vol_dir in sorted(catalogue.glob("volume_*")):
        # locate particles directory inside each volume
        for particles_dir in vol_dir.glob("particles_*"):
            crop_tbl = particles_dir / "crop.tbl"
            if not crop_tbl.exists():
                continue
            try:
                lines = crop_tbl.read_text().splitlines()
            except Exception:
                continue
            for line in lines:
                if not line.strip():
                    continue
                cols = line.split()
                try:
                    old_idx = int(cols[0])
                except (IndexError, ValueError):
                    continue
                src_em = particles_dir / f"particle_{old_idx:06d}.em"
                if not src_em.exists():
                    continue
                dst_em = merged_dir / f"particle_{next_idx:06d}.em"
                try:
                    shutil.copy2(src_em, dst_em)
                except Exception:
                    continue
                cols[0] = str(next_idx)
                merged_lines.append(" ".join(cols))
                next_idx += 1

    if merged_lines:
        try:
            (merged_dir / "merged_crop.tbl").write_text("\n".join(merged_lines) + "\n")
        except Exception:
            pass