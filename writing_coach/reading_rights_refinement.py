"""Per-item rights refinement at ingest (D-193, proposed).

A source's rights are a default for everything it publishes. For some publishers
the default is only true of the work they produced themselves: VOA's own staff
output is US-government work and in the public domain, but VOA also carries wire
copy (Reuters, AP, AFP, ...) and rewrites of it. Asserting "Public domain" for
such an item would be false.

This pure module decides, from what the extractor already read (author, body,
attribution lines), whether an item may inherit its source's republish/adapt/licence
answers. When it may not, those answers are withheld from the item's immutable
snapshot - an absent key is the existing "unknown" (`rights_state`) - so that
the D-190 warnings fire for the administrator, D-111 refuses automatic admission
(`rights_not_cleared`), and the learner is never shown a public-domain licence.
Nothing here grants a right; it can only withhold one. The reason is kept in the
item's metadata (`rights_refinement`) for the review page.

The condition is declarative configuration (`SOURCE_RIGHTS_RULES`, keyed by host
like `reading_source_cleanup.SOURCE_RULES`), not a branch on a publisher's name.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

REFINEMENT_VERSION = "reading-rights-refinement/1"
RULE_STAFF_AUTHORSHIP = "public_domain_requires_staff_authorship"

# host -> flags. A page host matches when it equals the key or ends with "." + key.
SOURCE_RIGHTS_RULES: dict[str, dict[str, bool]] = {
    "voanews.com": {RULE_STAFF_AUTHORSHIP: True},
    "voachinese.com": {RULE_STAFF_AUTHORSHIP: True},
}

# What an inherited source answer can no longer vouch for on a withheld item.
WITHHELD_KEYS = ("can_republish", "can_adapt", "license_note")

_AGENCY = (
    r"(?<![A-Za-z])(?:路透社?|美联社|法新社|德新社|新华社|中央社|共同社|韩联社|纽约时报|美国联合通讯社|彭博(?:社|新闻社?|资讯|通讯社)"
    r"|Reuters|Associated\s+Press|Agence\s+France[- ]Presse|AFP|Deutsche\s+Presse-Agentur|dpa"
    r"|Bloomberg(?:\s+News)?|Kyodo(?:\s+News)?|Yonhap(?:\s+News)?|Xinhua|The\s+New\s+York\s+Times|(?-i:AP|CNA))(?![A-Za-z])"
)
_LIST = rf"{_AGENCY}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+|\s*&\s*){_AGENCY})*"
# English credit forms. A credit ENDS the line on the agency ("... came from AP, Reuters and AFP."), so a
# sentence of prose that merely names one ("Reuters reported that ...", "according to a Reuters report") never matches.
_CREDIT_EN = re.compile(
    rf"(?:{_LIST}\s+(?:also\s+)?(?:contributed\s+to|provided\s+(?:information|reporting)\s+for)\s+this\s+(?:report|story)"
    r"|(?:(?:some|additional)\s+)?(?:information|reporting|material|video|photos?)\s+(?:for\s+this\s+(?:report|story)\s+)?"
    rf"(?:came|comes|was\s+provided|provided|supplied)\s+(?:from|by)\s+{_LIST}"
    rf"|(?:reported|reporting|written|supplied|provided|photographed)\s+(?:by|from)\s+{_LIST}"
    rf"|(?:based\s+on|adapted\s+from|compiled\s+from|with)\s+(?:(?:wire\s+)?(?:reporting|reports|information|material)\s+)?(?:from|by)\s+{_LIST}"
    r")\W*$",
    re.IGNORECASE,
)
_MAX_EN_CREDIT_LINE = 160
_AGENCY_RE = re.compile(_AGENCY, re.IGNORECASE)
# The agency named as the owner of the line: bracketed, or after a credit verb / label.
_BRACKETED = re.compile(r"[（(\[][^）)\]\n]{0,30}?" + _AGENCY + r"[^）)\]\n]{0,30}[）)\]]", re.IGNORECASE)
_DATELINE = re.compile(r"^[^。.!?！？\n]{0,40}?(?<![社])[（(]\s*" + _AGENCY + r"\s*[）)]\s*[—–:：-]", re.IGNORECASE)
_DERIVATION_ZH = re.compile(
    r"(?:依据|根据|综合|编译|改写|编自|摘自|转载自|转自|取自|源自|引自|参考|译自|来自|基于)[^。\n]{0,16}?" + _AGENCY, re.IGNORECASE)
_DERIVATION_AFTER = re.compile(_AGENCY + r"[^。\n]{0,4}?(?:的)?(?:报道|电|消息|稿件|供稿|提供|图片|照片|资料)", re.IGNORECASE)
_CREDIT_LABEL = re.compile(
    r"(?:来源|出处|图片|照片|摄影|供图|图源|Photo|Image|Source|Credit|Reporting\s+by|Additional\s+reporting"
    r"|Compiled\s+from|Based\s+on|With\s+(?:wire|agency)\s+reports|Contributed\s+to\s+this\s+report)[^\n]{0,30}?" + _AGENCY,
    re.IGNORECASE)
_MAX_CREDIT_LINE = 40  # characters: a credit or derivation note is a line, not a sentence in a story


def _agency_names(text: str) -> list[str]:
    return [match.group(0) for match in _AGENCY_RE.finditer(text)]


def detect_wire_credit(
    *, body: str, author: str, attribution_lines: Sequence[str] = ()
) -> list[dict[str, str]]:
    """Evidence that an item is, or is derived from, an agency's copy.

    Deliberately narrow: a sentence in a staff story that names an agency as a news
    source ("路透社说 ...", "told AP") is ordinary sourcing in the publisher's own
    words and is not evidence. What counts is a line that is a credit, a dateline or
    a derivation note ("(本文依据了美联社的报道。)"), or an author/byline that is
    an agency."""
    found: list[dict[str, str]] = []
    if _AGENCY_RE.fullmatch((author or "").strip()):
        found.append({"kind": "agency_byline", "text": author.strip()[:120]})
    for line in attribution_lines:
        if _agency_names(str(line)):
            found.append({"kind": "attribution_line", "text": str(line).strip()[:120]})
    for raw in re.split(r"\n+", body or ""):
        line = raw.strip()
        if not line or not _agency_names(line):
            continue
        if _DATELINE.search(line):
            found.append({"kind": "dateline", "text": line[:120]})
        elif len(line) <= _MAX_EN_CREDIT_LINE and _CREDIT_EN.search(line):
            found.append({"kind": "credit_line", "text": line[:120]})
        elif len(line) <= _MAX_CREDIT_LINE and (
            _BRACKETED.search(line) or _DERIVATION_ZH.search(line) or _CREDIT_LABEL.search(line)
            or (_DERIVATION_AFTER.fullmatch(line.strip("()（）[] 。.")))
        ):
            found.append({"kind": "credit_line", "text": line[:120]})
    unique: list[dict[str, str]] = []
    for entry in found:
        if entry not in unique:
            unique.append(entry)
    return unique[:5]


def rule_for(host: str) -> dict[str, bool]:
    host = (host or "").lower().split(":")[0].removeprefix("www.")
    merged: dict[str, bool] = {}
    for key, flags in SOURCE_RIGHTS_RULES.items():
        if host == key or host.endswith("." + key):
            merged.update(flags)
    return merged


def host_of(url: str) -> str:
    try:
        return (urlsplit(url or "").hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def refine_item_rights(
    *, source_base_url: str, canonical_url: str, author: str, body: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any] | None:
    """The refinement for one item, or None when no rule applies to its host.

    `outcome` is "kept" (staff authorship established, no wire evidence) or
    "withheld" (wire evidence, or no byline to establish authorship). The caller drops
    `WITHHELD_KEYS` that were inherited from the source when the outcome is withheld.
    """
    flags = rule_for(host_of(canonical_url)) or rule_for(host_of(source_base_url))
    if not flags.get(RULE_STAFF_AUTHORSHIP):
        return None
    extraction = metadata.get("extraction") if isinstance(metadata, Mapping) else None
    lines = (extraction or {}).get("attribution_lines") or []
    evidence = detect_wire_credit(body=body, author=author, attribution_lines=lines)
    reasons: list[str] = []
    if evidence:
        reasons.append("wire_copy")
    if not (author or "").strip():
        reasons.append("no_staff_byline")
    return {
        "version": REFINEMENT_VERSION,
        "rule": RULE_STAFF_AUTHORSHIP,
        "outcome": "withheld" if reasons else "kept",
        "reasons": reasons,
        "evidence": evidence,
        "withheld": list(WITHHELD_KEYS) if reasons else [],
    }
