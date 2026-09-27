import re
from pathlib import Path

from app import ORENA_ASSET_ROOT, ORENA_BRAND_SERVED, home, becoming_preview, next_learner_ui

ROOT = Path(__file__).resolve().parents[1]


def test_root_serves_new_orena_product() -> None:
    response = home()
    body = response.body.decode("utf-8")
    assert body == (ROOT / "templates" / "orena" / "index.html").read_text(encoding="utf-8")
    assert not (ROOT / "templates" / "index.html").exists()
    assert ORENA_ASSET_ROOT.name == "orena"


def test_root_document_is_not_cacheable() -> None:
    # The shell names every stylesheet and module the app loads, so a cached
    # copy keeps requesting yesterday's asset list and a sheet added since is
    # simply never fetched. Every asset answers no-store; the document that
    # names them has to as well.
    assert home().headers["cache-control"] == "no-store, max-age=0"


def test_becoming_aliases_canonicalize_to_root() -> None:
    response = becoming_preview()
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_oauth_callback_target_and_frontend_version_remain_canonical() -> None:
    auth = (ROOT / "auth_support.py").read_text(encoding="utf-8")
    assert 'RedirectResponse("/", status_code=302)' in auth

    frontend_version = (
        ROOT / "BECOMING_FRONTEND_VERSION"
    ).read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", frontend_version)

    template = (
        ROOT / "templates" / "orena" / "index.html"
    ).read_text(encoding="utf-8")
    assert '/orena-assets/app.js' in template
    assert '/orena-assets/world.css' in template
    assert '/becoming-assets/' not in template
    assert 'orena' in template
    assert not (ROOT / 'static/becoming').exists()


def test_next_serves_the_new_learner_ui_uncached() -> None:
    # D-091: the new learner UI is built beside the old one at /next until the
    # cutover, from its own template that loads none of the old UI's assets.
    response = next_learner_ui()
    body = response.body.decode("utf-8")
    assert body == (ROOT / "templates" / "orena" / "next.html").read_text(encoding="utf-8")
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert "/orena-assets/main.js" in body
    assert "/orena-assets/kit/tokens.css" in body
    for old in ("/orena-assets/app.js", "/orena-assets/theme.css", "/orena-assets/theme.js", "/orena-assets/world.css"):
        assert old not in body


def test_brand_marks_are_served_from_the_art_bible() -> None:
    # D-090: the logo and the Orena Intelligence mark are served from their one
    # copy in assets/brand/orena/logo, never duplicated into the web tree.
    assert "logo" in ORENA_BRAND_SERVED
    sprite = (ROOT / "assets" / "brand" / "orena" / "logo" / "orena-marks.svg").read_text(encoding="utf-8")
    for symbol in ("ol-mark", "ol-intel", "ol-intel-still", "ol-intel-listen", "ol-intel-speak", "ol-intel-think"):
        assert f'id="{symbol}"' in sprite
