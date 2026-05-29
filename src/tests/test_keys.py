from app.domain.models import derive_public_key, generate_key_pair


def test_derive_public_key_uses_x25519_wireguard_vector() -> None:
    private_key = "dwdtCnMYpX08FsFyUbJmRd9ML4frwJkqsXf7pR25LCo="
    public_key = "hSDwCYkwp1R0i33ctD73Wg2/Og0mOBr066SpjqqbTmo="

    assert derive_public_key(private_key) == public_key


def test_generate_key_pair_returns_matching_public_key() -> None:
    private_key, public_key = generate_key_pair()

    assert derive_public_key(private_key) == public_key
