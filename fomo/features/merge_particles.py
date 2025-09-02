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

    # Clean previous merged particles; keep existing merged_crop.tbl until we
    # finish writing a new one to avoid temporary zero counts in the UI.
    for em in merged_dir.glob("particle_*.em"):
        try:
            em.unlink()
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
        # Write to a temp file in the same directory, then atomically replace
        # the final file so the GUI never sees an empty table mid-merge.
        tmp_path = merged_dir / "merged_crop.tbl.tmp"
        final_path = merged_dir / "merged_crop.tbl"
        try:
            tmp_path.write_text("\n".join(merged_lines) + "\n")
            # Atomic on POSIX and effectively atomic on modern Windows
            tmp_path.replace(final_path)
        except Exception:
            # Best effort: if replace fails, try to clean the temp
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
