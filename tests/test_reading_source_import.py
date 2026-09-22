"""Every Reading input - paste, URL, file - converges on one normalized item.

The point of the adapter boundary is that the pipeline behind it never learns
where a text came from: a pasted paragraph, a fetched page and an uploaded
file all arrive as the same `NormalizedSourceItem`, with the same hash rule,
the same cleaning and the same rights snapshot. These tests hold that boundary
still, and they hold the limits: an admin-supplied URL is fetched under the
existing SSRF guard, never by a second, friendlier fetcher written for
Reading.
"""
from __future__ import annotations

import pytest

from writing_coach.reading_source_import import (
    MAX_TEXT_CHARS,
    DirectUrlAdapter,
    FileAdapter,
    ManualTextAdapter,
    ReadingSourceError,
    SubmittedInput,
    adapter_for,
    request_digest,
)

RIGHTS = {"can_republish": True, "attribution_required": True, "license_note": "CC BY 4.0"}

ARTICLE_HTML = """
<html><head>
  <title>Rain returns to the valley</title>
  <meta name="author" content="M. Tran">
  <meta property="article:published_time" content="2026-03-04T08:00:00+00:00">
</head><body>
  <nav>Home Sections Subscribe</nav>
  <script>trackEverything()</script>
  <article><p>The river rose overnight.</p><p>By morning the fields were green again.</p></article>
  <footer>Copyright 2026</footer>
</body></html>
"""


def _fetcher(body: str, content_type: str = "text/html"):
    calls: list[str] = []

    def fetch(url: str, *, max_bytes: int, timeout: float, content_types):
        calls.append(url)
        return body.encode("utf-8"), content_type

    fetch.calls = calls  # type: ignore[attr-defined]
    return fetch


# ---- manual text ------------------------------------------------------------

def test_pasted_text_becomes_a_normalized_item_with_a_hash():
    submitted = SubmittedInput(
        kind="text",
        text="  The garden was quiet.\n\n  The old man watered every plant.  ",
        title="A quiet garden",
        author="Orena Editorial",
        rights=RIGHTS,
    )
    item = ManualTextAdapter().normalize(ManualTextAdapter().fetch(submitted))
    assert item.title == "A quiet garden"
    assert item.author == "Orena Editorial"
    assert item.body == "The garden was quiet.\n\nThe old man watered every plant."
    assert len(item.content_hash) == 64
    assert item.rights == RIGHTS
    assert item.canonical_url == ""


def test_pasted_text_detects_its_language_when_the_admin_did_not_say():
    submitted = SubmittedInput(kind="text", text="今天早上的花园很安静，老人给每一棵植物浇水。", rights=RIGHTS)
    item = ManualTextAdapter().normalize(ManualTextAdapter().fetch(submitted))
    assert item.language == "zh"
    assert item.metadata["detected_language"] == "zh"


def test_a_declared_language_is_kept_and_the_disagreement_recorded():
    submitted = SubmittedInput(
        kind="text", text="今天早上的花园很安静，老人给每一棵植物浇水。", language="en", rights=RIGHTS
    )
    item = ManualTextAdapter().normalize(ManualTextAdapter().fetch(submitted))
    assert item.language == "en"
    assert item.metadata["detected_language"] == "zh"
    assert item.metadata["language_mismatch"] is True


def test_an_empty_paste_is_refused_rather_than_stored_as_an_empty_article():
    with pytest.raises(ReadingSourceError) as failure:
        ManualTextAdapter().fetch(SubmittedInput(kind="text", text="   \n  ", rights=RIGHTS))
    assert failure.value.code == "empty_source"


def test_a_paste_over_the_limit_is_refused_before_it_is_processed():
    with pytest.raises(ReadingSourceError) as failure:
        ManualTextAdapter().fetch(
            SubmittedInput(kind="text", text="x" * (MAX_TEXT_CHARS + 1), rights=RIGHTS)
        )
    assert failure.value.code == "source_too_large"


def test_missing_rights_are_recorded_rather_than_assumed():
    item = ManualTextAdapter().normalize(
        ManualTextAdapter().fetch(SubmittedInput(kind="text", text="A short text about rain.", rights={}))
    )
    assert item.metadata["rights_known"] is False


# ---- direct URL -------------------------------------------------------------

def test_a_fetched_page_yields_body_title_author_and_publication_date():
    adapter = DirectUrlAdapter(fetcher=_fetcher(ARTICLE_HTML))
    submitted = SubmittedInput(kind="url", url="https://example.com/news/rain?utm_source=x", rights=RIGHTS)
    item = adapter.normalize(adapter.fetch(submitted))
    assert item.title == "Rain returns to the valley"
    assert item.author == "M. Tran"
    assert item.published_at is not None and item.published_at.year == 2026
    assert item.body == "The river rose overnight.\n\nBy morning the fields were green again."
    assert "trackEverything" not in item.body and "Subscribe" not in item.body


def test_the_canonical_url_is_the_identity_a_second_submission_dedupes_on():
    adapter = DirectUrlAdapter(fetcher=_fetcher(ARTICLE_HTML))
    first = adapter.normalize(
        adapter.fetch(SubmittedInput(kind="url", url="https://www.example.com/news/rain?utm_source=x", rights=RIGHTS))
    )
    second = adapter.normalize(
        adapter.fetch(SubmittedInput(kind="url", url="https://example.com/news/rain#top", rights=RIGHTS))
    )
    assert first.canonical_url == second.canonical_url == "https://example.com/news/rain"
    assert first.source_native_id == first.canonical_url
    assert first.content_hash == second.content_hash


