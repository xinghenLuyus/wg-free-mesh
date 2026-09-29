"""CPS handshake preludes, not traffic encapsulation or complete sessions."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand


def packet_chain(direction: str, intensity: str) -> list[str | None]:
    count = {"low": 1, "balanced": 3, "high": 5}[intensity]
    if direction == "generic":
        packets = [f"<r {32 + secrets.randbelow(225)}>" for _ in range(count)]
    elif direction == "dns":
        packets = []
        for _ in range(count):
            length = 6 + secrets.randbelow(10)
            qtype = secrets.choice(("0001", "001c"))
            packets.append(f"<r 2><b 0x01000001000000000000{length:02x}><rc {length}><b 0x07696e76616c696400{qtype}0001>")
    elif direction == "stun":
        packets = []
        for _ in range(count):
            length = 4 * (1 + secrets.randbelow(4))
            # SOFTWARE is a padded UTF-8 attribute; transaction ID is runtime random.
            packets.append(f"<b 0x0001{length + 4:04x}2112a442><r 12><b 0x8022{length:04x}><rc {length}>")
    elif direction == "rtp":
        seq = secrets.randbelow(65536)
        timestamp = secrets.randbits(32)
        ssrc = secrets.randbits(32)
        packets = []
        for i in range(count):
            # RTP v2 / PCMU: correlated sequence, timestamp and SSRC within the draft.
            header = struct.pack("!BBHII", 0x80, 0, (seq + i) & 0xffff, (timestamp + 160 * i) & 0xffffffff, ssrc)
            packets.append(f"<b 0x{header.hex()}><r 160>")
    elif direction == "quic":
        # Each generation creates one authenticated 1200-byte v1 Initial.
        # Its ciphertext cannot contain CPS random tags without invalidating authentication.
        packets = [f"<b 0x{quic_initial().hex()}>"]
    else:
        raise ValueError("Unknown packet direction")
    return packets + [None] * (5 - len(packets))


def _u16(value: int) -> bytes:
    return value.to_bytes(2, "big")


def _varint(value: int) -> bytes:
    return bytes([value]) if value < 64 else _u16(value | 0x4000)


def _extension(kind: int, data: bytes) -> bytes:
    return _u16(kind) + _u16(len(data)) + data


def _expand(secret: bytes, label: bytes, length: int) -> bytes:
    label = b"tls13 " + label
    info = _u16(length) + bytes([len(label)]) + label + b"\0"
    return HKDFExpand(algorithm=hashes.SHA256(), length=length, info=info).derive(secret)


def quic_initial() -> bytes:
    """RFC 9001 packet protection. No connection is opened or TLS state retained."""
    dcid, scid = secrets.token_bytes(8), secrets.token_bytes(8)
    server_name = (secrets.token_hex(6) + ".invalid").encode()
    key_share = X25519PrivateKey.generate().public_key().public_bytes_raw()
    transport = b"\x0f" + _varint(len(scid)) + scid + b"\x03\x02" + _varint(1200)
    extensions = b"".join([
        _extension(0, _u16(len(server_name) + 3) + b"\0" + _u16(len(server_name)) + server_name),
        _extension(43, b"\x02\x03\x04"),
        _extension(10, b"\x00\x02\x00\x1d"),
        _extension(13, b"\x00\x04\x08\x04\x08\x07"),
        _extension(51, b"\x00\x24\x00\x1d\x00\x20" + key_share),
        _extension(16, b"\x00\x03\x02h3"),
        _extension(57, transport),
    ])
    hello = b"\x03\x03" + secrets.token_bytes(32) + b"\x00\x00\x02\x13\x01\x01\x00" + _u16(len(extensions)) + extensions
    hello = b"\x01" + len(hello).to_bytes(3, "big") + hello
    frame = b"\x06\x00" + _varint(len(hello)) + hello
    # Header ends with a 2-byte packet number (zero). AEAD tag is 16 bytes.
    prefix = b"\xc1\x00\x00\x00\x01\x08" + dcid + b"\x08" + scid + b"\x00"
    header_size = len(prefix) + 4
    plaintext = frame + bytes(1200 - header_size - 16 - len(frame))
    header = prefix + _varint(2 + len(plaintext) + 16) + b"\x00\x00"
    salt = bytes.fromhex("38762cf7f55934b34d179ae6a4c80cadccbb7f0a")
    initial = hmac.new(salt, dcid, hashlib.sha256).digest()
    client = _expand(initial, b"client in", 32)
    key, iv, hp = (_expand(client, label, length) for label, length in ((b"quic key", 16), (b"quic iv", 12), (b"quic hp", 16)))
    ciphertext = AESGCM(key).encrypt(iv, plaintext, header)
    encryptor = Cipher(algorithms.AES(hp), modes.ECB()).encryptor()
    mask = encryptor.update(ciphertext[2:18]) + encryptor.finalize()
    protected = bytearray(header)
    protected[0] ^= mask[0] & 0x0f
    protected[-2] ^= mask[1]
    protected[-1] ^= mask[2]
    return bytes(protected) + ciphertext
