from backend.app.normalization.text import display_hs_code, normalize_hs_code


def test_hs_code_preserves_leading_zero():
    assert normalize_hs_code("010121.00.000") == "01012100000"
    assert display_hs_code("01012100000") == "010121.00.000"


def test_hs_code_accepts_compact():
    assert normalize_hs_code("84414000000") == "84414000000"