def test_a_private_address_is_refused_by_the_existing_guard_not_fetched():
    adapter = DirectUrlAdapter()
    for url in ("http://127.0.0.1:8000/admin", "http://169.254.169.254/latest/meta-data/"):
        with pytest.raises(ReadingSourceError) as failure:
            adapter.fetch(SubmittedInput(kind="url", url=url, rights=RIGHTS))
        assert failure.value.code == "unsafe_url"


def test_a_url_that_is_not_http_is_refused_before_any_lookup():
    adapter = DirectUrlAdapter()
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(SubmittedInput(kind="url", url="file:///etc/passwd", rights=RIGHTS))
    assert failure.value.code == "unsafe_url"


def test_a_binary_content_type_is_refused_rather_than_decoded_as_text():
    adapter = DirectUrlAdapter(fetcher=_fetcher("%PDF-1.7", content_type="application/pdf"))
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(SubmittedInput(kind="url", url="https://example.com/a.pdf", rights=RIGHTS))
    assert failure.value.code == "unsupported_content_type"


def test_the_fetch_is_bounded_and_a_refusal_is_reported_as_a_job_error():
    def refusing_fetcher(url, *, max_bytes, timeout, content_types):
        from writing_coach.media_safe_fetch import UnsafeMediaFetch

        raise UnsafeMediaFetch("This media file is too large.")

    adapter = DirectUrlAdapter(fetcher=refusing_fetcher)
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(SubmittedInput(kind="url", url="https://example.com/big", rights=RIGHTS))
    assert failure.value.code == "fetch_failed"


def test_a_page_with_no_readable_text_is_refused_not_stored_empty():
    adapter = DirectUrlAdapter(fetcher=_fetcher("<html><body><script>x()</script></body></html>"))
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(SubmittedInput(kind="url", url="https://example.com/empty", rights=RIGHTS))
    assert failure.value.code == "empty_source"


# ---- file -------------------------------------------------------------------

@pytest.mark.parametrize("filename", ["story.txt", "story.md", "story.html"])
def test_text_friendly_files_are_accepted(filename):
    adapter = FileAdapter()
    submitted = SubmittedInput(
        kind="file", filename=filename, payload=b"<p>The river rose overnight.</p>", rights=RIGHTS
    )
    item = adapter.normalize(adapter.fetch(submitted))
    assert "river rose overnight" in item.body
    assert item.metadata["filename"] == filename


def test_a_format_this_phase_does_not_parse_is_refused_by_name_and_by_content():
    adapter = FileAdapter()
    with pytest.raises(ReadingSourceError) as by_name:
        adapter.fetch(SubmittedInput(kind="file", filename="story.pdf", payload=b"%PDF-1.7", rights=RIGHTS))
    assert by_name.value.code == "unsupported_file_type"
    with pytest.raises(ReadingSourceError) as by_content:
        adapter.fetch(
            SubmittedInput(kind="file", filename="story.txt", payload=b"%PDF-1.7\x00\x01binary", rights=RIGHTS)
        )
    assert by_content.value.code == "unsupported_file_type"


def test_a_filename_cannot_carry_a_path_into_the_item():
    adapter = FileAdapter()
    item = adapter.normalize(
        adapter.fetch(
            SubmittedInput(
                kind="file",
                filename="../../etc/passwd.txt",
                payload=b"The river rose overnight.",
                rights=RIGHTS,
            )
        )
    )
    assert item.metadata["filename"] == "passwd.txt"


def test_a_file_over_the_limit_is_refused():
    adapter = FileAdapter()
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(
            SubmittedInput(
                kind="file", filename="story.txt", payload=b"a" * (MAX_TEXT_CHARS * 4 + 1), rights=RIGHTS
            )
        )
    assert failure.value.code == "source_too_large"


def test_a_file_that_is_not_utf8_is_refused_with_its_own_reason():
    adapter = FileAdapter()
    with pytest.raises(ReadingSourceError) as failure:
        adapter.fetch(
            SubmittedInput(kind="file", filename="story.txt", payload="café".encode("latin-1"), rights=RIGHTS)
        )
    assert failure.value.code == "undecodable_source"


# ---- the boundary itself ----------------------------------------------------

def test_every_supported_kind_has_an_adapter_and_an_unknown_kind_does_not():
    assert adapter_for("text").kind == "manual"
    assert adapter_for("url").kind == "direct_url"
    assert adapter_for("file").kind == "file"
    with pytest.raises(ReadingSourceError) as failure:
        adapter_for("telepathy")
    assert failure.value.code == "unsupported_input"


def test_the_request_digest_is_the_idempotency_key_the_queue_needs():
    first = SubmittedInput(kind="url", url="https://www.example.com/a?utm_source=x", rights=RIGHTS)
    same = SubmittedInput(kind="url", url="https://example.com/a", rights=RIGHTS)
    other = SubmittedInput(kind="url", url="https://example.com/b", rights=RIGHTS)
    assert request_digest(first) == request_digest(same)
    assert request_digest(first) != request_digest(other)
    assert len(request_digest(first)) == 64


def test_two_pastes_of_the_same_text_share_a_digest_and_differ_from_a_third():
    first = SubmittedInput(kind="text", text="The river rose overnight.", rights=RIGHTS)
    same = SubmittedInput(kind="text", text="The river rose overnight.", rights=RIGHTS)
    other = SubmittedInput(kind="text", text="The river fell overnight.", rights=RIGHTS)
    assert request_digest(first) == request_digest(same) != request_digest(other)


def test_the_adapter_contract_is_the_same_shape_for_every_kind():
    for adapter in (ManualTextAdapter(), DirectUrlAdapter(), FileAdapter()):
        assert hasattr(adapter, "discover") and hasattr(adapter, "fetch") and hasattr(adapter, "normalize")
        assert adapter.discover() == []
