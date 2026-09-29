import hashlib
import hmac
import re
import struct

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.domain import awg
from app.domain.awg_signatures import _expand, packet_chain, quic_initial


def _materialize(cps: str) -> bytes:
    result = b""
    for kind, data in re.findall(r"<(b|r|rc) ([^>]+)>", cps):
        result += bytes.fromhex(data[2:]) if kind == "b" else (b"a" if kind == "rc" else b"\x01") * int(data)
    return result


@pytest.mark.parametrize("direction", ["generic", "dns", "stun", "rtp", "quic"])
def test_packet_chains_are_supported_cps_with_bounded_sizes(direction) -> None:
    for cps in packet_chain(direction, "high"):
        if cps:
            awg._validate_cps(cps)
            assert 0 < len(_materialize(cps)) <= 1200


def test_dns_query_lengths_and_counts() -> None:
    for cps in packet_chain("dns", "high"):
        packet = _materialize(cps)
        assert packet[2:12] == bytes.fromhex("01000001000000000000")
        offset = 12
        while packet[offset]:
            offset += 1 + packet[offset]
        assert len(packet) == offset + 5
        assert packet[-2:] == b"\x00\x01"


def test_stun_attribute_lengths_match_header() -> None:
    for cps in packet_chain("stun", "high"):
        packet = _materialize(cps)
        assert packet[:2] == b"\x00\x01"
        assert packet[4:8] == bytes.fromhex("2112a442")
        assert int.from_bytes(packet[2:4], "big") == len(packet) - 20
        assert packet[20:22] == bytes.fromhex("8022")
        assert int.from_bytes(packet[22:24], "big") == len(packet) - 24


def test_rtp_chain_has_correlated_headers() -> None:
    packets = [_materialize(cps) for cps in packet_chain("rtp", "high")]
    headers = [struct.unpack("!BBHII", packet[:12]) for packet in packets]
    first = headers[0]
    for i, header in enumerate(headers):
        assert header == (0x80, 0, (first[2] + i) & 65535, (first[3] + 160 * i) & 0xffffffff, first[4])
        assert len(packets[i]) == 172


def test_quic_hkdf_matches_rfc9001_appendix_a1() -> None:
    salt = bytes.fromhex("38762cf7f55934b34d179ae6a4c80cadccbb7f0a")
    initial = hmac.new(salt, bytes.fromhex("8394c8f03e515708"), hashlib.sha256).digest()
    client = _expand(initial, b"client in", 32)
    assert _expand(client, b"quic key", 16).hex() == "1f369613dd76d5467730efcbe3b1a22d"
    assert _expand(client, b"quic iv", 12).hex() == "fa044b2f42a3fd3b46fb255c"
    assert _expand(client, b"quic hp", 16).hex() == "9f50449e04a0e810283a1e9933adedd2"


def test_quic_initial_authenticates_and_contains_client_hello() -> None:
    packet = quic_initial()
    assert len(packet) == 1200
    assert packet[1:6] == b"\x00\x00\x00\x01\x08"
    dcid = packet[6:14]
    pn_offset = 26
    salt = bytes.fromhex("38762cf7f55934b34d179ae6a4c80cadccbb7f0a")
    client = _expand(hmac.new(salt, dcid, hashlib.sha256).digest(), b"client in", 32)
    cipher = Cipher(algorithms.AES(_expand(client, b"quic hp", 16)), modes.ECB()).encryptor()
    mask = cipher.update(packet[pn_offset + 4:pn_offset + 20]) + cipher.finalize()
    header = bytearray(packet[:pn_offset + 2])
    header[0] ^= mask[0] & 15
    header[-2] ^= mask[1]
    header[-1] ^= mask[2]
    assert header[0] == 0xc1 and header[-2:] == b"\x00\x00"
    assert (int.from_bytes(header[24:26], "big") & 0x3fff) == len(packet) - pn_offset
    plaintext = AESGCM(_expand(client, b"quic key", 16)).decrypt(_expand(client, b"quic iv", 12), packet[len(header):], bytes(header))
    assert plaintext[:2] == b"\x06\x00"  # CRYPTO frame at offset zero.
    hello_length = int.from_bytes(plaintext[2:4], "big") & 0x3fff
    hello = plaintext[4:4 + hello_length]
    assert hello[:1] == b"\x01"
    assert int.from_bytes(hello[1:4], "big") == len(hello) - 4
    assert hello[4:6] == b"\x03\x03"
    assert all(value == 0 for value in plaintext[4 + hello_length:])
