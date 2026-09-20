"""Zip mobile dist folder."""
import zipfile, os, sys, pathlib, shutil

src = pathlib.Path("mobile/dist")
dst = pathlib.Path("dist/mobile-dist.zip")

dst.parent.mkdir(exist_ok=True)
if dst.exists():
    dst.unlink()

total = sum(1 for _ in src.rglob("*") if _.is_file())
written = 0

with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            arcname = str(f.relative_to(src))
            zf.write(f, arcname)
            written += 1
            if written % 5 == 0:
                print(f"\r  {written}/{total} files", end="", flush=True)

print(f"\n  wrote {written} files to {dst} ({dst.stat().st_size:,} bytes)")
