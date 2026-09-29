from backend.app.customs.history_repository import ValidatedCaseMemory


def test_empty_history_stats_are_stable(tmp_path):
    memory = ValidatedCaseMemory(tmp_path)
    stats = memory.stats()
    assert stats["cases"] == 0
    assert stats["files"] == []
    assert len(stats["sha256"]) == 64
