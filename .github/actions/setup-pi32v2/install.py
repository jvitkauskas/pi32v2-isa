# SPDX-FileCopyrightText: 2026 Julius Vitkauskas
# SPDX-License-Identifier: MIT-0
"""Check a pi32v2-llvm package against SHA256SUMS and unpack it so that DEST is its top directory.

    install.py PACKAGE SHA256SUMS DEST
"""
import hashlib
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

package, sums, dest = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
want = None
for line in sums.read_text().splitlines():
    digest, _, name = line.strip().partition(" ")
    if name.lstrip(" *") == package.name:
        want = digest
if want is None:
    sys.exit(f"{package.name} is not in {sums.name}")
h = hashlib.sha256()
with package.open("rb") as f:
    for block in iter(lambda: f.read(1 << 20), b""):
        h.update(block)
if h.hexdigest() != want:
    sys.exit(f"{package.name}: SHA-256 {h.hexdigest()}, SHA256SUMS says {want}")
print(f"{package.name}: SHA-256 matches SHA256SUMS")

dest.parent.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(dir=dest.parent) as tmp:
    if package.suffix == ".zip":
        with zipfile.ZipFile(package) as z:
            z.extractall(tmp)
    else:
        with tarfile.open(package) as t:
            if hasattr(tarfile, "data_filter"):
                t.extractall(tmp, filter="data")
            else:
                t.extractall(tmp)
    (top,) = Path(tmp).iterdir()
    if dest.exists():
        shutil.rmtree(dest)
    shutil.move(str(top), str(dest))
print(f"installed in {dest}")
