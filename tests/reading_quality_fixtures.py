"""Page shapes from the 2026-10-13 Reading source trial, written for the quality gate.

None is a copy of a real page: each reproduces the structure that made the trial's
extractor accept (or nearly accept) something that is not an article.
"""
from __future__ import annotations

_ZH_SENTENCES = (
    "历史学者在雅典的演说中谈到了西方文明与现代政治之间的关系。",
    "他认为，民主制度的根基来自公民对公共事务的长期参与和讨论。",
    "听众提出了许多问题，包括欧洲与美国之间的合作应该如何继续。",
    "会后，主办方表示将把整场讨论整理成文字，供更多读者阅读。",
)


def _zh_paragraphs(count: int) -> str:
    return "".join(f"<p>{''.join(_ZH_SENTENCES)}</p>" for _ in range(count))


# VOA 中文 video page: a player, a short blurb, then a list of related links.
VOA_ZH_VIDEO = (
    "<html><head><title>历史学者潘东凯：卢比奥雅典演说 - 美国之音</title>"
    '<meta property="og:site_name" content="美国之音"></head><body>'
    '<header><a href="/">美国之音</a></header><main><h1>历史学者潘东凯：卢比奥雅典演说</h1>'
    '<div class="media-pholder"><video src="/v/8208887.mp4" controls></video>'
    '<div class="player">没有媒体可用资源</div></div>'
    f"<div class='wsw'>{_zh_paragraphs(2)}</div>"
    '<div class="related"><h2>相关内容</h2><ul>'
    + "".join(f'<li><a href="/a/{n}.html">相关报道标题 {n}</a></li>' for n in range(6))
    + "</ul></div></main><footer>版权所有</footer></body></html>"
)

# A VOA 中文 section page after extraction: one long "date, headline, teaser" line per entry.
SECTION_BODY = chr(10).join(
    f"2026年10月{n}日也门局势持续紧张，联合国表示冲突已导致大量平民流离失所，各方呼吁尽快恢复谈判并保障人道主义通道畅通。" for n in range(1, 13)
)

# VOA 中文 index page "所有内容": a list of dated headlines, no article.
VOA_ZH_INDEX = (
    "<html><head><title>美国之音 / 所有内容</title></head><body><main><h1>所有内容</h1><ul>"
    + "".join(
        f'<li><a href="/a/{n}.html">中国经济增长放缓影响全球市场第{n}期</a><span>2026-10-{n:02d}</span></li>'
        for n in range(1, 13)
    )
    + "</ul></main></body></html>"
)

# The same listing after extraction has produced a body of short dated lines.
LISTING_BODY = "\n\n".join(f"中国经济增长放缓影响全球市场第{n}期\n\n2026-10-{n:02d}" for n in range(1, 13))

# VOA Learning English audio page: only a player and its placeholder (P0-D strips the placeholder).
VOA_LE_AUDIO = (
    "<html><head><title>Barbara McClintock, Geneticist and Nobel Winner - VOA Learning English</title>"
    '<meta property="og:site_name" content="VOA Learning English"></head><body>'
    '<nav><a href="#main">Accessibility links</a></nav><main><h1>Barbara McClintock, Geneticist</h1>'
    '<div class="media-pholder"><audio src="/a/8010810.mp3" controls></audio>'
    '<div class="player">No media source currently available</div></div></main></body></html>'
)

# zh Wikipedia featured-feed entry: the Special:FeedItem URL and a ~150 character lead.
WIKI_FEEDITEM_URL = "https://zh.wikipedia.org/wiki/Special:FeedItem/featured/20261005000000/zh"
WIKI_FEEDITEM = (
    "<html><head><title>维基百科2026年10月5日典范条目</title></head><body><main>"
    "<h1>维基百科2026年10月5日典范条目</h1>"
    "<p>代谢是生物体内维持生命的化学反应的总称，包括合成代谢与分解代谢两大类，"
    "这些反应使生物能够生长、繁殖、维持结构并对环境作出反应，是生命活动的基础。</p></main></body></html>"
)

BOT_CHALLENGE = (
    "<html><head><title>Client Challenge</title></head><body><main><h1>Client Challenge</h1>"
    "<p>Your browser is being checked. Enable JavaScript and cookies to continue.</p></main></body></html>"
)
ACCESS_DENIED = (
    "<html><head><title>403 Forbidden</title></head><body><center><h1>403 Forbidden</h1></center>"
    "<p>Access denied. You do not have permission to view this page.</p></body></html>"
)

# Ordinary articles that must keep passing.
_EN_PARAGRAPH = (
    "The research team spent three years measuring how quickly the glacier retreated, and the results "
    "were clearer than anyone expected. Every summer the edge of the ice moved back by more than a "
    "hundred metres, which scientists say is faster than any model had predicted. "
)
NASA_ARTICLE = (
    "<html><head><title>NASA Demonstrates Next-Generation Heat Shield | NASA</title>"
    '<meta property="og:site_name" content="NASA"></head><body><header><a href="/">NASA</a></header>'
    "<main><article><h1>NASA Demonstrates Next-Generation Heat Shield</h1>"
    + "".join(f"<p>{_EN_PARAGRAPH}</p>" for _ in range(6))
    + "</article></main><footer>Privacy</footer></body></html>"
)
GLOBAL_VOICES_EN = (
    "<html><head><title>How Ecuador is fighting to keep industrial fishing away - Global Voices</title>"
    '<meta property="og:site_name" content="Global Voices"></head><body><main><article>'
    "<h1>How Ecuador is fighting to keep industrial fishing away</h1>"
    + "".join(f"<p>{_EN_PARAGRAPH}</p>" for _ in range(8))
    + "</article></main></body></html>"
)
VOA_ZH_ARTICLE = (
    "<html><head><title>赖清德发表双十国庆演说 - 美国之音</title>"
    '<meta property="og:site_name" content="美国之音"></head><body><main><article>'
    "<h1>赖清德发表双十国庆演说</h1>"
    + _zh_paragraphs(12)
    + "</article></main></body></html>"
)
