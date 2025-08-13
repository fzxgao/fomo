import os
import glob
import math
import numpy as np
import mrcfile

def list_mrcs(path):
    """List MRC/REC/MRCS files in the same dir as path (or in path if dir)."""
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.mrc")) +
                       glob.glob(os.path.join(path, "*.rec")) +
                       glob.glob(os.path.join(path, "*.mrcs")))
        return files
    else:
        d = os.path.dirname(path) or "."
        files = sorted(glob.glob(os.path.join(d, "*.mrc")) +
                       glob.glob(os.path.join(d, "*.rec")) +
                       glob.glob(os.path.join(d, "*.mrcs")))
        if path not in files and os.path.exists(path):
            files.append(path)
            files = sorted(files)
        return files

def fast_header_stats(mrc, data, fallback_max_voxels=2_000_000):
    """Use header amin/amax/amean if valid, else subsample quickly."""
    amin = getattr(mrc.header, "amin", None)
    amax = getattr(mrc.header, "amax", None)
    amean = getattr(mrc.header, "amean", None)
    try:
        if amin is not None and amax is not None:
            amin = float(amin); amax = float(amax)
            if np.isfinite(amin) and np.isfinite(amax) and amax > amin:
                mean = float(amean) if amean is not None and np.isfinite(amean) else 0.5*(amin+amax)
                return amin, amax, mean
    except Exception:
        pass
    Z, Y, X = data.shape
    total = Z*Y*X
    if total <= fallback_max_voxels:
        sample = np.asarray(data, dtype=np.float32).ravel()
    else:
        stride = int(math.ceil(total / fallback_max_voxels))
        sample = np.asarray(data.ravel()[::stride], dtype=np.float32)
    smin = float(np.min(sample))
    smax = float(np.max(sample))
    smean = float(np.mean(sample))
    return smin, smax, smean
