/**
 * Remote+ screen payload decoders.
 *
 * Port of the bit-level grammar from REMOTE_PLUS_PROTOCOL_SPEC.md (sections 7.4.1–7.4.3)
 * and tools/remote_plus_proto/screen_decode.py.
 *
 * Each decoder takes a hex string payload and returns a Uint8Array pixel buffer
 * (0=black, 255=white) plus dimensions.
 */

export interface DecodedScreen {
  width: number
  height: number
  pixels: Uint8Array // grayscale: 0 or 255 per pixel
}

const BLACK = 0
const WHITE = 255

function hexByte(hex: string, offset: number): number {
  return parseInt(hex.substring(offset, offset + 2), 16)
}

function* bitsMsb(byte: number): Generator<number> {
  for (let c = 7; c >= 0; c--) {
    yield (byte >> c) & 1
  }
}

// ── Orion / Cygnus RLE decoder ──

function decodeRle(
  hex: string,
  width: number,
  height: number,
  fast: boolean,
  cygnus: boolean,
): DecodedScreen {
  const total = width * height
  const pixels = new Uint8Array(total)
  let i = 0 // hex cursor (in chars, each byte = 2 chars)
  let s = 0 // mode byte
  let r = total - 1 // pixel write position (reverse)

  if (fast && hex.length >= 2) {
    s = hexByte(hex, i)
    i += 2
  }

  const colorOne = cygnus ? WHITE : BLACK
  const colorZero = cygnus ? BLACK : WHITE

  function idx(dst: number): number {
    if (!cygnus) return dst
    const m = dst % width
    return dst - m + width - m - 1
  }

  while (r >= 0 && i + 1 < hex.length) {
    const l = hexByte(hex, i)
    i += 2

    if (s === 0) {
      // Full frame mode
      if ((l === 0xff || l === 0x00) && i + 1 < hex.length) {
        const h = hexByte(hex, i)
        i += 2
        const run = 8 * h
        const color = l === 0xff ? colorOne : colorZero
        for (let j = 0; j < run && r >= 0; j++) {
          pixels[idx(r)] = color
          r--
        }
        continue
      }
      for (const bit of bitsMsb(l)) {
        if (r < 0) break
        pixels[idx(r)] = bit ? colorOne : colorZero
        r--
      }
    } else if (s === 1) {
      // Delta/update mode
      if (l === 0x00 && i + 1 < hex.length) {
        const h = hexByte(hex, i)
        i += 2
        if (h === 0) {
          for (const bit of bitsMsb(l)) {
            if (r < 0) break
            pixels[idx(r)] = bit ? colorOne : colorZero
            r--
          }
        } else {
          r -= 8 * h // skip
        }
        continue
      }
      for (const bit of bitsMsb(l)) {
        if (r < 0) break
        pixels[idx(r)] = bit ? colorOne : colorZero
        r--
      }
    } else {
      break
    }
  }

  return { width, height, pixels }
}

// ── Sirius bit-unpack decoder ──

function decodeSirius(hex: string): DecodedScreen {
  const width = 122
  const height = 32
  const total = width * height
  const pixels = new Uint8Array(total).fill(WHITE)
  let e = 0 // column
  let s = 0 // row

  for (let f = 0; f < total / 4 && f + 2 <= hex.length; f += 2) {
    const l = hexByte(hex, f)
    for (let c = 0; c < 8; c++) {
      const pos = e + s * width
      if (pos >= total) return { width, height, pixels }
      const bit = (l >> c) & 1
      pixels[pos] = bit ? BLACK : WHITE
      s++
      if (s >= height) {
        s = 0
        e++
      }
    }
  }

  return { width, height, pixels }
}

// ── Public API ──

export type DeviceFamily = 'orion' | 'cygnus' | 'sirius'

export function decodeScreen(
  family: DeviceFamily,
  hex: string,
  fast: boolean = true,
): DecodedScreen {
  switch (family) {
    case 'orion':
      return decodeRle(hex, 240, 128, fast, false)
    case 'cygnus':
      return decodeRle(hex, 128, 64, fast, true)
    case 'sirius':
      return decodeSirius(hex)
    default:
      throw new Error(`Unknown device family: ${family}`)
  }
}

/**
 * Render decoded screen pixels onto a canvas 2D context.
 * Scales up by `scale` factor for visibility.
 */
export function renderToCanvas(
  ctx: CanvasRenderingContext2D,
  screen: DecodedScreen,
  scale: number = 2,
): void {
  const { width, height, pixels } = screen
  const imageData = ctx.createImageData(width, height)
  for (let i = 0; i < pixels.length; i++) {
    const v = pixels[i]
    const off = i * 4
    imageData.data[off] = v     // R
    imageData.data[off + 1] = v // G
    imageData.data[off + 2] = v // B
    imageData.data[off + 3] = 255 // A
  }

  // Use a temporary canvas for scaling
  if (scale === 1) {
    ctx.putImageData(imageData, 0, 0)
  } else {
    const tmp = document.createElement('canvas')
    tmp.width = width
    tmp.height = height
    const tmpCtx = tmp.getContext('2d')!
    tmpCtx.putImageData(imageData, 0, 0)
    ctx.imageSmoothingEnabled = false
    ctx.drawImage(tmp, 0, 0, width * scale, height * scale)
  }
}
