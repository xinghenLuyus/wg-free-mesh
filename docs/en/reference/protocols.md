# Protocol Parameters

WG Free Mesh supports WireGuard and AmneziaWG. Select AWG 1.5, 2.0, or 3.1 separately when creating or editing a config; the whole Mesh uses the same version. See [AWG Protocol Compatibility](/en/help/awg-compatibility) for toolchain requirements.

## WireGuard

WireGuard does not use additional AWG parameters.

Generated configs use:

- `[Interface]`
- `[Peer]`
- `PrivateKey`
- `Address`
- `ListenPort`
- `MTU`
- `DNS`
- `AllowedIPs`
- `Endpoint`
- `PersistentKeepalive`
- `PresharedKey`

## AmneziaWG

The AmneziaWG toolchain follows WireGuard conventions with an `a` prefix:

- `wg` -> `awg`
- `wg-quick` -> `awg-quick`

Windows uses `amneziawg.exe` instead of `wireguard.exe`.

## Config-level AWG Parameters

Config-level parameters are shared by the entire Mesh.

| Field | Description | Rule |
| --- | --- | --- |
| `awg_s1` | Random prefix length for Init packets | `0..65535` |
| `awg_s2` | Random prefix length for Response packets | `0..65535` |
| `awg_s3` | Random prefix length for Cookie packets | `0..65535` |
| `awg_s4` | Random prefix length for Data packets | `0..65535` |
| `awg_h1` | Dynamic Init header range | A `uint32` value or `start-end` |
| `awg_h2` | Dynamic Response header range | A `uint32` value or `start-end` |
| `awg_h3` | Dynamic Cookie header range | A `uint32` value or `start-end` |
| `awg_h4` | Dynamic Data header range | A `uint32` value or `start-end` |

The `H1..H4` ranges must not overlap.

1.5 emits only S1/S2; S3/S4 must be zero. H1–H4 must be fixed values, and S1 + 56 must differ from S2. 2.0 and 3.1 support all S fields and H ranges.

Config extension fields live in `awg_options`. In 3.1, `header_protection_key` maps to `HeaderProtectionKey`: a nonzero 32-byte Base64 key. Explicit `null` disables it. Enabling it requires S1–S4 to be at least 12.

Shared `random_trailers` is an `on/off` switch and requires equal S1–S4 when enabled. Saving the shared switch aligns all endpoints; the same endpoint option applies when no shared value is set.

## Endpoint-level AWG Parameters

Endpoint-level parameters may differ for each endpoint.

| Field | Description | Rule |
| --- | --- | --- |
| `awg_jc` | Junk packet count | `0..65535` |
| `awg_jmin` | Minimum junk length | `0..65535` |
| `awg_jmax` | Maximum junk length | `0..65535` and greater than `Jmin` |
| `awg_i1..awg_i5` | CPS decoy-packet chain | Text expression |

New endpoints and first-time AWG switches fill missing parameters. Ordinary saves allow clearing them without random refilling.

Endpoint extension fields also live in `awg_options`:

| Version | Fields | Rules |
| --- | --- | --- |
| 1.5 | `j1`, `j2`, `j3` | CPS expressions, emitted as J1–J3. |
| 1.5 | `itime` | `uint32`, emitted as Itime. |
| 3.1 | `content_padding_addition`, `rekey_after_time`, `rekey_timeout`, `reject_after_time`, `keepalive_timeout`, `max_handshake_attempts` | Fixed values or `start-end` within `0..65535`. The nonzero lower bound of RejectAfterTime must exceed the nonzero upper bound of RekeyAfterTime. |
| 3.1 | `disable_cookies` | Boolean, emitted as `on/off` and preserved during generation. |

Emitted names use toolchain CamelCase, such as `RekeyAfterTime`. Empty values are omitted. Stored options unused by the selected version remain stored but are not emitted; adding or changing unsupported options is rejected.

## Randomization Strategy

Unified generation selects `generic/dns/stun/rtp/quic` direction and `low/balanced/high` intensity. Stored config options `_random_direction/_random_intensity` affect only explicit generation and new endpoint initialization, never override saved concrete values.

| Intensity | S random upper bound | Jc | Jmin | Jmax upper bound | I packet count (except QUIC) |
| --- | --- | --- | --- | --- | --- |
| low | 24 | 1–3 | 64–255 | 256 | 1 |
| balanced | 48 | 4–7 | 64–256 | 768 | 3 |
| high | 96 | 8–10 | 64–256 | 1024 | 5 |

S starts at zero, or 12 with 3.1 HP enabled. 3.1 generates equal S1–S4; 1.5 keeps S3/S4 zero. H uses randomly generated nonoverlapping uint32 ranges (2.0) or fixed values (1.5/3.1). Jmax exceeds Jmin. Each endpoint independently uses the system secure random source for J/I and applicable padding/timing or J1–J3/Itime parameters; accidental equal values remain possible.

QUIC generates one 1200-byte Initial. Other directions generate structured handshake preludes; unused I fields are empty. Generation preserves configured HP keys and mechanism switches. Every applicable field is editable; suggested ranges are not manual limits. Assess large packets and aggressive timing against your actual network. See [AWG Protocol Compatibility](/en/help/awg-compatibility) for direction limitations.
