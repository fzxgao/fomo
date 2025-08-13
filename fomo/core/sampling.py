import math
import numpy as np

def subsampled_histogram(memmap_arr, bins=256, max_voxels=2_000_000):
    """Sample up to max_voxels from arr for histogram."""
    Z, Y, X = memmap_arr.shape
    total = Z * Y * X
    if total <= max_voxels:
        vals = memmap_arr.ravel()
    else:
        stride = int(math.ceil(total / max_voxels))
        vals = memmap_arr.ravel()[::stride]
    vals = vals.astype(np.float32)
    hist, edges = np.histogram(vals, bins=bins)
    return hist, edges
