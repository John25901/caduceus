from backend.app.ingestion.document_profiler import profile_document_text


def test_contact_directory_is_not_treated_as_equipment():
    text = """
    AGRICULTURE & MATERIEL AGRICOLE
    RAISON SOCIALE : STE COMPTOIR AGRICOLE DU SOUSS
    ADRESSE : RUE JABIR BEN HAYANE
    TEL : 0524434109
    FAX : 0524434614
    RAISON SOCIALE : STE AGRODEP
    ADRESSE : MARRAKECH
    TEL : 0524420252
    FAX : 0524430535
    """
    p = profile_document_text(text)
    assert p.kind == "DIRECTORY_CONTACTS"
    assert p.equipment_likelihood < 0.1


def test_nonstandard_equipment_text_is_identified():
    text = """
    INDUSTRIAL PROJECT EQUIPMENT
    PVC pipe production line
    Automatic belling machine
    Air compressor 30HP
    Mixer
    Crusher
    """
    p = profile_document_text(text)
    assert p.kind == "EQUIPMENT_LIST"
    assert p.equipment_likelihood >= 0.6
