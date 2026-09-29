from backend.app.evaluation.benchmark import compute_ranking_metrics


def test_compute_ranking_metrics():
    expected = ["A", "B", "C", "D"]
    rankings = [
        ["A", "X", "Y"],
        ["X", "B", "Y"],
        ["X", "Y", "C"],
        ["X", "Y", "Z"],
    ]
    m = compute_ranking_metrics(expected, rankings)
    assert m["top1_accuracy"] == 0.25
    assert m["top3_recall"] == 0.75
    assert m["top5_recall"] == 0.75
    assert round(m["mrr"], 6) == round((1 + 1/2 + 1/3) / 4, 6)
