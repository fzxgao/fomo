import os


def list_mrcs(path: str):
    """Return sorted list of MRC-like files for *path*.

    Searches case-insensitively for ``.mrc``, ``.rec`` and ``.mrcs`` files in
    the provided directory.  If *path* points to a file, all matching files in
    its directory are returned and the file itself is included when present.
    """

    path = os.path.abspath(path)

    def _scan(directory: str):
        files = []
        try:
            for entry in os.scandir(directory):
                if entry.is_file():
                    name = entry.name.lower()
                    if name.endswith((".mrc", ".rec", ".mrcs")):
                        files.append(os.path.join(directory, entry.name))
        except FileNotFoundError:
            return []
        return sorted(files)

    if os.path.isdir(path):
        return _scan(path)
    else:
        directory = os.path.dirname(path) or "."
        files = _scan(directory)
        if os.path.exists(path) and path not in files:
            files.append(path)
            files.sort()
        return files
