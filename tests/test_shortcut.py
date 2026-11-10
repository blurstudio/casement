import io

import pytest

from casement.shortcut import Shortcut


def test_create_icon_copies_existing_ico(tmp_path):
    (tmp_path / "icon.ico").write_bytes(b"ico data")
    output = tmp_path / "out" / "copied.ico"

    result = Shortcut.create_icon(str(tmp_path / "icon.svg"), str(output))

    assert result == str(output)
    assert output.read_bytes() == b"ico data"


def test_create_shortcut_icon_from_svg(tmp_path, monkeypatch):
    pil_image = pytest.importorskip("PIL.Image")
    resvg_py = pytest.importorskip("resvg_py")

    svg = tmp_path / "icon.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        '<circle cx="12" cy="12" r="10" fill="red"/></svg>'
    )
    # common=0 writes the generated icon to %APPDATA%\casement\icons
    monkeypatch.setenv("APPDATA", str(tmp_path))

    Shortcut.create(
        "CASEMENT_DELETE_ME",
        "",
        icon_source=str(svg),
        path=str(tmp_path),
        common=0,
    )

    ico = tmp_path / "casement" / "icons" / "CASEMENT_DELETE_ME.ico"
    with pil_image.open(ico) as im:
        assert im.format == "ICO"
        assert (256, 256) in im.info["sizes"]
        # Small sizes are rendered from the svg, not downscaled from 256.
        im.size = (16, 16)
        direct = resvg_py.svg_to_bytes(svg_path=str(svg), width=16, height=16)
        with pil_image.open(io.BytesIO(direct)) as expected:
            assert (
                im.convert("RGBA").tobytes()
                == expected.convert("RGBA").tobytes()
            )
    assert (tmp_path / "CASEMENT_DELETE_ME.lnk").exists()
