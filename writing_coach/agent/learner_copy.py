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
        # The one sentence that offers a proposed button (agent/honesty.py): the server's, never the model's,
        # in the interface layer like the button it names, and in the learner's address pair (human direction
        # 2026-09-28). Built from the action in hand (label, and the word it names): what tapping does.
        "offer.save_word": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} to add {text} to your words.", "vi": "Bấm {label} để thêm {text} vào từ vựng của {user}.",
             "zh-CN": "点击“{label}”，把{text}加入{user}的词汇。"},
        ),
        "offer.unsave_word": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} to remove {text} from your words.", "vi": "Bấm {label} để bỏ {text} khỏi từ vựng của {user}.",
             "zh-CN": "点击“{label}”，把{text}从{user}的词汇中移除。"},
        ),
        "offer.add_word_to_collection": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} to add {text} to the collection.", "vi": "Bấm {label} để thêm {text} vào bộ sưu tập.",
             "zh-CN": "点击“{label}”，把{text}加入收藏。"},
        ),
        "offer.start_review": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} to start the review.", "vi": "Bấm {label} để bắt đầu ôn.", "zh-CN": "点击“{label}”开始复习。"},
        ),
        "offer.navigate": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} to open it.", "vi": "Bấm {label} để mở.", "zh-CN": "点击“{label}”打开。"},
        ),
        "offer.action": _entry(
            CopyLayer.INTERFACE,
            {"en": "Tap {label} if you want to.", "vi": "Bấm {label} nếu {user} muốn.", "zh-CN": "需要的话，点击“{label}”。"},
        ),
        # Said when every sentence of an answer claimed Orena had changed something (agent/honesty.py).
        "honesty.nothing_done": _entry(
            CopyLayer.SUPPORT,
            {"en": "I haven't changed anything.", "vi": "{self_cap} chưa thay đổi gì cả.", "zh-CN": "{self}没有做任何更改。"},
        ),
        # Said when the learner changed or cancelled a coach note and none was changed, even when asked again
        # (agent/notes.py): the truth, never "there is no such note".
        # A question about the learner's own learning that no record was read for (dogfood gate 3.1).
        "evidence.unread": _entry(
            CopyLayer.SUPPORT,
            {"en": "I couldn't read your learning records just now, so I can't say that yet. Please ask again in a moment.",
             "vi": "{self_cap} chưa đọc được dữ liệu học của {user} lúc này, nên chưa thể kết luận. {user_cap} hỏi lại sau một chút nhé.",
             "zh-CN": "{self}现在没能读取{user}的学习记录，所以还不能下结论。请稍后再问一次。"},
        ),
        "notes.unchanged": _entry(
            CopyLayer.SUPPORT,
            {"en": "I haven't changed your notes yet. Could you say which one to change or forget?",
             "vi": "{self_cap} chưa sửa hay xoá ghi chú nào của {user}. {user_cap} nói rõ ghi chú nào cần sửa hoặc xoá nhé?",
             "zh-CN": "{self}还没有修改或删除{user}的笔记。请告诉{self}要修改或删除哪一条？"},
        ),
        # A keep request typed without Vietnamese diacritics (agent/notes.py): asked back, never refused in silence;
        # kept only when the learner taps `notes.keep_label` (human direction 2026-10-04).
        "notes.confirm": _entry(
            CopyLayer.SUPPORT,
            {"en": "Do you want me to remember: “{text}”?", "vi": "{user_cap} muốn {self} ghi nhớ: “{text}”?",
             "zh-CN": "{user}想让{self}记住：“{text}”吗？"},
        ),
        # The button's label is the learner's next message (contract §4): agent/notes.py reads it back.
        "notes.keep_label": _entry(
            CopyLayer.INTERFACE,
            {"en": "Remember: {text}", "vi": "Ghi nhớ: {text}", "zh-CN": "记住：{text}"},
        ),
        # The wish is too long to fit on a button: the learner is asked to type it with its marks.
        "notes.retype": _entry(
            CopyLayer.SUPPORT,
            {"en": "Do you want me to remember this? Please type it again with its accents.",
             "vi": "{user_cap} muốn {self} ghi nhớ điều này? {user_cap} gõ lại có dấu giúp {self} nhé.",
             "zh-CN": "{user}想让{self}记住这件事吗？请带声调符号再输入一次。"},
        ),
        # Tapped to keep a note, and the model kept none even when asked again.
        "notes.not_kept": _entry(
            CopyLayer.SUPPORT,
            {"en": "I haven't kept it yet. Could you tap it again?",
             "vi": "{self_cap} chưa ghi nhớ được. {user_cap} bấm lại giúp {self} nhé?",
             "zh-CN": "{self}还没有记下。请再点一次？"},
        ),
        # The opening greeting when the model's names no fact of the snapshot (agent/greeting.py): one fact, from
        # the snapshot, never a generic line (human direction 2026-09-28).
        "opening.due": _entry(
            CopyLayer.SUPPORT,
            {"en": "Hi! You have {n} words due for review today.", "vi": "Chào {user}! Hôm nay {user} có {n} từ đến hạn ôn.",
             "zh-CN": "你好！今天{user}有{n}个词需要复习。"},
        ),
        "opening.activity": _entry(
            CopyLayer.SUPPORT,
            {"en": "Hi! In the last 30 days: {n} × {what} in {skill}.",
             "vi": "Chào {user}! 30 ngày qua {user} có {n} {what} ở phần {skill}.",
             "zh-CN": "你好！最近30天，{user}在{skill}有{n}次{what}。"},
        ),
        "opening.empty": _entry(
            CopyLayer.SUPPORT,
            {"en": "Hi! Nothing has been recorded in the last 30 days yet.",
             "vi": "Chào {user}! 30 ngày qua chưa có hoạt động nào được ghi lại.",
             "zh-CN": "你好！最近30天还没有学习记录。"},
        ),
        "opening.unread": _entry(
            CopyLayer.SUPPORT,
            {"en": "Hi! I can't read your progress right now.", "vi": "Chào {user}! {self_cap} chưa đọc được tiến độ lúc này.",
             "zh-CN": "你好！{self}现在读不到{user}的学习进度。"},
        ),
        "identity.who": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "I'm Orena, your AI learning assistant and personal coach in this app. "
                "Ask me about this screen, your progress, or what to practise next.",
                "vi": "{self_cap} là Orena, trợ lý học tập AI và huấn luyện viên riêng của {user} trong ứng dụng này. "
                "{user_cap} có thể hỏi {self} về màn hình này, tiến độ học, hay nên luyện gì tiếp.",
                "zh-CN": "{self}是 Orena，{user}在这个应用里的 AI 学习助手和私人教练。"
                "{user}可以问{self}这个页面的用法、{user}的学习进度，或者接下来该练什么。",
            },
        ),
        "identity.model": _entry(
            CopyLayer.SUPPORT,
            {
                "en": "I'm Orena, your AI learning assistant and personal coach. "
                "The AI model behind me is chosen by Orena and may change, so I don't name one.",
                "vi": "{self_cap} là Orena, trợ lý học tập AI và huấn luyện viên riêng của {user}. "
                "Mô hình AI phía sau do Orena chọn và có thể thay đổi, nên {self} không nêu tên mô hình.",
                "zh-CN": "{self}是 Orena，{user}的 AI 学习助手和私人教练。背后的 AI 模型由 Orena 选择，可能会更换，所以{self}不说具体名称。",
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
        "tool.build_learning_snapshot": _entry(
            CopyLayer.INTERFACE,
            {"en": "Looking at your learning", "vi": "Đang xem việc học của bạn", "zh-CN": "正在查看你的学习情况"},
        ),
        "result.build_learning_snapshot": _entry(
            CopyLayer.INTERFACE,
            {"en": "Skills with records: {n}", "vi": "Kỹ năng có dữ liệu: {n}", "zh-CN": "有记录的技能：{n}"},
        ),
        "tool.get_learning_weaknesses": _entry(
            CopyLayer.INTERFACE,
            {"en": "Looking for patterns", "vi": "Đang tìm điểm hay lặp lại", "zh-CN": "正在查找反复出现的问题"},
        ),
        "result.get_learning_weaknesses": _entry(
            CopyLayer.INTERFACE,
            {"en": "Skills with patterns: {n}", "vi": "Kỹ năng có điểm lặp lại: {n}", "zh-CN": "有反复问题的技能：{n}"},
        ),
        "tool.get_recommended_next_activities": _entry(
            CopyLayer.INTERFACE,
            {"en": "Choosing what's next", "vi": "Đang chọn việc tiếp theo", "zh-CN": "正在选择下一步"},
        ),
        "result.get_recommended_next_activities": _entry(
            CopyLayer.INTERFACE,
            {"en": "Next steps: {n}", "vi": "Bước tiếp theo: {n}", "zh-CN": "下一步：{n}"},
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
        # Place names are the UI's, read from surfaces.json (agent/surfaces.py, contract v5 §6.2).
    }
)


def layer_language(layer: CopyLayer, *, interface: str, support: str) -> str:
    return interface if layer is CopyLayer.INTERFACE else support


def language_of(key: str, *, interface: str, support: str) -> str:
    """The pack a key is read from for this locale (its layer's language, or the fallback)."""

    entry = CATALOG[key]
    language = layer_language(entry.layer, interface=interface, support=support)
    return language if language in entry.texts else FALLBACK_LANGUAGE


def address_terms(language: str, address: object = None) -> dict[str, str]:
    """The `{self}` / `{user}` slots (and their sentence-initial `_cap` forms) for copy in `language`: the learner's
    address when it is for that language (contract v5 §5.6), that language's default otherwise - so a text with
    slots reads exactly as the unaddressed one when nothing was chosen."""

    from writing_coach.agent.address import DEFAULTS, capitalised

    self_term, user_term = DEFAULTS.get(language, DEFAULTS[FALLBACK_LANGUAGE])
    if address is not None and getattr(address, "lang", None) == language:
        self_term = getattr(address, "self_term", None) or self_term
        user_term = getattr(address, "user_term", None) or user_term
    return {"self": self_term, "self_cap": capitalised(self_term), "user": user_term, "user_cap": capitalised(user_term)}


def text(key: str, *, interface: str, support: str, address: object = None, **params: object) -> tuple[str, str]:
    """Return `(language, text)` for a key, read from its own layer's pack.

    `params` fill `{name}` placeholders (counts, labels, the word an action names). `address` is the turn's
    §5.6 address: it fills `{self}` / `{user}` only in copy of its own language.
    """

    entry = CATALOG[key]
    language = language_of(key, interface=interface, support=support)
    words = entry.texts[language]
    return language, words.format(**{**address_terms(language, address), **params})
