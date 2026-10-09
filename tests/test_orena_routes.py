import re
from pathlib import Path
from types import SimpleNamespace

from app import ORENA_ASSET_ROOT, ORENA_BRAND_SERVED, home, becoming_preview, former_learner_ui_address

ROOT = Path(__file__).resolve().parents[1]
# Sign-in is off in the test environment, so `/` is the shell whoever asks (tests/test_public_entry.py covers sign-in on).
_VISITOR = SimpleNamespace(session={}, query_params={})


def test_root_serves_the_learner_ui() -> None:
    # D-091 item 5, D-143: since the cutover `/` serves the learner UI, from a template that loads none of
    # the retired UI's assets.
    body = home(_VISITOR).body.decode("utf-8")
    assert body == (ROOT / "templates" / "orena" / "index.html").read_text(encoding="utf-8")
    assert "/orena-assets/main.js" in body
    assert "/orena-assets/kit/tokens.css" in body
    for old in ("/orena-assets/app.js", "/orena-assets/theme.css", "/orena-assets/theme.js", "/orena-assets/world.css"):
        assert old not in body
    assert not (ROOT / "templates" / "index.html").exists()
    assert ORENA_ASSET_ROOT.name == "orena"


def test_root_document_is_not_cacheable() -> None:
    # The shell names every stylesheet and module the app loads, so a cached
    # copy keeps requesting yesterday's asset list and a sheet added since is
    # simply never fetched. Every asset answers no-store; the document that
    # names them has to as well.
    assert home(_VISITOR).headers["cache-control"] == "no-store, max-age=0"


def test_former_addresses_canonicalize_to_root() -> None:
    for response in (becoming_preview(), former_learner_ui_address()):
        assert response.status_code == 302
        assert response.headers["location"] == "/"


def test_oauth_callback_target_and_frontend_version_remain_canonical() -> None:
    auth = (ROOT / "auth_support.py").read_text(encoding="utf-8")
    assert 'safe_next_target(stored_next, default="/") if stored_next else "/"' in auth

    frontend_version = (
        ROOT / "BECOMING_FRONTEND_VERSION"
    ).read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", frontend_version)
    assert not (ROOT / 'static/becoming').exists()


def test_brand_marks_are_served_from_the_art_bible() -> None:
    # D-090: the logo and the Orena Intelligence mark are served from their one
    # copy in assets/brand/orena/logo, never duplicated into the web tree.
    assert "logo" in ORENA_BRAND_SERVED
    sprite = (ROOT / "assets" / "brand" / "orena" / "logo" / "orena-marks.svg").read_text(encoding="utf-8")
    for symbol in ("ol-mark", "ol-intel", "ol-intel-still", "ol-intel-listen", "ol-intel-speak", "ol-intel-think"):
        assert f'id="{symbol}"' in sprite
