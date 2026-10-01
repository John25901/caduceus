from backend.app.core.branding import brand_favicon_image, brand_logo_data_uri, brand_logo_png


def test_brand_logo_png_is_valid_png():
    data = brand_logo_png(compact=True)
    assert data.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
    assert len(data) > 1000


def test_brand_logo_data_uri():
    uri = brand_logo_data_uri(compact=True)
    assert uri.startswith("data:image/png;base64,")
    assert len(uri) > 1000


def test_brand_favicon_is_square():
    icon = brand_favicon_image()
    assert icon.size == (64, 64)
