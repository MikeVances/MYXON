"""
HOTRACO / SyslinQ / Remote+ vendor adapter.

Implements the Remote+ binary TCP protocol for HMI control of
industrial controllers (Orion, Cygnus, Sirius families).

Protocol source: reverse-engineered from Remote+ 1.2.0 Android app
and SyslinQ Remote 1.3.0 (see REMOTE_PLUS_PROTOCOL_SPEC.md).

Transport: TCP socket (default port 5843)
Framing: ASCII hex frames  @DEST SRC CMD SUB BLOCK LEN DATA CRC*\\r
Auth: SHA-1 hashed password in authData payload
Mediation: ComputersRequest(4091) -> MediateRequest(4092)
Runtime: ConfigurationRead(2) -> CaptureScreenFast(96) -> SendKey(93)
"""
