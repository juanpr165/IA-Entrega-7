from app.hitl import is_critical_task
from app.graph import safe_calculate


def test_identifies_side_effect_as_critical() -> None:
    assert is_critical_task("Publicar el informe en producción") is True


def test_keeps_read_only_question_non_critical() -> None:
    assert is_critical_task("Calculá 20 * 4") is False


def test_safe_calculator_accepts_arithmetic_only() -> None:
    assert safe_calculate("(3 + 5) * 2") == 16
