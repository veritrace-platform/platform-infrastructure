import json
from pathlib import Path

from veritrace_simulator.gs1 import check_digit, valid_sscc

# A copy of veritrace/docs/contracts/test-vectors/gs1-check-digit.json.
VECTORS = json.loads((Path(__file__).parent / "testdata" / "gs1-check-digit.json").read_text(encoding="utf-8"))


def test_check_digit_vectors():
    for vector in VECTORS["valid"]:
        key = vector["key"]
        assert check_digit(key[:-1]) == int(key[-1]), key


def test_valid_sscc_vectors():
    sscc = [v for v in VECTORS["valid"] if v["type"] == "SSCC"]
    assert sscc
    for vector in sscc:
        assert valid_sscc(vector["key"]), vector


def test_wrong_check_digits():
    for vector in VECTORS["valid"]:
        if vector["type"] == "SSCC":
            key = vector["key"]
            wrong = str((int(key[-1]) + 1) % 10)
            assert not valid_sscc(key[:-1] + wrong), key


def test_other_keys_are_not_ssccs():
    for key in ["", "08930001000018", "0893000100000000180", "08930001000000001٨"]:
        assert not valid_sscc(key)
