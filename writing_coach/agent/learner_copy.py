"""Server-written learner copy, each key declaring its language layer (D-080).

The agent's own words - `error.message`, `tool_call.label`, an action's or a
suggestion's label, a capability's title - are copy, not model output (spec
§13). Every key names its layer, and the text is chosen from the pack of that
layer: `interface` for names, labels, buttons and short system statuses (every
`label` the agent sends, human ruling 2026-09-27), `support` for explanations
and the explanation of an error. There is no default layer, and no `target`
copy (material never lives in copy). A support language without a pack reads
English, never the interface language (D-080).

Packs are keyed by contract codes (`zh-CN`, not `zh`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

FALLBACK_LANGUAGE = "en"
PACK_LANGUAGES = ("en", "vi", "zh-CN")


class CopyLayer(StrEnum):
    INTERFACE = "interface"
    SUPPORT = "support"


@dataclass(frozen=True)
class CopyEntry:
    layer: CopyLayer
    texts: Mapping[str, str]


def _entry(layer: CopyLayer, texts: dict[str, str]) -> CopyEntry:
    missing = [code for code in PACK_LANGUAGES if not texts.get(code)]
    if missing or set(texts) - set(PACK_LANGUAGES):
        raise ValueError(f"copy entry needs exactly {PACK_LANGUAGES}")
    return CopyEntry(layer, MappingProxyType(dict(texts)))


CATALOG: Mapping[str, CopyEntry] = MappingProxyType(
    {
        # Said in place of a claim that a button's action is done (agent/honesty.py): support layer,
        # since it is part of the answer; the label is the button's own interface-layer text.
        # Built from the action in hand (label, and the word it names): what tapping does.
        "offer.save_word": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} to add {text} to your words.", "vi": "Bấm {label} để thêm {text} vào từ vựng của bạn.",
             "zh-CN": "点击“{label}”，把{text}加入你的词汇。"},
        ),
        "offer.unsave_word": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} to remove {text} from your words.", "vi": "Bấm {label} để bỏ {text} khỏi từ vựng của bạn.",
             "zh-CN": "点击“{label}”，把{text}从你的词汇中移除。"},
        ),
        "offer.add_word_to_collection": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} to add {text} to the collection.", "vi": "Bấm {label} để thêm {text} vào bộ sưu tập.",
             "zh-CN": "点击“{label}”，把{text}加入收藏。"},
        ),
        "offer.start_review": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} to start the review.", "vi": "Bấm {label} để bắt đầu ôn.", "zh-CN": "点击“{label}”开始复习。"},
        ),
        "offer.navigate": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} to open it.", "vi": "Bấm {label} để mở.", "zh-CN": "点击“{label}”打开。"},
        ),
        "offer.action": _entry(
            CopyLayer.SUPPORT,
            {"en": "Tap {label} if you want to.", "vi": "Bấm {label} nếu bạn muốn.", "zh-CN": "需要的话，点击“{label}”。"},
        ),
        # Said when every sentence of an answer claimed Orena had changed something (agent/honesty.py).
        "honesty.nothing_done": _entry(
            CopyLayer.SUPPORT,
            {"en": "I haven't changed anything.", "vi": "Mình chưa thay đổi gì cả.", "zh-CN": "我没有做任何更改。"},
        ),
        "identity.who": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "I'm Orena, your AI learning assistant and personal coach in this app. "
                "Ask me about this screen, your progress, or what to practise next.",
                "vi": "Mình là Orena, trợ lý học tập AI và huấn luyện viên riêng của bạn trong ứng dụng này. "
                "Bạn có thể hỏi mình về màn hình này, tiến độ học, hay nên luyện gì tiếp.",
                "zh-CN": "我是 Orena，你在这个应用里的 AI 学习助手和私人教练。"
                "你可以问我这个页面的用法、你的学习进度，或者接下来该练什么。",
            },
        ),
        "identity.model": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "I'm Orena, your AI learning assistant and personal coach. "
                "The AI model behind me is chosen by Orena and may change, so I don't name one.",
                "vi": "Mình là Orena, trợ lý học tập AI và huấn luyện viên riêng của bạn. "
                "Mô hình AI phía sau do Orena chọn và có thể thay đổi, nên mình không nêu tên mô hình.",
                "zh-CN": "我是 Orena，你的 AI 学习助手和私人教练。背后的 AI 模型由 Orena 选择，可能会更换，所以我不说具体名称。",
            },
        ),
        "error.provider_unavailable": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Orena is busy. Please try again shortly.",
                "vi": "Orena đang bận, thử lại sau nhé.",
                "zh-CN": "Orena 正忙，请稍后再试。",
            },
        ),
        "error.voice_unavailable": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Voice isn't available right now. Let's continue in text.",
                "vi": "Giọng nói tạm thời không dùng được. Mình tiếp tục bằng chữ nhé.",
                "zh-CN": "语音暂时不可用，我们先用文字继续。",
            },
        ),
        "error.internal": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "Something went wrong. Please try again.",
                "vi": "Orena gặp sự cố. Thử lại nhé.",
                "zh-CN": "出了点问题，请重试。",
            },
        ),
        "tool.get_due_review_summary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking your review queue", "vi": "Đang xem các từ cần ôn", "zh-CN": "正在查看复习队列"},
        ),
        "tool.get_due_vocabulary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Reading your due words", "vi": "Đang xem từ đến hạn", "zh-CN": "正在查看到期的词"},
        ),
        "tool.get_current_writing_evaluation": _entry(
            CopyLayer.INTERFACE,
            {"en": "Reading your writing feedback", "vi": "Đang xem nhận xét bài viết", "zh-CN": "正在查看写作反馈"},
        ),
        "result.get_due_review_summary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Due: {n}", "vi": "Đến hạn: {n}", "zh-CN": "到期：{n}"},
        ),
        "result.get_due_vocabulary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Words: {n}", "vi": "Số từ: {n}", "zh-CN": "词数：{n}"},
        ),
        "result.get_current_writing_evaluation": _entry(
            CopyLayer.INTERFACE,
            {"en": "Issues: {n}", "vi": "Điểm cần sửa: {n}", "zh-CN": "问题：{n}"},
        ),
        "tool.get_saved_word_state": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking your saved words", "vi": "Đang xem từ đã lưu", "zh-CN": "正在查看已保存的词"},
        ),
        "tool.get_word_detail": _entry(
            CopyLayer.INTERFACE,
            {"en": "Looking up the word", "vi": "Đang tra từ", "zh-CN": "正在查词"},
        ),
        "tool.get_writing_feedback_items": _entry(
            CopyLayer.INTERFACE,
            {"en": "Reading the feedback items", "vi": "Đang xem các điểm cần sửa", "zh-CN": "正在查看修改建议"},
        ),
        "tool.get_writing_history_summary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Reading your writing history", "vi": "Đang xem lịch sử bài viết", "zh-CN": "正在查看写作记录"},
        ),
        "result.get_saved_word_state": _entry(
            CopyLayer.INTERFACE,
            {"en": "Saved: {n}", "vi": "Đã lưu: {n}", "zh-CN": "已保存：{n}"},
        ),
        "tool.get_pronunciation_history": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking your speaking", "vi": "Đang xem các lần nói", "zh-CN": "正在查看口语记录"},
        ),
        "result.get_pronunciation_history": _entry(
            CopyLayer.INTERFACE,
            {"en": "Attempts: {n}", "vi": "Lần nói: {n}", "zh-CN": "录音：{n}"},
        ),
        "tool.get_pronunciation_attempt": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking this take", "vi": "Đang xem lần nói này", "zh-CN": "正在查看这次录音"},
        ),
        "result.get_pronunciation_attempt": _entry(
            CopyLayer.INTERFACE,
            {"en": "Flagged: {n}", "vi": "Được đánh dấu: {n}", "zh-CN": "被标记：{n}"},
        ),
        "tool.get_pronunciation_word_detail": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking the word", "vi": "Đang xem từ này", "zh-CN": "正在查看这个词"},
        ),
        "result.get_pronunciation_word_detail": _entry(
            CopyLayer.INTERFACE,
            {"en": "Words: {n}", "vi": "Từ: {n}", "zh-CN": "词：{n}"},
        ),
        "tool.get_current_listening_context": _entry(
            CopyLayer.INTERFACE,
            {"en": "Opening the lesson", "vi": "Đang mở bài nghe", "zh-CN": "正在打开听力课"},
        ),
        "result.get_current_listening_context": _entry(
            CopyLayer.INTERFACE,
            {"en": "Lessons: {n}", "vi": "Bài: {n}", "zh-CN": "课：{n}"},
        ),
        "tool.get_listening_attempt": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking your dictation", "vi": "Đang xem bài chép", "zh-CN": "正在查看听写记录"},
        ),
        "result.get_listening_attempt": _entry(
            CopyLayer.INTERFACE,
            {"en": "Lines: {n}", "vi": "Câu: {n}", "zh-CN": "句子：{n}"},
        ),
        "tool.get_current_reading_context": _entry(
            CopyLayer.INTERFACE,
            {"en": "Opening the text", "vi": "Đang mở bài đọc", "zh-CN": "正在打开阅读"},
        ),
        "result.get_current_reading_context": _entry(
            CopyLayer.INTERFACE,
            {"en": "Texts: {n}", "vi": "Bài đọc: {n}", "zh-CN": "文章：{n}"},
        ),
        "tool.get_reading_progress": _entry(
            CopyLayer.INTERFACE,
            {"en": "Checking your reading", "vi": "Đang xem các lần đọc", "zh-CN": "正在查看阅读记录"},
        ),
        "result.get_reading_progress": _entry(
            CopyLayer.INTERFACE,
            {"en": "Attempts: {n}", "vi": "Lần làm: {n}", "zh-CN": "作答：{n}"},
        ),
        "tool.get_grammar_point": _entry(
            CopyLayer.INTERFACE,
            {"en": "Opening the grammar point", "vi": "Đang mở điểm ngữ pháp", "zh-CN": "正在打开语法点"},
        ),
        "result.get_grammar_point": _entry(
            CopyLayer.INTERFACE,
            {"en": "Grammar points: {n}", "vi": "Điểm ngữ pháp: {n}", "zh-CN": "语法点：{n}"},
        ),
        "tool.search_grammar_points": _entry(
            CopyLayer.INTERFACE,
            {"en": "Searching grammar", "vi": "Đang tìm ngữ pháp", "zh-CN": "正在查找语法"},
        ),
        "result.search_grammar_points": _entry(
            CopyLayer.INTERFACE,
            {"en": "Matches: {n}", "vi": "Kết quả: {n}", "zh-CN": "结果：{n}"},
        ),
        "result.get_word_detail": _entry(
            CopyLayer.INTERFACE,
            {"en": "Entries: {n}", "vi": "Mục từ: {n}", "zh-CN": "词条：{n}"},
        ),
        "result.get_writing_feedback_items": _entry(
            CopyLayer.INTERFACE,
            {"en": "Issues: {n}", "vi": "Điểm cần sửa: {n}", "zh-CN": "问题：{n}"},
        ),
        "result.get_writing_history_summary": _entry(
            CopyLayer.INTERFACE,
            {"en": "Error types: {n}", "vi": "Loại lỗi: {n}", "zh-CN": "错误类型：{n}"},
        ),
        "result.unavailable": _entry(
            CopyLayer.INTERFACE,
            {"en": "Not available", "vi": "Chưa xem được", "zh-CN": "暂时无法查看"},
        ),
        "action.play_model": _entry(
            CopyLayer.INTERFACE,
            {"en": "Play model", "vi": "Nghe mẫu", "zh-CN": "播放示范"},
        ),
        "action.play_user": _entry(
            CopyLayer.INTERFACE,
            {"en": "Play my take", "vi": "Nghe lại giọng bạn", "zh-CN": "播放我的录音"},
        ),
        "action.say_again": _entry(
            CopyLayer.INTERFACE,
            {"en": "Say it again", "vi": "Nói lại", "zh-CN": "再说一遍"},
        ),
        "action.compare_with_model": _entry(
            CopyLayer.INTERFACE,
            {"en": "Compare", "vi": "So sánh với mẫu", "zh-CN": "与示范对比"},
        ),
        "action.save_word": _entry(
            CopyLayer.INTERFACE,
            {"en": "Save word", "vi": "Lưu từ", "zh-CN": "保存单词"},
        ),
        "action.add_word_to_collection": _entry(
            CopyLayer.INTERFACE,
            {"en": "Add to collection", "vi": "Thêm vào bộ sưu tập", "zh-CN": "加入收藏集"},
        ),
        "action.start_review": _entry(
            CopyLayer.INTERFACE,
            {"en": "Start review", "vi": "Ôn ngay", "zh-CN": "开始复习"},
        ),
        "action.start_targeted_drill": _entry(
            CopyLayer.INTERFACE,
            {"en": "Practice this", "vi": "Luyện phần này", "zh-CN": "专项练习"},
        ),
        "action.unsave_word": _entry(
            CopyLayer.INTERFACE,
            {"en": "Remove word", "vi": "Bỏ lưu từ", "zh-CN": "取消保存"},
        ),
        "navigate.home": _entry(
            CopyLayer.INTERFACE,
            {"en": "Home", "vi": "Trang chính", "zh-CN": "首页"},
        ),
        "navigate.library": _entry(
            CopyLayer.INTERFACE,
            {"en": "Library", "vi": "Thư viện", "zh-CN": "资料库"},
        ),
        "navigate.reading.library": _entry(
            CopyLayer.INTERFACE,
            {"en": "Reading library", "vi": "Thư viện đọc", "zh-CN": "阅读库"},
        ),
        "navigate.reading.workspace": _entry(
            CopyLayer.INTERFACE,
            {"en": "Open the text", "vi": "Mở bài đọc", "zh-CN": "打开文章"},
        ),
        "navigate.listening.library": _entry(
            CopyLayer.INTERFACE,
            {"en": "Listening library", "vi": "Thư viện nghe", "zh-CN": "听力库"},
        ),
        "navigate.listening.workspace": _entry(
            CopyLayer.INTERFACE,
            {"en": "Open the lesson", "vi": "Mở bài nghe", "zh-CN": "打开听力"},
        ),
        "navigate.listening.dictation": _entry(
            CopyLayer.INTERFACE,
            {"en": "Start dictation", "vi": "Chép chính tả", "zh-CN": "开始听写"},
        ),
        "navigate.speaking.library": _entry(
            CopyLayer.INTERFACE,
            {"en": "Speaking library", "vi": "Thư viện nói", "zh-CN": "口语库"},
        ),
        "navigate.speaking.workspace": _entry(
            CopyLayer.INTERFACE,
            {"en": "Open speaking", "vi": "Mở bài nói", "zh-CN": "打开口语练习"},
        ),
        "navigate.speaking.free_talk": _entry(
            CopyLayer.INTERFACE,
            {"en": "Free talk", "vi": "Nói tự do", "zh-CN": "自由对话"},
        ),
        "navigate.speaking.word_detail": _entry(
            CopyLayer.INTERFACE,
            {"en": "See this word", "vi": "Xem từ này", "zh-CN": "查看这个词"},
        ),
        "navigate.speaking.compare": _entry(
            CopyLayer.INTERFACE,
            {"en": "Compare", "vi": "So sánh với mẫu", "zh-CN": "与示范对比"},
        ),
        "navigate.writing.workspace": _entry(
            CopyLayer.INTERFACE,
            {"en": "Write", "vi": "Viết bài", "zh-CN": "写作"},
        ),
        "navigate.writing.review": _entry(
            CopyLayer.INTERFACE,
            {"en": "See feedback", "vi": "Xem nhận xét", "zh-CN": "查看反馈"},
        ),
        "navigate.writing.revision": _entry(
            CopyLayer.INTERFACE,
            {"en": "Revise", "vi": "Sửa bài", "zh-CN": "修改文章"},
        ),
        "navigate.vocabulary.my_language": _entry(
            CopyLayer.INTERFACE,
            {"en": "My Library", "vi": "Thư viện của tôi", "zh-CN": "我的书库"},
        ),
        "navigate.vocabulary.word": _entry(
            CopyLayer.INTERFACE,
            {"en": "Open word", "vi": "Mở từ", "zh-CN": "打开单词"},
        ),
        "navigate.vocabulary.review_due": _entry(
            CopyLayer.INTERFACE,
            {"en": "Review due words", "vi": "Ôn từ đến hạn", "zh-CN": "复习到期的词"},
        ),
        "navigate.grammar.catalog": _entry(
            CopyLayer.INTERFACE,
            {"en": "Grammar", "vi": "Ngữ pháp", "zh-CN": "语法"},
        ),
        "navigate.grammar.point": _entry(
            CopyLayer.INTERFACE,
            {"en": "Open pattern", "vi": "Mở mẫu ngữ pháp", "zh-CN": "打开语法点"},
        ),
        "navigate.progress": _entry(
            CopyLayer.INTERFACE,
            {"en": "Progress", "vi": "Tiến độ", "zh-CN": "学习进度"},
        ),
        "navigate.preferences": _entry(
            CopyLayer.INTERFACE,
            {"en": "Preferences", "vi": "Cài đặt", "zh-CN": "设置"},
        ),
        "navigate.preferences.agent_memory": _entry(
            CopyLayer.INTERFACE,
            {"en": "What Orena remembers", "vi": "Orena ghi nhớ gì", "zh-CN": "Orena 记住的内容"},
        ),
        "prompt.review_due": _entry(
            CopyLayer.INTERFACE,
            {"en": "Review due words", "vi": "Ôn từ đến hạn", "zh-CN": "复习到期的词"},
        ),
        "prompt.writing_feedback": _entry(
            CopyLayer.INTERFACE,
            {"en": "Where do I go wrong?", "vi": "Tôi hay sai chỗ nào?", "zh-CN": "我常错在哪里？"},
        ),
        "prompt.app_help": _entry(
            CopyLayer.INTERFACE,
            {"en": "What is this screen for?", "vi": "Màn này dùng để làm gì?", "zh-CN": "这个页面是做什么的？"},
        ),
        # Each place's name as the new UI shows it (its shell copy), so an answer names a screen the way
        # the learner reads it, never by an id or an English title.
        **{
            f"surface.{surface}": _entry(CopyLayer.INTERFACE, {"en": en, "vi": vi, "zh-CN": zh})
            for surface, (en, vi, zh) in {
                "home": ("Today", "Hôm nay", "今天"),
                "orena.home": ("Orena", "Orena", "Orena"),
                "library": ("Discover", "Khám phá", "发现"),
                "reading.library": ("Discover", "Khám phá", "发现"),
                "reading.workspace": ("Reader", "Đọc", "阅读"),
                "listening.library": ("Discover", "Khám phá", "发现"),
                "listening.workspace": ("Listening", "Nghe", "听力"),
                "listening.dictation": ("Dictation", "Chép chính tả", "听写"),
                "speaking.library": ("Practice Hub", "Luyện tập", "练习中心"),
                "speaking.workspace": ("Pronunciation", "Phát âm", "发音"),
                "speaking.free_talk": ("Free Talk", "Nói tự do", "自由说"),
                "speaking.word_detail": ("Compare with model", "So với mẫu", "与示范对比"),
                "speaking.compare": ("Compare with model", "So với mẫu", "与示范对比"),
                "writing.workspace": ("Writing", "Viết", "写作"),
                "writing.review": ("Writing", "Viết", "写作"),
                "writing.revision": ("Compare versions", "So sánh phiên bản", "版本对比"),
                "vocabulary.my_language": ("My Library", "Thư viện của tôi", "我的书库"),
                "vocabulary.word": ("Word", "Từ", "词语"),
                "vocabulary.review_due": ("Review", "Ôn tập", "复习"),
                "grammar.catalog": ("Grammar", "Ngữ pháp", "语法"),
                "grammar.point": ("Grammar", "Ngữ pháp", "语法"),
                "progress": ("Progress", "Tiến độ", "进度"),
                "preferences": ("Settings", "Cài đặt", "设置"),
                "preferences.agent_memory": ("Settings", "Cài đặt", "设置"),
            }.items()
        },
    }
)


def layer_language(layer: CopyLayer, *, interface: str, support: str) -> str:
    return interface if layer is CopyLayer.INTERFACE else support


def text(key: str, *, interface: str, support: str, **params: object) -> tuple[str, str]:
    """Return `(language, text)` for a key, read from its own layer's pack.

    `params` fill `{name}` placeholders (counts only; never learner content).
    """

    entry = CATALOG[key]
    language = layer_language(entry.layer, interface=interface, support=support)
    if language not in entry.texts:
        language = FALLBACK_LANGUAGE
    words = entry.texts[language]
    return language, words.format(**params) if params else words
