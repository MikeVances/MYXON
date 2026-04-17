from __future__ import annotations


BLACK = 0
WHITE = 255


def _bits_msb(byte: int):
    for c in range(7, -1, -1):
        yield 1 if ((byte >> c) & 1) else 0


def decode_orion(screen_hex: str, fast: bool) -> tuple[int, int, list[int]]:
    return _decode_rle(screen_hex, width=240, height=128, fast=fast, cygnus=False)


def decode_cygnus(screen_hex: str, fast: bool) -> tuple[int, int, list[int]]:
    return _decode_rle(screen_hex, width=128, height=64, fast=fast, cygnus=True)


def _decode_rle(screen_hex: str, width: int, height: int, fast: bool, cygnus: bool) -> tuple[int, int, list[int]]:
    i = 0
    s = 0
    total = width * height
    pixels = [0] * total
    r = total - 1
    if fast and len(screen_hex) >= 2:
        s = int(screen_hex[i : i + 2], 16)
        i += 2

    def idx(dst: int) -> int:
        if not cygnus:
            return dst
        m = dst % width
        return dst - m + width - m - 1

    color_one = WHITE if cygnus else BLACK
    color_zero = BLACK if cygnus else WHITE

    while r >= 0 and i + 1 < len(screen_hex):
        l = int(screen_hex[i : i + 2], 16)
        i += 2
        if s == 0:
            if l in (0xFF, 0x00) and i + 1 < len(screen_hex):
                h = int(screen_hex[i : i + 2], 16)
                i += 2
                run = 8 * h
                color = color_one if l == 0xFF else color_zero
                for _ in range(run):
                    if r < 0:
                        break
                    pixels[idx(r)] = color
                    r -= 1
                continue
            for bit in _bits_msb(l):
                if r < 0:
                    break
                pixels[idx(r)] = color_one if bit else color_zero
                r -= 1
        elif s == 1:
            if l == 0x00 and i + 1 < len(screen_hex):
                h = int(screen_hex[i : i + 2], 16)
                i += 2
                if h == 0:
                    for bit in _bits_msb(l):
                        if r < 0:
                            break
                        if bit:
                            pixels[idx(r)] = color_one
                        else:
                            pixels[idx(r)] = color_zero
                        r -= 1
                else:
                    r -= 8 * h
                continue
            for bit in _bits_msb(l):
                if r < 0:
                    break
                pixels[idx(r)] = color_one if bit else color_zero
                r -= 1
        else:
            break
    return width, height, pixels


def decode_sirius(screen_hex: str) -> tuple[int, int, list[int]]:
    width = 122
    height = 32
    total = width * height
    pixels = [WHITE] * total
    e = 0
    s = 0
    # Matches app logic: iterate bytes and write 8 bits each
    for f in range(0, total // 4, 2):
        if f + 2 > len(screen_hex):
            break
        l = int(screen_hex[f : f + 2], 16)
        for c in range(8):
            pos = e + s * width
            if pos >= total:
                return width, height, pixels
            bit = 1 if ((l >> c) & 1) else 0
            pixels[pos] = BLACK if bit else WHITE
            s += 1
            if s >= height:
                s = 0
                e += 1
    return width, height, pixels


def write_pgm(path: str, width: int, height: int, pixels: list[int]) -> None:
    with open(path, "wb") as f:
        f.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
        f.write(bytes(pixels))

