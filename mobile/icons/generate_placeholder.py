"""Generate placeholder dark-grey PNG icons for the mobile PWA."""
import struct
import zlib
from pathlib import Path


def make_png(width: int, height: int, color: tuple[int, int, int] = (14, 17, 22)) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t: bytes, d: bytes) -> bytes:
        crc = zlib.crc32(t + d)
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(color) * width
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def main() -> None:
    out_dir = Path(__file__).resolve().parent
    for size in (192, 512):
        path = out_dir / f"icon-{size}.png"
        path.write_bytes(make_png(size, size))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
