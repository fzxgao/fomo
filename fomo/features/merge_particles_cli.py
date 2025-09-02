from pathlib import Path

from .merge_particles import merge_crop_tables_and_particles


def main() -> None:
    merge_crop_tables_and_particles(Path.cwd())


if __name__ == "__main__":
    main()

