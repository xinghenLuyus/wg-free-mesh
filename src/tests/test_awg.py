from app.domain import awg


def test_random_node_params_include_complete_i_chain() -> None:
    values = awg.random_node_params()

    assert 4 <= values["awg_jc"] <= 10
    assert 64 <= values["awg_jmin"] < values["awg_jmax"] <= 1024
    for key in ("awg_i1", "awg_i2", "awg_i3", "awg_i4", "awg_i5"):
        assert isinstance(values[key], str)
        assert values[key]
