"""底 written for the structural particle 的 (PRE-105 / D23).

Early written vernacular (Xu Dishan's 落花生, 1922: 我们底, 父亲底, 花生底好处) spells the attributive particle 的 as
底. The dictionary reading and gloss of 底 are dǐ "bottom", which is right for every lexical use (到底, 底下, 海底,
彻底, 年底 ...) and wrong here. The tagger never marks this use as a particle (jieba calls it a locative `f`, or merges
it into the next word: 底话, 底书), so the decision is made on the characters and on the word before it.

One rule, shared by the sentence annotation (`linguistic_annotation`) and the word lookup (`reading_lookup`), so the two
agree. Everything is data: add a compound to `COMPOUND_EXCLUSIONS` rather than special-casing a text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

__all__ = [
    "COMPOUND_EXCLUSIONS",
    "FORM",
    "READING",
    "gloss",
    "is_structural_particle",
    "is_structural_reading",
]

FORM = "底"
READING = "de"

# Lexical words containing 底: 底 inside any of these (matched in the source text around it) is never the particle.
COMPOUND_EXCLUSIONS: tuple[str, ...] = (
    "到底", "底下", "底层", "底部", "底面", "底线", "彻底", "心底", "海底", "年底", "月底", "井底", "眼底",
    "根底", "底细", "底子", "底片", "底座", "底色", "底稿", "底蕴", "封底", "水底", "地底", "脚底", "鞋底", "锅底",
    "碗底", "杯底", "瓶底", "缸底", "桶底", "箱底", "船底", "河底", "湖底", "池底", "山底", "谷底", "海底捞针",
    "底气", "追根问底", "寻根问底", "问底", "底楼", "底纹", "底图", "底妆", "底料", "底仓", "底火", "底功",
    "底样", "底单", "底洞", "底册", "底牌", "底价", "底数", "底薪", "底盘", "底漆", "底版", "底本", "底案", "底账", "底肥", "底边",
    "底角", "底舱", "底端", "底限", "底里", "底事", "探底", "触底", "见底", "垫底", "打底", "抄底", "兜底",
    "托底", "保底", "筑底", "落底", "沉底", "掉底", "穿底", "刨根问底", "寻根究底", "归根结底", "追根究底",
    "骨子里", "胶底", "布底", "厚底", "薄底", "平底", "尖底", "圆底", "凹底", "凸底", "无底", "洞底", "窑底", "坑底",
)

# A compound above that is NOT the word when the text goes on with one of these characters: the real segment is a longer
# word that begins after 底, so 底 is the particle (花生底气味, 它底样子).
COMPOUND_EXCEPTIONS: Mapping[str, tuple[str, ...]] = {
    "底气": ("味",),
    "底样": ("子",),
}

# A word that precedes the particle as the possessor / modifier. Pronouns are decided by the word itself, so a tagger
# that mislabels one cannot lose the reading.
MODIFIER_PRONOUNS = frozenset(
    {"我", "你", "他", "她", "它", "我们", "你们", "他们", "她们", "它们", "咱们", "咱", "自己", "大家", "人家", "谁", "彼"}
)
# Otherwise the word before must be tagged as a noun, pronoun, verb, numeral, measure word, time or place word
# (n* r* v* m* q* t* s*: 买种底买种, 几样底食品, 晚上底天色) by the tagger, and have at least this many
# characters: a lone noun before 底 is far more often the first half of a compound (池底, 锅底) than a possessor.
MODIFIER_TAG_PREFIXES = ("n", "r", "v", "m", "q", "t", "s")
MIN_NOUN_LENGTH = 2

# A character after 底 that makes it the head of a lexical compound (底下, 底层, 底部, 底面, 底线), never the particle.
COMPOUND_FOLLOWERS = frozenset("下层部面线")

_HAN = re.compile(r"[㐀-䶿一-鿿]")

# The sense shown for the tap, by support language: the particle 的, with the note that this is its old written form.
_GLOSSES: Mapping[str, tuple[str, str]] = {
    "en": ("the particle 的 (possessive / attributive)", "old written form of 的"),
    "vi": ("trợ từ 的 (sở hữu / định ngữ)", "dạng viết cũ của 的"),
    "zh": ("结构助词“的”（表领属、修饰）", "“的”的旧式写法"),
}


def is_structural_particle(source: str, index: int, previous_word: str, previous_flag: str) -> bool:
    """Whether the 底 at `source[index]` is the particle 的, given the tagged word that ends just before it."""

    if index < 0 or index >= len(source) or source[index] != FORM:
        return False
    for compound in COMPOUND_EXCLUSIONS:
        offset = compound.find(FORM)
        while offset >= 0:
            start = index - offset
            if start >= 0 and source[start : start + len(compound)] == compound:
                tail = source[start + len(compound) :]
                if not any(tail.startswith(extra) for extra in COMPOUND_EXCEPTIONS.get(compound, ())):
                    return False
            offset = compound.find(FORM, offset + 1)
    following = source[index + 1 : index + 2]
    if following in COMPOUND_FOLLOWERS:
        return False
    word = str(previous_word or "")
    if word in MODIFIER_PRONOUNS:
        return True  # 这是我们底: a pronoun possessor needs no head after it
    if len(word) >= MIN_NOUN_LENGTH and str(previous_flag or "").startswith(MODIFIER_TAG_PREFIXES):
        return bool(following and _HAN.match(following))  # a noun modifier must be followed by what it modifies
    return False


def is_structural_reading(word: str, reading: str) -> bool:
    """Whether the tagger's contextual `reading` of the single character `word` is the particle's."""

    return word == FORM and str(reading or "").strip().casefold() == READING


def gloss(language: str) -> tuple[str, str]:
    """The (meaning, note) of the particle for a support language, English when it has none of its own."""

    return _GLOSSES.get(str(language or "").split("-", 1)[0].casefold(), _GLOSSES["en"])
