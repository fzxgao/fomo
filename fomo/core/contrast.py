import numpy as np

def apply_contrast(arr, minv, maxv):
    """Apply linear contrast scaling to array -> uint8 grayscale."""
    arr8 = np.clip((arr - minv) / (maxv - minv), 0, 1)
    return (arr8 * 255).astype(np.uint8, copy=False)
