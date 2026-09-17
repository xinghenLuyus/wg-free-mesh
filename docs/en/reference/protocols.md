# Protocol Parameters

WG Free Mesh supports WireGuard and AmneziaWG 2.0. Select the protocol when creating a config or from the config settings page.

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

## AmneziaWG 2.0

The AmneziaWG toolchain follows WireGuard conventions with an `a` prefix:

- `wg` -> `awg`
- `wg-quick` -> `awg-quick`

Windows uses `amneziawg.exe` instead of `wireguard.exe`.

## Config-level AWG Parameters

Config-level parameters are shared by the entire Mesh.

| Field | Description | Rule |
| --- | --- | --- |
| `awg_s1` | Random prefix length for Init packets | `0..64` |
| `awg_s2` | Random prefix length for Response packets | `0..64` |
| `awg_s3` | Random prefix length for Cookie packets | `0..64` |
| `awg_s4` | Random prefix length for Data packets | `0..32` |
| `awg_h1` | Dynamic Init header range | A `uint32` value or `start-end` |
| `awg_h2` | Dynamic Response header range | A `uint32` value or `start-end` |
| `awg_h3` | Dynamic Cookie header range | A `uint32` value or `start-end` |
| `awg_h4` | Dynamic Data header range | A `uint32` value or `start-end` |

The `H1..H4` ranges must not overlap.

## Endpoint-level AWG Parameters

Endpoint-level parameters may differ for each endpoint.

| Field | Description | Rule |
| --- | --- | --- |
| `awg_jc` | Junk packet count | `0..10` |
| `awg_jmin` | Minimum junk length | `64..1024` |
| `awg_jmax` | Maximum junk length | `64..1024` and greater than `Jmin` |
| `awg_i1..awg_i5` | CPS decoy-packet chain | Text expression |

The backend generates random values when these fields are empty.

## Randomization Strategy

Backend-generated values use:

- `S1..S3`: `15..64`
- `S4`: `0..32`
- `H1..H4`: random, non-overlapping ranges within `1024..4294967295`
- `Jc`: `4..10`
- `Jmin`: `64..256`
- `Jmax`: greater than `Jmin`, up to `1024`
- `I1..I5`: DNS-like, STUN-like, or QUIC-like templates
