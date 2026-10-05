from types import SimpleNamespace

from backend.app.main import health


def test_health_is_non_blocking_while_runtime_initializes():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                services=None,
                startup_status={
                    "status": "initializing",
                    "phase": "Référentiel CAMCIS / index sémantique",
                    "error": None,
                },
            )
        )
    )

    payload = health(request)
    assert payload["status"] == "initializing"
    assert payload["semantic_index"]["status"] == "INITIALIZING"
    assert payload["camcis"]["records"] == 0
    assert payload["startup"]["phase"]


def test_health_exposes_controlled_startup_error_without_raising():
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                services=None,
                startup_status={
                    "status": "error",
                    "phase": "Initialisation interrompue",
                    "error": "synthetic failure",
                },
            )
        )
    )

    payload = health(request)
    assert payload["status"] == "error"
    assert payload["startup"]["error"] == "synthetic failure"
