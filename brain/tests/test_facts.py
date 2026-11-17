import pytest

from sapo.facts import arithmetic, verified


@pytest.mark.parametrize(
    "text,expected",
    [
        ("cuanto es 17 por 23?", "17 × 23 = 391"),
        ("cuánto es 17x23", "17 × 23 = 391"),
        ("2 + 2 * 3", "2 + 2 × 3 = 8"),
        ("(2 + 2) * 3", "(2 + 2) × 3 = 12"),
        ("cuanto es 100 entre 8", "100 ÷ 8 = 12,5"),
        ("1500 menos 320 mas 20", "1500 − 320 + 20 = 1 200"),
        ("2 elevado a 10", "2 ^ 10 = 1 024"),
        ("cuanto es el 15% de 200", "15 % de 200 = 30"),
        ("raiz cuadrada de 144", "√144 = 12"),
        ("12 al cuadrado", "12² = 144"),
        ("3,5 por 2", "3,5 × 2 = 7"),
        ("-5 + 3", "− 5 + 3 = -2"),
    ],
)
def test_arithmetic(text, expected):
    assert arithmetic(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "hola sapo",
        "son las 10:30",
        "mi cumple es el 12/05/2008",
        "tengo 3 gatos",
        "cuanto es 5 entre 0",
        "pasame 2 por favor",
        "recomiendame una peli de terror",
    ],
)
def test_not_arithmetic(text):
    assert arithmetic(text) is None


def test_verified_note():
    note = verified("oye cuanto es 17 por 23")
    assert note is not None and "391" in note
    assert verified("que onda") is None
