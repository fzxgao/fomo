import os, sys, argparse
from PyQt5 import QtWidgets
from .viewer import TomoViewer
from .io.mrcio import list_mrcs
from .style import apply_dark_theme

def build_parser():
    p = argparse.ArgumentParser(description="Fast MRC viewer (fomo)")
    p.add_argument("path", help="MRC file or folder")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--scroll-base", type=int, default=4)
    p.add_argument("--scroll-threshold", type=float, default=2.0)
    p.add_argument("--scroll-mult", type=float, default=0.01)
    p.add_argument("--scroll-max-streak", type=int, default=4)
    return p

def main(argv=None):
    args = build_parser().parse_args(argv)
    path = os.path.abspath(args.path)
    if not list_mrcs(path):
        sys.exit("No MRC files found.")

    app = QtWidgets.QApplication(sys.argv)
    apply_dark_theme(app)
    w = TomoViewer(
        path,
        verbose=args.verbose,
        scroll_base=args.scroll_base,
        scroll_threshold=args.scroll_threshold,
        scroll_mult=args.scroll_mult,
        scroll_max_streak=args.scroll_max_streak,
    )
    w.resize(1250, 945)
    w.show()
    sys.exit(app.exec_())
