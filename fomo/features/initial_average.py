"""Initial average calculation utilities."""

import random
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def calculate_initial_average(box_size: int) -> Tuple[Optional[subprocess.Popen], Optional[Path]]:
    """Run Dynamo to compute an initial average from up to 500 particles.

    Parameters
    ----------
    box_size : int
        Box size used to determine the alignment directory.

    Returns
    -------
    Tuple[Optional[subprocess.Popen], Optional[Path]]
        The spawned process handle and the output EM file path. If any
        preparation step fails, ``(None, None)`` is returned.
    """
    avg_dir = (
        Path.cwd()
        / "fomo_dynamo_catalogue"
        / "tomograms"
        / "alignments"
        / "average_reference"
        / str(box_size)
    )
    avg_dir.mkdir(parents=True, exist_ok=True)

    merged_dir = Path.cwd() / "fomo_dynamo_catalogue" / "tomograms" / "merged"
    merged_tbl = merged_dir / "merged_crop.tbl"
    subset_tbl = merged_dir / "subset_500_merged_crop.tbl"

    tbl_to_use = merged_tbl
    try:
        with merged_tbl.open() as fh:
            lines = fh.readlines()
        if len(lines) >= 500:
            selected = random.sample(lines, 500)
            with subset_tbl.open("w") as out:
                out.writelines(selected)
            tbl_to_use = subset_tbl
    except Exception:
        return None, None

    dest_em = avg_dir / "rawTemplate.em"
    setup = Path(__file__).resolve().parent.parent / "dynamo_setup_EDITME.sh"
    cmd = [
        "bash",
        str(setup),
        "-s",
        (
            f"oa=daverage('fomo_dynamo_catalogue/tomograms/merged','t','{tbl_to_use.as_posix()}');"
            f"dwrite(oa.average,'{dest_em.as_posix()}');"
        ),
    ]
    try:
        proc = subprocess.Popen(cmd)
    except Exception:
        return None, None

    return proc, dest_em
