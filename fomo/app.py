# fomo/app.py
import os
import sys
import argparse
from PyQt5 import QtWidgets
from .viewer import TomoViewer
from .utils import list_mrcs


def main():
    parser = argparse.ArgumentParser(description="Fast MRC viewer (fomo)")
    parser.add_argument("path", help="MRC file or folder")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose tracing to stdout")
    parser.add_argument("--scroll-base", type=int, default=4,
                        help="Base slices per notch (default: 4)")
    parser.add_argument("--scroll-threshold", type=float, default=2.0,
                        help="Seconds between wheel events to count as fast (default: 2.0)")
    parser.add_argument("--scroll-mult", type=float, default=0.01,
                        help="Per-streak multiplier (default: 0.01)")
    parser.add_argument("--scroll-max-streak", type=int, default=4,
                        help="Max streak growth steps (default: 4)")
    args = parser.parse_args()

    verbose = args.verbose or os.environ.get("FOMO_VERBOSE", "") not in ("", "0", "false", "False")

    path = os.path.abspath(args.path)
    files = list_mrcs(path)
    if not files:
        sys.exit("No MRC files found.")

    app = QtWidgets.QApplication(sys.argv)
    w = TomoViewer(
        path,
        verbose=verbose,
        scroll_base=args.scroll_base,
        scroll_threshold=args.scroll_threshold,
        scroll_mult=args.scroll_mult,
        scroll_max_streak=args.scroll_max_streak,
    )
    w.resize(800, 850)
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
