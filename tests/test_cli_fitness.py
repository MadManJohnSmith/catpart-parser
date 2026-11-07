"""Seam 2 (A1 scope): the ``catpart-fitness`` console script stub.

The fitness runner lands with ticket #14; until then the stub must say
so loudly and never pretend success.
"""

from __future__ import annotations


def run_fitness(capsys) -> tuple[int, str, str]:
    from catpart.cli import main_fitness

    code = main_fitness([])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_fitness_stub_says_not_implemented(capsys) -> None:
    code, out, err = run_fitness(capsys)
    assert code == 2
    assert out == ""
    assert "not implemented yet" in err
    assert "catpart-fitness" in err
