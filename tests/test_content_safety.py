from pathlib import Path
from relluna.services.content_safety.nsfw import check_image_nsfw


def test_nsfw_stub_returns_result(tmp_path):
    img = tmp_path / "x.jpg"
    img.write_bytes(b"fake")

    result = check_image_nsfw(img)

    assert result is not None
    assert result.is_nsfw is False
    assert result.score == 0.0