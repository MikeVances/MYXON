/**
 * Device family key maps — from REMOTE_PLUS_PROTOCOL_SPEC.md section 14.
 *
 * Maps UI button labels to protocol-level key codes for each device family.
 */

export interface KeyDef {
  label: string
  code: number
  group: 'nav' | 'func' | 'num' | 'misc'
}

export const ORION_KEYS: KeyDef[] = [
  // Navigation
  { label: '▲', code: 19, group: 'nav' },
  { label: '▶', code: 18, group: 'nav' },
  { label: '▼', code: 20, group: 'nav' },
  { label: '◀', code: 17, group: 'nav' },
  { label: 'OK', code: 21, group: 'nav' },
  // Function
  { label: 'F1', code: 64, group: 'func' },
  { label: 'F2', code: 65, group: 'func' },
  { label: 'F3', code: 66, group: 'func' },
  { label: 'F4', code: 67, group: 'func' },
  { label: 'F5', code: 68, group: 'func' },
  { label: 'F6', code: 69, group: 'func' },
  // Numeric
  { label: '0', code: 48, group: 'num' },
  { label: '1', code: 49, group: 'num' },
  { label: '2', code: 50, group: 'num' },
  { label: '3', code: 51, group: 'num' },
  { label: '4', code: 52, group: 'num' },
  { label: '5', code: 53, group: 'num' },
  { label: '6', code: 54, group: 'num' },
  { label: '7', code: 55, group: 'num' },
  { label: '8', code: 56, group: 'num' },
  { label: '9', code: 57, group: 'num' },
  // Misc
  { label: '±', code: 22, group: 'misc' },
  { label: '.', code: 46, group: 'misc' },
  { label: 'Prev', code: 80, group: 'misc' },
  { label: 'Next', code: 81, group: 'misc' },
]

export const CYGNUS_KEYS: KeyDef[] = [
  { label: '▲', code: 19, group: 'nav' },
  { label: '▶', code: 18, group: 'nav' },
  { label: '▼', code: 20, group: 'nav' },
  { label: '◀', code: 17, group: 'nav' },
  { label: 'OK', code: 21, group: 'nav' },
  { label: 'F1', code: 64, group: 'func' },
  { label: 'F2', code: 65, group: 'func' },
  { label: 'F3', code: 66, group: 'func' },
  { label: 'F4', code: 67, group: 'func' },
]

export const SIRIUS_KEYS: KeyDef[] = [
  { label: '▲', code: 1, group: 'nav' },
  { label: '▶', code: 3, group: 'nav' },
  { label: '▼', code: 2, group: 'nav' },
  { label: 'OK', code: 4, group: 'nav' },
  { label: 'K1', code: 16, group: 'func' },
  { label: 'K2', code: 17, group: 'func' },
  { label: 'K3', code: 18, group: 'func' },
  { label: 'K4', code: 19, group: 'func' },
  { label: 'K5', code: 20, group: 'func' },
  { label: 'K6', code: 21, group: 'func' },
  { label: 'K7', code: 22, group: 'func' },
  { label: 'K8', code: 23, group: 'func' },
  { label: 'K9', code: 24, group: 'func' },
  { label: 'K10', code: 25, group: 'func' },
]

export function getKeysForFamily(family: string): KeyDef[] {
  switch (family.toLowerCase()) {
    case 'orion': return ORION_KEYS
    case 'cygnus': return CYGNUS_KEYS
    case 'sirius': return SIRIUS_KEYS
    default: return []
  }
}
