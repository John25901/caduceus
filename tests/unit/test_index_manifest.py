from backend.app.customs.index_manager import CamcisIndexManager


def test_manifest_matches_only_exact_reference_model_and_collection():
    manifest = {
        "manifest_version": 1,
        "camcis_sha256": "abc",
        "embedding_model": "model-a",
        "records": 6869,
        "collection_name": "camcis_abc_model",
    }
    assert CamcisIndexManager.manifest_matches(
        manifest,
        camcis_sha256="abc",
        embedding_model="model-a",
        expected_records=6869,
        expected_collection="camcis_abc_model",
    )
    assert not CamcisIndexManager.manifest_matches(
        manifest,
        camcis_sha256="changed",
        embedding_model="model-a",
        expected_records=6869,
        expected_collection="camcis_abc_model",
    )
    assert not CamcisIndexManager.manifest_matches(
        manifest,
        camcis_sha256="abc",
        embedding_model="model-b",
        expected_records=6869,
        expected_collection="camcis_abc_model",
    )
