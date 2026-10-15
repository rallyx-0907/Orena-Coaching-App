"""The local tagger answers for a supported language whoever is asking (P1-5, live).

The Listening player widens a one-character Chinese tap to the tagged word. An administrator previewing a held
Chinese item (D-206) has English as the learning language, so the endpoint answered 409 and the tap stayed on
one character. The tagger is local, stateless and spends no AI, so it needs only a language it can segment.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from writing_coach.core.request_context import LANGUAGE_CODE_CTX
from writing_coach.media_interaction import MediaAnnotateIn, annotate_media_text

LINE = "请先洗手，然后擦干。"


@pytest.mark.parametrize("learning", ["en", "zh"])
def test_a_chinese_line_is_tagged_whatever_the_learning_language(learning):
    token = LANGUAGE_CODE_CTX.set(learning)
    try:
        result = annotate_media_text(MediaAnnotateIn(text=LINE, source_language="zh"))
    finally:
        LANGUAGE_CODE_CTX.reset(token)
    spans = {(a["start"], a["end"]): a["fragment"] for a in result["annotations"]}
    assert spans.get((2, 4)) == "洗手" and LINE[2:4] == "洗手", spans


def test_an_unsupported_language_is_refused():
    with pytest.raises(HTTPException) as caught:
        annotate_media_text(MediaAnnotateIn(text="hola", source_language="es"))
    assert caught.value.status_code == 422
