"""SSCC validation (docs/domain/gs1-identifiers.md), so the simulator never publishes readings that the
ingestion service rejects for their SSCC."""

SSCC_LENGTH = 18


def check_digit(payload: str) -> int:
    """Return the GS1 Modulo 10 check digit of a key without its check digit."""
    total = 0
    weight = 3
    for digit in reversed(payload):
        total += int(digit) * weight
        weight = 4 - weight
    return (10 - total % 10) % 10


def valid_sscc(sscc: str) -> bool:
    """Report whether sscc has 18 ASCII digits and a correct check digit."""
    if len(sscc) != SSCC_LENGTH or not sscc.isascii() or not sscc.isdigit():
        return False
    return check_digit(sscc[:-1]) == int(sscc[-1])
