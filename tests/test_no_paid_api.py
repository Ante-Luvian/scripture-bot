"""No test may reach a paid API (the owner saw 20 cents go to tests that bought horoscope readings)."""
import os


def test_the_key_is_gone_in_tests():
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_stress_runs_drop_it_too(monkeypatch):
    import stress
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-not-a-real-key")
    stress.isolate_runtime_files()
    assert "ANTHROPIC_API_KEY" not in os.environ
