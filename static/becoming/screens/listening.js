import {api} from '../api.js';
import {go} from '../router.js';
import {state,supportLanguage} from '../store.js';
import {esc,showDialog,toast} from '../components/primitives.js';
import {connectMediaPlayer,disconnectMediaPlayer,mediaPlayer,playbackAvailable,posterUrl,replaySegment,seekBy,toggleMute,togglePlayback,setPlaybackRate as setMediaPlaybackRate} from '../components/media-player.js';
import {t,uiLocale} from '../domain/i18n.js';
import {countUnits} from '../language.js';
import {oIcon} from '../orena/icons.js';
import {installSelectEnhancements} from '../components/select-field.js';
import {createLocalAudioRecorder,localAudioRecordingSupported} from '../components/audio-recorder.js';
import {transcriptTokens} from '../domain/transcript-tokens.js';
import {buildTranscriptDisplayUnits,displayUnitContains,displayUnitMeaning} from '../domain/transcript-display-units.js';
import {openDictionary} from '../components/dictionary.js';
import {activeCanonicalSegment} from '../domain/transcript-playback.js';
import {applyPlayingSegment} from '../components/interactive-transcript.js';
import {
  MAX_LISTENING_EVALUATION_UNITS,
  MAX_LISTENING_RECONSTRUCTION_CHARS,
  advanceListeningPracticeHint,
  createListeningPracticeSession,
  evaluateListeningReconstruction,
  listeningReconstructionDiff,
  listeningPracticeSummary,
  listeningUnits,
  restoreListeningPracticeProgress,
  recordListeningPracticeAttempt,
  retryListeningPracticeSegment,
  revealListeningPracticeAnswer,
  selectListeningPracticeSegment,
  setListeningPracticeDraft,
} from '../domain/listening-practice.js';
import {
  createShadowingPracticeSession,
  recordShadowingPracticeRound,
  restoreShadowingPracticeProgress,
  selectShadowingPracticeSegment,
  shadowingPracticeSummary,
} from '../domain/shadowing-practice.js';
import {getSharedMediaSession,selectSharedMediaSegment,setSharedMediaMode,setSharedMediaSession} from '../domain/shared-media-session.js';
import {clearPendingMediaImport,getPendingMediaImport,setPendingMediaImport} from '../domain/media-import-resume.js';
import {listMediaLessons,rememberMediaLesson,takeLessonAutostartContext,resumableLesson} from '../domain/media-lesson-history.js';
import {addListenedSeconds,listenedSeconds,listeningGoals,saveListeningGoal} from '../domain/listening-habit.js';
import {skillMasthead} from '../components/skill-masthead.js';

const LIBRARY_COPY={
  en:{purpose:'Choose something interesting and start listening now.',discover:'Discover',myMedia:'My media',recommended:'Recommended for you',quick:'Quick listening',dictation:'Dictation practice',beginner:'Beginner',newContent:'New content',topics:'Topics',allTopics:'All topics',allLevels:'All levels',open:'Start lesson',loading:'Preparing your Listening library…',empty:'No curated lessons match these filters yet.',failed:'The Listening library could not be loaded.',retry:'Try again',duration:'Duration',modes:'practice modes',addOwn:'Add your own media',addOwnLead:'Bring a supported external video into the same Listening workspace and practice modes.',backLibrary:'Back to Library',continue:'Continue learning',level:'Level',sourceRights:'Source & rights',hintCount:'Word / character count',hintFirst:'First letter / character',hintVocab:'Difficult vocabulary',hintUsed:'Hint used',correct:'Correct',missing:'Missing',wrong:'Wrong',extra:'Extra'},
  vi:{purpose:'Chọn một nội dung thú vị và bắt đầu luyện nghe ngay.',discover:'Khám phá',myMedia:'Media của tôi',recommended:'Đề xuất cho bạn',quick:'Luyện nghe nhanh',dictation:'Luyện chính tả',beginner:'Cơ bản',newContent:'Nội dung mới',topics:'Chủ đề',allTopics:'Tất cả chủ đề',allLevels:'Mọi trình độ',open:'Bắt đầu bài',loading:'Đang chuẩn bị thư viện Listening…',empty:'Chưa có bài curated phù hợp với bộ lọc này.',failed:'Không thể tải thư viện Listening.',retry:'Thử lại',duration:'Thời lượng',modes:'chế độ luyện tập',addOwn:'Thêm media của bạn',addOwnLead:'Đưa video ngoài được hỗ trợ vào cùng workspace và các chế độ luyện nghe.',backLibrary:'Về Thư viện',continue:'Học tiếp',level:'Trình độ',sourceRights:'Nguồn & bản quyền',hintCount:'Số từ / chữ',hintFirst:'Chữ cái / chữ đầu',hintVocab:'Từ khó',hintUsed:'Đã dùng gợi ý',correct:'Đúng',missing:'Thiếu',wrong:'Sai',extra:'Thừa'},
  zh:{purpose:'选择有趣的内容，马上开始听力练习。',discover:'发现',myMedia:'我的媒体',recommended:'为你推荐',quick:'快速听力',dictation:'听写练习',beginner:'初级',newContent:'新内容',topics:'主题',allTopics:'全部主题',allLevels:'全部等级',open:'开始课程',loading:'正在准备听力内容库…',empty:'暂时没有符合筛选条件的精选课程。',failed:'无法加载听力内容库。',retry:'重试',duration:'时长',modes:'种练习模式',addOwn:'添加自己的媒体',addOwnLead:'把受支持的外部视频导入同一个听力工作区和练习模式。',backLibrary:'返回内容库',continue:'继续学习',level:'等级',sourceRights:'来源与授权',hintCount:'词数 / 字数',hintFirst:'首字母 / 首字',hintVocab:'难词',hintUsed:'已使用提示',correct:'正确',missing:'遗漏',wrong:'错误',extra:'多余'},
};
Object.assign(LIBRARY_COPY.en,{tags:'Tags',allTags:'All tags',popular:'Popular',source:'Source',reviewedLevel:'Editor reviewed',correctTranscript:'Correct transcript',nextSegment:'Next segment',shadowThis:'Shadow this segment',saveWord:'Save difficult word',wordSaved:'Saved to Active Recall',saveFailed:'Could not save this word',replaySlow:'Replay slowly'});
Object.assign(LIBRARY_COPY.vi,{tags:'Thẻ nội dung',allTags:'Tất cả thẻ',popular:'Phổ biến',source:'Nguồn',reviewedLevel:'Đã biên tập duyệt',correctTranscript:'Transcript đúng',nextSegment:'Đoạn tiếp theo',shadowThis:'Shadow đoạn này',saveWord:'Lưu từ khó',wordSaved:'Đã lưu vào Active Recall',saveFailed:'Không thể lưu từ này',replaySlow:'Nghe chậm'});
Object.assign(LIBRARY_COPY.zh,{tags:'标签',allTags:'全部标签',popular:'热门',source:'来源',reviewedLevel:'编辑已审核',correctTranscript:'正确原文',nextSegment:'下一句',shadowThis:'跟读这一句',saveWord:'保存难词',wordSaved:'已保存到主动复习',saveFailed:'无法保存这个词',replaySlow:'慢速重听'});
Object.assign(LIBRARY_COPY.en,{secMovie:'Movies & animation',secDaily:'Daily conversations',secStories:'Stories',secPodcast:'Podcasts & interviews',secScience:'Science & technology',secCulture:'Culture',secKids:'Kids & family',secShadowing:'Shadowing practice',secAudio:'Audio practice',intermediate:'Intermediate',advanced:'Advanced',needsReview:'Needs review',videoLesson:'Video',audioLesson:'Audio'});
Object.assign(LIBRARY_COPY.vi,{secMovie:'Phim & hoạt hình',secDaily:'Hội thoại hằng ngày',secStories:'Câu chuyện',secPodcast:'Podcast & phỏng vấn',secScience:'Khoa học & công nghệ',secCulture:'Văn hóa',secKids:'Trẻ em & gia đình',secShadowing:'Luyện Shadowing',secAudio:'Luyện nghe audio',intermediate:'Trung cấp',advanced:'Nâng cao',needsReview:'Cần rà soát',videoLesson:'Video',audioLesson:'Audio'});
Object.assign(LIBRARY_COPY.zh,{secMovie:'电影与动画',secDaily:'日常对话',secStories:'故事',secPodcast:'播客与访谈',secScience:'科学与科技',secCulture:'文化',secKids:'儿童与家庭',secShadowing:'跟读练习',secAudio:'音频练习',intermediate:'中级',advanced:'高级',needsReview:'待复核',videoLesson:'视频',audioLesson:'音频'});
const libraryText=()=>LIBRARY_COPY[uiLocale()]||LIBRARY_COPY.en;
const LIBRARY_TERM_LABELS={
  en:{'daily-life':'Daily life',travel:'Travel',conversations:'Conversations',culture:'Culture',follow:'Listen',active:'Active listening',dictation:'Dictation',shadowing:'Shadowing'},
  vi:{'daily-life':'Đời sống hằng ngày',travel:'Du lịch',conversations:'Hội thoại',culture:'Văn hóa',follow:'Nghe',active:'Nghe chủ động',dictation:'Chính tả',shadowing:'Shadowing'},
  zh:{'daily-life':'日常生活',travel:'旅行',conversations:'对话',culture:'文化',follow:'听力',active:'主动听力',dictation:'听写',shadowing:'跟读'},
};
Object.assign(LIBRARY_TERM_LABELS.en,{listen:'Listen',science:'Science',technology:'Technology'});
Object.assign(LIBRARY_TERM_LABELS.vi,{listen:'Nghe',science:'Khoa học',technology:'Công nghệ'});
Object.assign(LIBRARY_TERM_LABELS.zh,{listen:'听力',science:'科学',technology:'科技'});
const libraryTerm=value=>(LIBRARY_TERM_LABELS[uiLocale()]||LIBRARY_TERM_LABELS.en)[value]||String(value||'').replaceAll('-',' ');
const isPracticeMode=mode=>mode==='active'||mode==='dictation';

const COPY={
  en:{
  v2:{
    kicker:'LISTENING PRACTICE',
    headline1:'Sharpen your ear.',headline2:'Understand the world.',
    lead:'Listen with intention. Catch every nuance. Make it yours.',
    focusMode:'Focus mode',leaveFocus:'Leave focus mode',
    followSub:'Listen & read along',activeSub:'Understand deeply',shadowSub:'Speak in sync',
    currentSegment:'Current segment',revealMeaning:'Reveal meaning',
    preparing:'Translation preparing…',
    preparingBody:'The meaning is still being prepared. The original transcript is ready to use now.',
    hiddenBody:'The meaning is ready. Reveal it when you want it.',
    vocabFocus:'Vocabulary focus',
    vocabFocusEmpty:'No word in this segment is in your library yet.',
    vocabFocusNote:'These are words you have already saved. Nothing else in the line is classified.',
    listeningGoal:'Listening goal',daily:'Daily goal',weekly:'Weekly goal',
    minutes:'min',editGoals:'Edit goals',
    goalTip:'Minutes of playback this device has actually counted while a lesson was playing. It is not synced anywhere.',
    goalPrompt:'How many minutes a day do you want to listen?',
    sourceVideo:'Source video',viewOnProvider:'Open the source',
    savedLessons:'Saved lessons',viewAll:'View all',noSaved:'Lessons you prepare appear here.',newLesson:'Add a video',
    subtitles:'Subtitles',speed:'Speed',abLoop:'AB loop',shortcutsLabel:'Shortcuts',
    loopSetA:'Set loop start',loopSetB:'Set loop end',loopClear:'Clear loop',
    loopArmed:'Loop start set. Play on and set the end.',loopOn:'Looping this stretch.',loopOff:'Loop cleared.',
    savedWord:'Saved word',
  },shortcuts:'Shortcuts',shortcutsTitle:'Keyboard shortcuts',wordTiming:'Word timing',vocabulary:'Vocabulary',notes:'Notes',notesPlaceholder:'Your notes for this lesson stay on this device.',vocabularyEmpty:'Words you save from a review appear here.',download:'Download',hidePlayer:'Hide player',showPlayer:'Show player',jumpPlaying:'Jump to what is playing',skipBack:'Skip back',skipForward:'Skip forward',mute:'Mute',unmute:'Unmute',words:'words',listen:'LISTEN · FOLLOW',title:'HEAR THE IDEA, ONE MOMENT AT A TIME.',lead:'Bring an external video into one shared media lesson. Watch, follow the original words, read the meaning when available, and replay a sentence.',url:'Video URL',placeholder:'https://www.youtube.com/watch?v=…',prepare:'Import / Prepare lesson',preparingMeaning:'Preparing the meaning… the original transcript is ready to use now.',showGroup:'Show',skillName:'Listen',skillStat:'lessons ready',recentTitle:'Continue a lesson',needTitle:'What works',need1:'A YouTube link, pasted straight from the address bar.',need2:'The video must already have captions — without them there is nothing to follow.',need3:'Spoken in the language you are studying.',retryTranslation:'Retry preparation',validating:'Checking the URL…',processing:'Preparing lesson…',translationFailed:'Meaning could not be prepared. Retry preparation to start this lesson.',original:'Original transcript',meaning:'Meaning',unavailable:'Meaning is not available yet.',notRequired:'Translation is not required for the selected support language.',translationUnavailable:'Meaning could not be generated right now. Continue with the original transcript.',translationTooLarge:'This lesson is too large for automatic meaning generation. Continue with the original transcript.',generatedTranscript:'This transcript was generated automatically and may contain mistakes.',transcriptMissing:'This video has no usable transcript.',unsupported:'This video source is not supported.',malformedUrl:'Enter a valid public media URL.',unsupportedProvider:'This media provider is not supported yet.',mediaUnavailable:'This media is private or unavailable.',providerTimeout:'The media provider did not respond in time. Please try again.',providerFailure:'The media provider could not prepare this lesson. Please try again.',unsupportedSourceLanguage:'This media language is not supported yet.',invalidTargetLanguage:'Choose a valid support language.',failed:'The lesson could not be prepared.',previous:'Previous segment',next:'Next segment',replay:'Replay',speed:'Speed',select:'Select a transcript segment to replay it.',shadow:'Shadow this',shared:'Shadowing reuses this same media and segment. No separate import is needed.',playback:'Playback is unavailable for this source.'},
  vi:{
  v2:{
    kicker:'LUYỆN NGHE',
    headline1:'Luyện tai nghe.',headline2:'Hiểu được thế giới.',
    lead:'Nghe có chủ đích. Bắt từng sắc thái. Biến nó thành của mình.',
    focusMode:'Chế độ tập trung',leaveFocus:'Thoát chế độ tập trung',
    followSub:'Nghe và đọc theo',activeSub:'Hiểu sâu',shadowSub:'Nói cùng nhịp',
    currentSegment:'Đoạn hiện tại',revealMeaning:'Hiện nghĩa',
    preparing:'Đang chuẩn bị bản dịch…',
    preparingBody:'Phần nghĩa vẫn đang được chuẩn bị. Transcript gốc thì đã dùng được ngay.',
    hiddenBody:'Phần nghĩa đã sẵn sàng. Hiện ra khi bạn muốn.',
    vocabFocus:'Từ trọng tâm',
    vocabFocusEmpty:'Chưa từ nào trong đoạn này có trong thư viện của bạn.',
    vocabFocusNote:'Đây là những từ bạn đã lưu. Phần còn lại của câu không được phân loại.',
    listeningGoal:'Mục tiêu nghe',daily:'Mỗi ngày',weekly:'Mỗi tuần',
    minutes:'phút',editGoals:'Đổi mục tiêu',
    goalTip:'Số phút phát mà thiết bị này thật sự đếm được khi bài đang chạy. Không đồng bộ đi đâu cả.',
    goalPrompt:'Mỗi ngày bạn muốn nghe bao nhiêu phút?',
    sourceVideo:'Nguồn video',viewOnProvider:'Mở nguồn',
    savedLessons:'Bài đã lưu',viewAll:'Xem tất cả',noSaved:'Bài bạn chuẩn bị sẽ hiện ở đây.',newLesson:'Thêm video',
    subtitles:'Phụ đề',speed:'Tốc độ',abLoop:'Lặp AB',shortcutsLabel:'Phím tắt',
    loopSetA:'Đặt điểm đầu',loopSetB:'Đặt điểm cuối',loopClear:'Xoá vòng lặp',
    loopArmed:'Đã đặt điểm đầu. Nghe tiếp rồi đặt điểm cuối.',loopOn:'Đang lặp đoạn này.',loopOff:'Đã xoá vòng lặp.',
    savedWord:'Từ đã lưu',
  },shortcuts:'Phím tắt',shortcutsTitle:'Phím tắt bàn phím',wordTiming:'Bám theo từ',vocabulary:'Từ vựng',notes:'Ghi chú',notesPlaceholder:'Ghi chú cho bài học này chỉ lưu trên thiết bị.',vocabularyEmpty:'Những từ bạn lưu từ phần nhận xét sẽ hiện ở đây.',download:'Tải về',hidePlayer:'Ẩn video',showPlayer:'Hiện video',jumpPlaying:'Nhảy tới chỗ đang phát',skipBack:'Lùi',skipForward:'Tiến',mute:'Tắt tiếng',unmute:'Bật tiếng',words:'từ',listen:'NGHE · THEO DÕI',title:'NGHE TỪNG Ý, THEO TỪNG KHOẢNH KHẮC.',lead:'Đưa video bên ngoài vào một bài học media dùng chung. Xem, theo dõi lời gốc, đọc nghĩa khi có và nghe lại từng câu.',url:'URL video',placeholder:'https://www.youtube.com/watch?v=…',prepare:'Nhập / Chuẩn bị bài học',preparingMeaning:'Đang chuẩn bị phần nghĩa… transcript gốc đã dùng được ngay.',showGroup:'Hiển thị',skillName:'Nghe',skillStat:'bài đã chuẩn bị',recentTitle:'Học tiếp một bài',needTitle:'Video thế nào thì dùng được',need1:'Một đường dẫn YouTube, dán thẳng từ thanh địa chỉ.',need2:'Video phải có sẵn phụ đề — không có phụ đề thì không có gì để theo dõi.',need3:'Nội dung nói bằng ngôn ngữ bạn đang học.',retryTranslation:'Thử chuẩn bị lại',validating:'Đang kiểm tra URL…',processing:'Đang chuẩn bị bài học…',translationFailed:'Chưa thể chuẩn bị phần nghĩa. Hãy thử lại để bắt đầu bài học.',original:'Transcript gốc',meaning:'Nghĩa',unavailable:'Bản dịch nghĩa chưa có.',notRequired:'Không cần bản dịch cho ngôn ngữ hỗ trợ đã chọn.',translationUnavailable:'Hiện chưa thể tạo phần nghĩa. Bạn vẫn có thể tiếp tục với transcript gốc.',translationTooLarge:'Bài học này quá lớn để tự động tạo phần nghĩa. Bạn vẫn có thể tiếp tục với transcript gốc.',generatedTranscript:'Transcript này được tạo tự động và có thể có sai sót.',transcriptMissing:'Video này không có transcript phù hợp.',unsupported:'Nguồn video này chưa được hỗ trợ.',malformedUrl:'Hãy nhập URL media công khai hợp lệ.',unsupportedProvider:'Nhà cung cấp media này chưa được hỗ trợ.',mediaUnavailable:'Media này đang riêng tư hoặc không khả dụng.',providerTimeout:'Nhà cung cấp media không phản hồi kịp thời. Vui lòng thử lại.',providerFailure:'Nhà cung cấp media không thể chuẩn bị bài học này. Vui lòng thử lại.',unsupportedSourceLanguage:'Ngôn ngữ của media này chưa được hỗ trợ.',invalidTargetLanguage:'Hãy chọn ngôn ngữ hỗ trợ hợp lệ.',failed:'Không thể chuẩn bị bài học.',previous:'Đoạn trước',next:'Đoạn sau',replay:'Nghe lại',speed:'Tốc độ',select:'Chọn một đoạn transcript để nghe lại.',shadow:'Shadow câu này',shared:'Shadowing dùng lại chính media và đoạn này, không cần nhập lại video.',playback:'Không thể phát nguồn này.'},
  zh:{
  v2:{
    kicker:'听力练习',
    headline1:'练出你的耳朵。',headline2:'听懂这个世界。',
    lead:'带着目的去听，抓住每一处细微差别，把它变成你自己的。',
    focusMode:'专注模式',leaveFocus:'退出专注模式',
    followSub:'边听边读',activeSub:'深入理解',shadowSub:'同步跟读',
    currentSegment:'当前句段',revealMeaning:'显示释义',
    preparing:'正在准备释义…',
    preparingBody:'释义还在准备中。原文字幕现在已经可以使用。',
    hiddenBody:'释义已经准备好，想看的时候再打开。',
    vocabFocus:'重点词汇',
    vocabFocusEmpty:'这一句里还没有你词库中的词。',
    vocabFocusNote:'这些是你已经保存过的词。句中其他内容没有做任何分类。',
    listeningGoal:'听力目标',daily:'每日目标',weekly:'每周目标',
    minutes:'分钟',editGoals:'修改目标',
    goalTip:'本设备在课程播放时真实计到的分钟数，不会同步到任何地方。',
    goalPrompt:'你每天想听多少分钟？',
    sourceVideo:'视频来源',viewOnProvider:'打开来源',
    savedLessons:'已保存课程',viewAll:'查看全部',noSaved:'你准备的课程会出现在这里。',newLesson:'添加视频',
    subtitles:'字幕',speed:'速度',abLoop:'AB 循环',shortcutsLabel:'快捷键',
    loopSetA:'设置起点',loopSetB:'设置终点',loopClear:'清除循环',
    loopArmed:'起点已设置，继续播放后设置终点。',loopOn:'正在循环这一段。',loopOff:'循环已清除。',
    savedWord:'已保存的词',
  },shortcuts:'快捷键',shortcutsTitle:'键盘快捷键',wordTiming:'逐词对齐',vocabulary:'词汇',notes:'笔记',notesPlaceholder:'本课笔记仅保存在此设备上。',vocabularyEmpty:'你在点评中保存的词会出现在这里。',download:'下载',hidePlayer:'隐藏视频',showPlayer:'显示视频',jumpPlaying:'跳到正在播放处',skipBack:'后退',skipForward:'前进',mute:'静音',unmute:'取消静音',words:'词',listen:'听力 · 跟随',title:'逐句听见意思。',lead:'把外部视频导入一个共享媒体课程。观看视频、跟随原文、在可用时阅读释义，并重听每个句子。',url:'视频网址',placeholder:'https://www.youtube.com/watch?v=…',prepare:'导入 / 准备课程',preparingMeaning:'正在准备释义……原文字幕现在已可使用。',showGroup:'显示',skillName:'听力',skillStat:'已准备课程',recentTitle:'继续一课',needTitle:'什么样的视频可用',need1:'一个 YouTube 链接，直接从地址栏粘贴。',need2:'视频必须已有字幕 —— 没有字幕就无法跟读。',need3:'使用你正在学习的语言。',retryTranslation:'重试准备',validating:'正在检查网址…',processing:'正在准备课程…',translationFailed:'暂时无法准备释义。请重试准备后开始课程。',original:'原文字幕',meaning:'释义',unavailable:'释义暂时不可用。',notRequired:'所选辅助语言不需要翻译。',translationUnavailable:'目前无法生成释义。你仍可继续使用原文字幕。',translationTooLarge:'本课内容过大，当前无法自动生成释义。你仍可继续使用原文字幕。',generatedTranscript:'此字幕由系统自动生成，可能有误。',transcriptMissing:'这个视频没有可用字幕。',unsupported:'暂不支持这个视频来源。',malformedUrl:'请输入有效的公开视频网址。',unsupportedProvider:'暂不支持这个媒体提供方。',mediaUnavailable:'该媒体为私密内容或暂不可用。',providerTimeout:'媒体提供方响应超时，请重试。',providerFailure:'媒体提供方无法准备本课，请重试。',unsupportedSourceLanguage:'暂不支持这个媒体语言。',invalidTargetLanguage:'请选择有效的辅助语言。',failed:'无法准备课程。',previous:'上一句',next:'下一句',replay:'重听',speed:'速度',select:'选择一段字幕后重听。',shadow:'跟读这句',shared:'跟读直接复用同一媒体和句段，不需要再次导入视频。',playback:'这个来源暂时无法播放。'},
};
const ACTIVE_COPY={
  en:{follow:'Follow',active:'Active',mode:'Listening mode',activeUnavailable:'Active Listening and Shadowing need usable provider playback.',practice:'Active Listening',prompt:'Type what you heard',check:'Check answer',reveal:'Reveal answer',retry:'Retry',yourAnswer:'Your answer',textMatch:'Text match',exact:'Exact match',close:'Close match',tryAgain:'Try again',disclaimer:'Text match compares your reconstruction with this transcript. It is not a proficiency score.',progress:'Session practice',practiced:'Practiced',exactCount:'Exact',average:'Average best text match',attempts:'Checked attempts',revealed:'Revealed only',segment:'Segment',answerEmpty:'Type what you heard before checking.',answerTooLarge:'Your reconstruction is too long to check safely.',segmentTooLarge:'This transcript segment is too large to check safely. Follow mode remains available.',meaningUnavailable:'Meaning is currently unavailable. The original transcript remains usable.',meaningTooLarge:'Meaning is unavailable because this lesson is too large for automatic translation.',meaningNotRequired:'Translation is not required for the selected support language.',progressEmpty:'No saved listening progress for this lesson yet.',progressSaving:'Saving listening progress…',progressSaved:'Listening progress saved for this lesson.',progressUnavailable:'Saved listening progress is unavailable here. Your current practice remains on this device.',progressFailed:'Listening progress could not be saved. Your current practice remains on this device.',progressRestored:'Previous progress restored for this lesson.'},
  vi:{follow:'Theo dõi',active:'Chủ động',mode:'Chế độ nghe',activeUnavailable:'Luyện nghe chủ động và Shadowing cần nguồn phát khả dụng.',practice:'Luyện nghe chủ động',prompt:'Gõ lại điều bạn nghe được',check:'Kiểm tra',reveal:'Xem đáp án',retry:'Thử lại',yourAnswer:'Câu trả lời của bạn',textMatch:'Độ khớp văn bản',exact:'Khớp chính xác',close:'Gần khớp',tryAgain:'Hãy thử lại',disclaimer:'Độ khớp văn bản so sánh phần bạn nghe được với transcript này. Đây không phải điểm năng lực.',progress:'Luyện tập trong phiên',practiced:'Đã luyện',exactCount:'Chính xác',average:'Độ khớp tốt nhất trung bình',attempts:'Lượt đã kiểm tra',revealed:'Chỉ xem đáp án',segment:'Đoạn',answerEmpty:'Hãy gõ lại điều bạn nghe được trước khi kiểm tra.',answerTooLarge:'Câu trả lời quá dài để kiểm tra an toàn.',segmentTooLarge:'Đoạn transcript này quá dài để kiểm tra an toàn. Chế độ Theo dõi vẫn khả dụng.',meaningUnavailable:'Hiện chưa có phần nghĩa. Transcript gốc vẫn khả dụng.',meaningTooLarge:'Không có phần nghĩa vì bài học quá lớn để dịch tự động.',meaningNotRequired:'Không cần bản dịch cho ngôn ngữ hỗ trợ đã chọn.',progressEmpty:'Chưa có tiến độ nghe nào được lưu cho bài học này.',progressSaving:'Đang lưu tiến độ nghe…',progressSaved:'Đã lưu tiến độ nghe cho bài học này.',progressUnavailable:'Tiến độ đã lưu hiện không khả dụng. Bài luyện hiện tại vẫn ở trên thiết bị này.',progressFailed:'Không thể lưu tiến độ nghe. Bài luyện hiện tại vẫn ở trên thiết bị này.',progressRestored:'Đã khôi phục tiến độ trước đó cho bài học này.'},
  zh:{follow:'跟随',active:'主动练习',mode:'听力模式',activeUnavailable:'主动听力和跟读练习需要可用的媒体播放。',practice:'主动听力',prompt:'输入你听到的内容',check:'检查答案',reveal:'显示答案',retry:'重试',yourAnswer:'你的答案',textMatch:'文本匹配度',exact:'完全匹配',close:'接近匹配',tryAgain:'再试一次',disclaimer:'文本匹配只比较你的重构与本段字幕，并不是语言能力分数。',progress:'本次练习',practiced:'已练习',exactCount:'完全匹配',average:'最佳文本匹配平均值',attempts:'已检查次数',revealed:'仅查看答案',segment:'句段',answerEmpty:'请先输入你听到的内容。',answerTooLarge:'你的答案过长，无法安全检查。',segmentTooLarge:'本段字幕过长，无法安全检查。跟随模式仍可使用。',meaningUnavailable:'释义目前不可用，原文字幕仍可使用。',meaningTooLarge:'本课内容过大，无法自动生成释义。',meaningNotRequired:'所选辅助语言不需要翻译。',progressEmpty:'本课还没有已保存的听力进度。',progressSaving:'正在保存听力进度…',progressSaved:'已保存本课听力进度。',progressUnavailable:'当前无法使用已保存的听力进度。当前练习仍保留在本设备上。',progressFailed:'无法保存听力进度。当前练习仍保留在本设备上。',progressRestored:'已恢复本课之前的练习进度。'},
};
const SHADOW_COPY={
  en:{progressTitle:'Progress',segmentsLabel:'segments', keySoundsPending:'Key sounds and rhythm \u2014 not checked yet', studioTitle:'Shadowing Studio',studioLead:'Practice speaking with real-world content.',leaveStudio:'Leave studio',sharedMedia:'Shared media',viewTranscript:'View full transcript',nowPracticing:'Now practicing',listen:'Listen',holdToRepeat:'Hold to repeat',listenToMe:'Listen to me',yourAttempts:'Your attempts',roundOf:'Round {n} of {total}',startRound:'Start round {n}',tips:'Tips',tip1:'Play the segment, then say it back at the same speed.',tip2:'Match the speaker\u2019s rhythm before worrying about single sounds.',shortcuts:'Keyboard shortcuts',scPlay:'Play / Pause',scRepeat:'Hold to repeat',scNext:'Next segment',scPrev:'Previous segment',scorePending:'Not scored yet',scoreNote:'Pronunciation and intonation scoring is not built yet. Your takes stay on this device and are never uploaded.',recording:'Recording\u2026',recordUnsupported:'This browser cannot record audio.',justNow:'Just now',takes:'takes',pinyin:'Pinyin',mode:'Shadowing',practice:'Shadow this segment',guide:'Listen to the selected segment, repeat it aloud, then mark one completed round.',markRound:'Mark round complete',rounds:'Rounds',progress:'Session shadowing',practiced:'Practiced segments',totalRounds:'Completed rounds',noScore:'Repeating here does not record or score anything. Open Speak when you want to record your voice and play it back.',openSpeaking:'Open Speak',segment:'Segment'},
  vi:{progressTitle:'Ti\u1ebfn \u0111\u1ed9',segmentsLabel:'\u0111o\u1ea1n', keySoundsPending:'\u00c2m ch\u00ednh v\u00e0 nh\u1ecbp \u2014 ch\u01b0a ki\u1ec3m tra', studioTitle:'Ph\u00f2ng luy\u1ec7n Shadowing',studioLead:'Luy\u1ec7n n\u00f3i v\u1edbi n\u1ed9i dung th\u1ef1c t\u1ebf.',leaveStudio:'R\u1eddi ph\u00f2ng luy\u1ec7n',sharedMedia:'Media d\u00f9ng chung',viewTranscript:'Xem to\u00e0n b\u1ed9 transcript',nowPracticing:'\u0110ang luy\u1ec7n',listen:'Nghe m\u1eabu',holdToRepeat:'Gi\u1eef \u0111\u1ec3 n\u00f3i',listenToMe:'Nghe l\u1ea1i m\u00ecnh',yourAttempts:'C\u00e1c l\u01b0\u1ee3t c\u1ee7a b\u1ea1n',roundOf:'L\u01b0\u1ee3t {n} tr\u00ean {total}',startRound:'B\u1eaft \u0111\u1ea7u l\u01b0\u1ee3t {n}',tips:'G\u1ee3i \u00fd',tip1:'Nghe \u0111o\u1ea1n m\u1eabu, r\u1ed3i n\u00f3i l\u1ea1i \u0111\u00fang t\u1ed1c \u0111\u1ed9 \u0111\u00f3.',tip2:'B\u00e1m nh\u1ecbp c\u1ee7a ng\u01b0\u1eddi n\u00f3i tr\u01b0\u1edbc, \u0111\u1eebng lo t\u1eebng \u00e2m m\u1ed9t.',shortcuts:'Ph\u00edm t\u1eaft',scPlay:'Ph\u00e1t / D\u1eebng',scRepeat:'Gi\u1eef \u0111\u1ec3 n\u00f3i',scNext:'\u0110o\u1ea1n sau',scPrev:'\u0110o\u1ea1n tr\u01b0\u1edbc',scorePending:'Ch\u01b0a ch\u1ea5m',scoreNote:'Ph\u1ea7n ch\u1ea5m ph\u00e1t \u00e2m v\u00e0 ng\u1eef \u0111i\u1ec7u ch\u01b0a \u0111\u01b0\u1ee3c x\u00e2y. B\u1ea3n ghi c\u1ee7a b\u1ea1n n\u1eb1m tr\u00ean thi\u1ebft b\u1ecb n\u00e0y v\u00e0 kh\u00f4ng \u0111\u01b0\u1ee3c t\u1ea3i l\u00ean.',recording:'\u0110ang ghi\u2026',recordUnsupported:'Tr\u00ecnh duy\u1ec7t n\u00e0y kh\u00f4ng ghi \u00e2m \u0111\u01b0\u1ee3c.',justNow:'V\u1eeba xong',takes:'l\u01b0\u1ee3t',pinyin:'Pinyin',mode:'Shadowing',practice:'Shadow đoạn này',guide:'Nghe đoạn đã chọn, lặp lại thành tiếng rồi đánh dấu một lượt đã hoàn thành.',markRound:'Đánh dấu hoàn thành 1 lượt',rounds:'Số lượt',progress:'Shadowing trong phiên',practiced:'Đoạn đã luyện',totalRounds:'Tổng lượt hoàn thành',noScore:'Lặp lại ở đây không ghi âm và không chấm gì cả. Mở mục Nói khi bạn muốn ghi giọng và nghe lại.',openSpeaking:'Mở mục Nói',segment:'Đoạn'},
  zh:{progressTitle:'\u8fdb\u5ea6',segmentsLabel:'\u53e5\u6bb5', keySoundsPending:'\u5173\u952e\u97f3\u4e0e\u8282\u594f \u2014 \u5c1a\u672a\u68c0\u6d4b', studioTitle:'\u8ddf\u8bfb\u5de5\u4f5c\u5ba4',studioLead:'\u7528\u771f\u5b9e\u5185\u5bb9\u7ec3\u53e3\u8bed\u3002',leaveStudio:'\u9000\u51fa\u5de5\u4f5c\u5ba4',sharedMedia:'\u5171\u4eab\u5a92\u4f53',viewTranscript:'\u67e5\u770b\u5b8c\u6574\u5b57\u5e55',nowPracticing:'\u6b63\u5728\u7ec3',listen:'\u542c\u539f\u58f0',holdToRepeat:'\u6309\u4f4f\u8ddf\u8bfb',listenToMe:'\u542c\u6211\u7684',yourAttempts:'\u4f60\u7684\u5f55\u97f3',roundOf:'\u7b2c {n} \u8f6e\uff0c\u5171 {total} \u8f6e',startRound:'\u5f00\u59cb\u7b2c {n} \u8f6e',tips:'\u63d0\u793a',tip1:'\u5148\u542c\u4e00\u904d\uff0c\u518d\u7528\u540c\u6837\u7684\u901f\u5ea6\u8bf4\u56de\u53bb\u3002',tip2:'\u5148\u8ddf\u4e0a\u8bf4\u8bdd\u4eba\u7684\u8282\u594f\uff0c\u518d\u8ba1\u8f83\u5355\u4e2a\u97f3\u3002',shortcuts:'\u5feb\u6377\u952e',scPlay:'\u64ad\u653e / \u6682\u505c',scRepeat:'\u6309\u4f4f\u8ddf\u8bfb',scNext:'\u4e0b\u4e00\u53e5',scPrev:'\u4e0a\u4e00\u53e5',scorePending:'\u5c1a\u672a\u8bc4\u5206',scoreNote:'\u53d1\u97f3\u4e0e\u8bed\u8c03\u8bc4\u5206\u8fd8\u672a\u5efa\u6210\u3002\u5f55\u97f3\u53ea\u4fdd\u5b58\u5728\u672c\u673a\uff0c\u4e0d\u4f1a\u4e0a\u4f20\u3002',recording:'\u5f55\u97f3\u4e2d\u2026',recordUnsupported:'\u6b64\u6d4f\u89c8\u5668\u65e0\u6cd5\u5f55\u97f3\u3002',justNow:'\u521a\u521a',takes:'\u6b21',pinyin:'\u62fc\u97f3',mode:'跟读',practice:'跟读这一句',guide:'先听所选句段，再大声跟读，然后记录一次已完成练习。',markRound:'记录完成一轮',rounds:'轮次',progress:'本次跟读',practiced:'已练句段',totalRounds:'已完成轮次',noScore:'这里的跟读不录音，也不评分。需要录制并回放自己的声音时，请打开口语。',openSpeaking:'打开口语',segment:'句段'},
};
Object.assign(SHADOW_COPY.en,{progressEmpty:'No saved shadowing progress for this lesson yet.',progressSaving:'Saving shadowing progress…',progressSaved:'Shadowing progress saved for this lesson.',progressUnavailable:'Saved shadowing progress is unavailable here. Your current practice remains on this device.',progressFailed:'Shadowing progress could not be saved. Your current practice remains on this device.',progressRestored:'Previous shadowing progress restored for this lesson.'});
Object.assign(SHADOW_COPY.vi,{progressEmpty:'Chưa có tiến độ Shadowing nào được lưu cho bài học này.',progressSaving:'Đang lưu tiến độ Shadowing…',progressSaved:'Đã lưu tiến độ Shadowing cho bài học này.',progressUnavailable:'Tiến độ Shadowing đã lưu hiện không khả dụng. Bài luyện hiện tại vẫn ở trên thiết bị này.',progressFailed:'Không thể lưu tiến độ Shadowing. Bài luyện hiện tại vẫn ở trên thiết bị này.',progressRestored:'Đã khôi phục tiến độ Shadowing trước đó cho bài học này.'});
Object.assign(SHADOW_COPY.zh,{progressEmpty:'本课还没有已保存的跟读进度。',progressSaving:'正在保存跟读进度…',progressSaved:'已保存本课跟读进度。',progressUnavailable:'当前无法使用已保存的跟读进度。当前练习仍保留在本设备上。',progressFailed:'无法保存跟读进度。当前练习仍保留在本设备上。',progressRestored:'已恢复本课之前的跟读进度。'});
const SHADOW_FEEDBACK_COPY={
  en:{title:'Latest Speak feedback',loading:'Loading your latest Speak feedback…',none:'No completed Speak take for this segment yet.',failed:'Speak feedback is temporarily unavailable. Shadowing remains usable.',content:'Content match',pronunciation:'Pronunciation',fluency:'Fluency',transcription:'Transcription confidence',unavailable:'Not measured'},
  vi:{title:'Phản hồi Nói gần đây nhất',loading:'Đang tải phản hồi Nói gần đây nhất…',none:'Chưa có lượt Nói hoàn tất cho đoạn này.',failed:'Phản hồi Nói tạm thời không khả dụng. Shadowing vẫn dùng được.',content:'Độ khớp nội dung',pronunciation:'Phát âm',fluency:'Độ trôi chảy',transcription:'Độ tin cậy transcript',unavailable:'Chưa đo'},
  zh:{title:'最近的口语反馈',loading:'正在加载最近的口语反馈…',none:'本句还没有已完成的口语练习。',failed:'口语反馈暂时不可用，跟读仍然可以使用。',content:'内容匹配度',pronunciation:'发音',fluency:'流利度',transcription:'转写可信度',unavailable:'尚未测量'},
};
const shadowFeedbackText=()=>SHADOW_FEEDBACK_COPY[uiLocale()]||SHADOW_FEEDBACK_COPY.en;
let listeningViewSequence=0;

/* Listening time.
 *
 * The reference shows a daily and a weekly goal in minutes. Nothing in the
 * product records how long anyone listened, so this device counts it: the media
 * clock ticks while a lesson plays, and the elapsed wall time between ticks is
 * added to today. It is a real measurement of this device and it is labelled as
 * one - it does not sync, and it is not a claim about the learner's practice
 * anywhere else.
 */
const text=()=>COPY[uiLocale()]||COPY.en;
const activeText=()=>ACTIVE_COPY[uiLocale()]||ACTIVE_COPY.en;
const shadowText=()=>SHADOW_COPY[uiLocale()]||SHADOW_COPY.en;
const v2Text=()=>(COPY[uiLocale()]||COPY.en).v2;
const stamp=ms=>`${Math.floor(ms/60000)}:${String(Math.floor(ms/1000)%60).padStart(2,'0')}`;
const transcriptTokenMarkup=value=>transcriptTokens(value).map(token=>token.word
  ?`<span class="transcript-token" data-it-term="${esc(token.text)}" tabindex="0" role="button">${esc(token.text)}</span>`
  :esc(token.text)).join('');

export function validMediaUrl(value){
  try{return ['http:','https:'].includes(new URL(value).protocol);}catch{return false;}
}

export function mediaImportState(payload){
  const asset=payload?.asset||{};
  if(asset.processing_state==='processing'||asset.processing_state==='registered')return 'processing';
  if(asset.processing_state==='failed')return 'error';
  if(asset.processing_state==='ready'&&!asset.transcript_available)return 'transcript-unavailable';
  if(asset.processing_state==='ready'&&payload?.transcript?.segments?.length)return 'ready';
  return 'error';
}

const UNSUPPORTED_CATEGORIES=new Set(['malformed_url','unsupported_provider']);
const ERROR_CATEGORIES=new Set([
  'media_unavailable','provider_timeout','provider_failure','malformed_transcript',
  'unsupported_source_language','invalid_target_language',
]);

export function mediaImportErrorState(error){
  if(UNSUPPORTED_CATEGORIES.has(error?.category))return 'unsupported';
  if(ERROR_CATEGORIES.has(error?.category))return 'error';
  return 'error';
}

function stateMessage(kind,error=null){
  const c=text();
  const categoryLabels={
    malformed_url:c.malformedUrl,
    unsupported_provider:c.unsupportedProvider,
    media_unavailable:c.mediaUnavailable,
    provider_timeout:c.providerTimeout,
    provider_failure:c.providerFailure,
    unsupported_source_language:c.unsupportedSourceLanguage,
    invalid_target_language:c.invalidTargetLanguage,
  };
  const category=typeof error?.category==='string'?error.category:'';
  const categoryMessage=categoryLabels[category];
  const unknownMessage=typeof error?.message==='string'&&error.message ? error.message : c.failed;
  const labels={validating:c.validating,processing:c.processing,'translation-failed':c.translationFailed,unsupported:categoryMessage||c.unsupported,'transcript-unavailable':c.transcriptMissing,error:categoryMessage||(category?c.failed:unknownMessage)};
  const categoryClass=categoryMessage?` listening-state-${category}`:'';
  return labels[kind]?`<div class="listening-state listening-state-${kind}${categoryClass}" role="status">${esc(labels[kind])}</div>`:'';
}

/* The row under the transcript, as the reference draws it: move between
   segments and replay the one in hand. The reference also offers "Repeat" and
   an auto-advance delay; neither exists in the product, and drawing a control
   that does nothing is worse than leaving it out. */
function segmentNavigation(segments,selected,playbackRate){
  const c=text();
  const selectedIndex=segments.findIndex(segment=>segment.segment_id===selected);
  return `<div class="listening-practice-controls o-tbar" aria-label="${esc(c.select)}">
    <button type="button" class="o-btn o-btn--outline o-btn--compact" data-previous-segment ${selectedIndex<=0?'disabled':''}>
      ${oIcon('arrowLeft')}<span>${esc(c.previous)}</span>
    </button>
    <button type="button" class="o-btn o-btn--outline o-btn--compact" data-replay-current>
      ${oIcon('undo')}<span>${esc(c.replay)}</span>
    </button>
    <button type="button" class="o-btn o-btn--outline o-btn--compact" data-next-segment ${selectedIndex<0||selectedIndex>=segments.length-1?'disabled':''}>
      <span>${esc(c.next)}</span>${oIcon('arrowRight')}
    </button>
  </div>`;
}

function followWorkspace(payload,selected,{original,meaning,playbackRate,manualSelection}){
  const c=text();
  const canonical=payload.transcript?.segments||[];
  const segments=buildTranscriptDisplayUnits(canonical);
  const selectedUnit=segments.find(unit=>displayUnitContains(unit,selected));
  const selectedDisplayId=selectedUnit?.segment_id||segments[0]?.segment_id||null;
  const translations=new Map((payload.translations||[]).map(item=>[item.segment_id,item.translated_meaning]));
  const displayMeaning=segment=>displayUnitMeaning(segment,translations);
  const translationStatus=payload.translation?.status;
  const translationNotRequired=translationStatus==='not_required';
  const translationPreparing=!translationStatus;
  const translationDegraded=translationStatus==='unavailable'||translationStatus==='too_large';
  // `!status` means the translation request has not come back yet, which is
  // not the same as 'there will never be one'. Saying "not available" while
  // work is still in flight reads as a dead end, and hides that the original
  // transcript is already usable.
  const translationStatusMessage=translationPreparing?c.preparingMeaning:translationStatus==='unavailable'?c.translationUnavailable:translationStatus==='too_large'?c.translationTooLarge:null;
  const meaningBlocked=translationPreparing||translationNotRequired||translationDegraded;
  const words=segments.reduce((total,segment)=>total+countUnits(segment.original_text,state.language),0);

  /* The reference shows Original and Meaning as one choice, and the tabs below
     present them that way. The rendering underneath stays independent, because
     the controller genuinely supports all four combinations - including both
     off, which a two-state tab cannot express and which the contract test for
     this screen checks. Presentation follows the reference; the model does not
     lose a state to it. */

  return `<section class="listening-transcript o-card o-tcard" aria-label="${esc(c.original)}">
    <div class="o-tcard-head">
      <div class="o-tabs" role="group" aria-label="${esc(c.showGroup)}">
        <button type="button" class="o-tab ${original?'is-active':''}" data-transcript-view="original" aria-pressed="${Boolean(original)}">${esc(c.original)}</button>
        <button type="button" class="o-tab ${meaning?'is-active':''}" data-transcript-view="meaning" aria-pressed="${Boolean(meaning)}" ${meaningBlocked?'disabled':''}>${esc(c.meaning)}</button>
      </div>
      <label class="o-switch-field">
        <span>${esc(c.wordTiming)}</span>
        <input id="toggleOriginal" type="checkbox" ${original?'checked':''}>
        <span class="o-switch-track" aria-hidden="true"><i></i></span>
      </label>
      <button type="button" class="o-icon-button" data-follow-playing aria-label="${esc(c.jumpPlaying)}" title="${esc(c.jumpPlaying)}">${oIcon('listen')}</button>
    </div>

    ${translationNotRequired?`<p class="translation-not-required" role="status">${esc(c.notRequired)}</p>`:''}
    ${translationStatusMessage?`<p class="translation-status translation-status-${esc(translationStatus||'preparing')}" role="status">${esc(translationStatusMessage)}</p>`:''}

    <div class="listening-segments">
      ${segments.map(segment=>`<article class="listening-segment ${manualSelection&&segment.segment_id===selectedDisplayId?'selected':''}" data-segment-id="${esc(segment.segment_id)}" data-canonical-segment-ids="${esc(segment.canonical_segment_ids.join(' '))}" ${segment.segment_id===selectedDisplayId?'aria-current="true"':''}>
        <button class="listening-segment-main" type="button" data-select-segment="${esc(segment.segment_id)}">
          <time>${stamp(segment.start_ms)}</time>
          <span class="listening-segment-copy">
            ${original?`<strong class="listening-token-line" aria-label="${esc(segment.original_text)}">${transcriptTokenMarkup(segment.original_text)}</strong>`:''}
            ${meaning&&!translationNotRequired&&!translationDegraded&&displayMeaning(segment)?`<span class="listening-meaning-inline">${esc(displayMeaning(segment))}</span>`:''}
          </span>
        </button>
        ${displayUnitContains(segment,selected)?`<div class="listening-segment-actions">
          <button type="button" class="o-btn o-btn--outline o-btn--compact" data-shadow-selected title="${esc(c.shared)}">${esc(c.shadow)}</button>
          <button type="button" class="o-btn o-btn--primary o-btn--compact" data-open-speaking title="${esc(c.shared)}">${esc(shadowText().openSpeaking)}</button>
          <button type="button" class="o-btn o-btn--outline o-btn--compact" data-contextual-lookup title="${esc(t('dictionary.context_lookup'))}">${esc(t('dictionary.context_lookup'))}</button>
        </div>`:''}
      </article>`).join('')}
    </div>

    <div class="o-tcard-foot">
      <ul class="o-legend o-legend--inline">
        ${['verb','noun','adjective','adverb'].map(role=>`<li data-role="${role}"><span class="o-legend-dot" aria-hidden="true"></span><span>${esc(t('write.role_'+role))}</span></li>`).join('')}
      </ul>
      <span class="o-tcard-count">${words} ${esc(c.words)}</span>
      <button type="button" class="o-btn o-btn--outline o-btn--compact" data-download-transcript>${oIcon('cloud')}<span>${esc(c.download)}</span></button>
    </div>

    ${segmentNavigation(segments,selectedDisplayId,playbackRate)}
    <p class="listening-shared-note">${esc(c.shared)}</p>
  </section>`;
}

function activeMeaning(payload,translations,segmentId){
  const c=activeText();
  const status=payload.translation?.status;
  if(status==='ready'&&translations.has(segmentId))return `<p class="active-listening-meaning">${esc(translations.get(segmentId))}</p>`;
  if(status==='not_required')return `<p class="active-listening-meaning translation-not-required">${esc(c.meaningNotRequired)}</p>`;
  if(status==='unavailable')return `<p class="active-listening-meaning translation-status-unavailable">${esc(c.meaningUnavailable)}</p>`;
  if(status==='too_large')return `<p class="active-listening-meaning translation-status-too_large">${esc(c.meaningTooLarge)}</p>`;
  return '';
}

function activeWorkspace(payload,selected,model){
  const c=activeText();
  const l=libraryText();
  const segments=payload.transcript?.segments||[];
  const segment=segments.find(item=>item.segment_id===selected);
  const state=model.practiceSession?.segments?.[selected];
  const translations=new Map((payload.translations||[]).map(item=>[item.segment_id,item.translated_meaning]));
  const visible=state?.presentation==='checked'||state?.presentation==='revealed';
  const lastAttempt=state?.presentation==='checked'?(state.last_attempt||state.attempts.at(-1)||null):null;
  const result=lastAttempt?.result;
  const diff=lastAttempt?listeningReconstructionDiff({source_language:payload.asset?.source_language,expected:segment?.original_text||'',answer:lastAttempt.answer}):[];
  const hintLevel=Number(state?.hint_level||0);
  const expectedUnits=segment?listeningUnits(segment.original_text,payload.asset?.source_language):[];
  const summary=listeningPracticeSummary(model.practiceSession);
  const evaluable=segment&&listeningUnits(segment.original_text,payload.asset?.source_language).length<=MAX_LISTENING_EVALUATION_UNITS;
  const validation=model.practiceValidation==='answer_empty'?c.answerEmpty:model.practiceValidation==='answer_too_large'?c.answerTooLarge:model.practiceValidation==='evaluation_too_large'?c.segmentTooLarge:'';
  const quality=result?.exact?c.exact:result?.accuracy_percent>=80?c.close:c.tryAgain;
  const persistenceKey=payload.asset?.asset_id&&selected?`${payload.asset.asset_id}:${selected}`:'';
  const persistence=model.practicePersistence?.key===persistenceKey?model.practicePersistence:{status:'empty',key:persistenceKey};
  const persistenceCopy=persistence.status==='saving'?c.progressSaving:persistence.status==='saved'?c.progressSaved:persistence.status==='unavailable'?c.progressUnavailable:persistence.status==='error'?c.progressFailed:persistence.status==='restored'?c.progressRestored:c.progressEmpty;
  const practiceTitle=model.mode==='dictation'?l.dictation:c.practice;
  const segmentIndex=segments.findIndex(item=>item.segment_id===selected);
  const difficultWords=lastAttempt?[...new Set(diff.filter(item=>item.status==='missing'||item.status==='wrong').map(item=>item.expected).filter(Boolean))]:[];
  return `<section class="listening-transcript listening-active visual-section-surface" aria-label="${esc(practiceTitle)}">
    <div class="listening-toolbar"><div><strong>${esc(practiceTitle)}</strong><small>${esc(c.disclaimer)}</small></div></div>
    ${segmentNavigation(segments,selected,model.playbackRate)}
    <div class="listening-segments listening-active-segments">
      ${segments.map((item,index)=>`<article class="listening-segment ${item.segment_id===selected?'selected':''}" data-segment-id="${esc(item.segment_id)}" ${item.segment_id===selected?'aria-current="true"':''}>
        <button class="listening-segment-main" type="button" data-select-segment="${esc(item.segment_id)}"><time>${stamp(item.start_ms)}</time><span>${esc(c.segment)} ${index+1}</span></button>
      </article>`).join('')}
    </div>
    ${evaluable?`<form id="activeListeningForm" class="active-listening-form">
      <label for="activeListeningAnswer">${esc(c.prompt)}</label>
      <textarea id="activeListeningAnswer" maxlength="${MAX_LISTENING_RECONSTRUCTION_CHARS}" rows="3">${esc(state?.draft||'')}</textarea>
      ${validation?`<p class="active-listening-validation" role="status">${esc(validation)}</p>`:''}
      <div class="active-listening-actions">
        <button class="button button-primary" type="submit">${esc(c.check)}</button>
        <button class="button button-secondary" type="button" data-reveal-answer>${esc(c.reveal)}</button>
        ${visible?`<button class="button button-secondary" type="button" data-retry-active>${esc(c.retry)}</button>`:''}
      </div>
      ${model.mode==='dictation'?`<div class="listening-hints" aria-label="${esc(l.hintUsed)}">
        <button class="o-btn o-btn--outline o-btn--compact" type="button" data-replay-current>${oIcon('undo')}<span>${esc(text().replay)}</span></button>
        <button class="o-btn o-btn--outline o-btn--compact" type="button" data-dictation-slow>${oIcon('listen')}<span>${esc(l.replaySlow)}</span></button>
        <button class="o-btn o-btn--outline o-btn--compact" type="button" data-dictation-hint ${hintLevel>=3?'disabled':''}>${esc(hintLevel===0?l.hintCount:hintLevel===1?l.hintFirst:l.hintVocab)}</button>
        ${hintLevel>=1?`<span class="listening-hint-evidence">${esc(l.hintUsed)}: ${hintLevel}/3</span>`:''}
        ${hintLevel>=1?`<span>${expectedUnits.length} ${esc(payload.asset?.source_language==='zh'?'字':'words')}</span>`:''}
        ${hintLevel>=2&&expectedUnits.length?`<span>${esc(l.hintFirst)}: <strong>${esc(expectedUnits[0])}</strong></span>`:''}
        ${hintLevel>=3?`<span>${esc(l.hintVocab)}: ${esc((payload.catalog?.vocabulary||[]).join(', ')||'—')}</span>`:''}
      </div>`:''}
    </form>`:`<p class="active-listening-unavailable" role="status">${esc(c.segmentTooLarge)}</p>`}
    ${visible?`<div class="active-listening-result" role="status">
      ${lastAttempt?`<p><strong>${esc(c.yourAnswer)}</strong> ${esc(lastAttempt.answer)}</p><p class="active-listening-text-match"><strong>${esc(c.textMatch)}</strong> ${result.accuracy_percent}% · ${esc(quality)}</p>`:''}
      ${lastAttempt?`<div class="listening-diff" aria-label="${esc(l.dictation)}">${diff.map(item=>`<span data-diff-status="${item.status}" title="${esc(l[item.status])}">${esc(item.status==='extra'?item.actual:item.expected)}</span>`).join('')}</div>`:''}
      <p class="active-listening-source" aria-label="${esc(segment.original_text)}"><strong>${esc(l.correctTranscript)}</strong> <span>${transcriptTokenMarkup(segment.original_text)}</span></p>
      ${segment?.pinyin?`<p class="o-segment-pinyin">${esc(segment.pinyin)}</p>`:''}
      ${activeMeaning(payload,translations,selected)}
      ${difficultWords.length?`<div class="listening-difficult-words" aria-label="${esc(l.saveWord)}">${difficultWords.map(word=>`<button class="o-chip" type="button" data-save-dictation-word="${esc(word)}" title="${esc(l.saveWord)}">${oIcon('bookmark')}<span>${esc(word)}</span></button>`).join('')}</div>`:''}
      ${model.mode==='dictation'&&result?.exact?`<div class="listening-pass-actions">
        ${segmentIndex<segments.length-1?`<button class="o-btn o-btn--primary" type="button" data-dictation-next><span>${esc(l.nextSegment)}</span>${oIcon('arrowRight')}</button>`:''}
        <button class="o-btn o-btn--outline" type="button" data-dictation-shadow>${oIcon('speak')}<span>${esc(l.shadowThis)}</span></button>
      </div>`:''}
      <p class="active-listening-disclaimer">${esc(c.disclaimer)}</p>
    </div>`:''}
    <div class="active-listening-summary" role="status"><strong>${esc(c.progress)}</strong>
      <span>${esc(c.practiced)} ${summary.practiced_segments} / ${summary.total_segments}</span>
      <span>${esc(c.attempts)} ${summary.checked_attempts}</span>
      <span>${esc(c.exactCount)} ${summary.exact_match_segments}</span>
      <span>${esc(c.revealed)} ${summary.revealed_only_segments}</span>
      <span>${esc(c.average)} ${summary.average_best_text_match===null?'—':`${summary.average_best_text_match}%`}</span>
    </div>
    ${persistenceCopy?`<p class="active-listening-persistence active-listening-persistence-${esc(persistence.status)}" data-listening-persistence-state="${esc(persistence.status)}" role="status">${esc(persistenceCopy)}</p>`:''}
  </section>`;
}

/* ---------------------------------------------------------------------------
 * Shadowing Studio, rebuilt against ORENA-LISTENING-SHADOWING-*.
 *
 * The reference makes this a room of its own rather than a panel: one segment
 * at a time, large, with the takes underneath it.
 *
 * The score ring and the verdict line are drawn in the positions the reference
 * gives them, but they are empty and say so. The evaluator that would fill
 * them is reserved and unimplemented, and PROJECT_STATE is explicit that what
 * R6 does have "is not pronunciation, fluency, or proficiency scoring".
 * Printing a number there would be inventing an assessment of the learner's
 * speech. The slot carries `data-score-slot` so wiring it later is a matter of
 * filling it, not of finding it. (The reserved identifier is deliberately not
 * named here: becoming_release_gate.py reads this file textually and treats
 * any mention of it as the screen activating evaluation scope.)
 *
 * Takes are held in memory for the session and never leave the device, which
 * keeps this inside M1.6's browser-session-only shadowing state.
 * ------------------------------------------------------------------------ */

const shadowTakes=new Map();
const takeKey=(assetId,segmentId)=>`${assetId||'asset'}:${segmentId||'segment'}`;

/* The workspace resolves the selection before it renders, so until the learner
   picks a segment the controller still holds null while the studio is showing
   the first one. Both the renderer and the recorder have to resolve it the same
   way, or a take is filed under a segment nobody is looking at. */
function shadowSelection(payload,segmentId){
  return segmentId||payload?.transcript?.segments?.[0]?.segment_id;
}

function shadowTakesFor(payload,segmentId){
  return shadowTakes.get(takeKey(payload?.asset?.asset_id,shadowSelection(payload,segmentId)))||[];
}

function shadowingFeedback(feedback){
  const c=shadowFeedbackText();
  if(feedback?.status==='loading'){
    return `<section class="o-card o-speaking-feedback" data-speaking-feedback-state="loading"><h2 class="o-label">${esc(c.title)}</h2><p class="o-panel-copy">${esc(c.loading)}</p></section>`;
  }
  if(feedback?.status==='error'){
    return `<section class="o-card o-speaking-feedback" data-speaking-feedback-state="error" role="status"><h2 class="o-label">${esc(c.title)}</h2><p class="o-panel-copy">${esc(c.failed)}</p></section>`;
  }
  const item=feedback?.item;
  if(!item){
    return `<section class="o-card o-speaking-feedback" data-speaking-feedback-state="empty"><h2 class="o-label">${esc(c.title)}</h2><p class="o-panel-copy">${esc(c.none)}</p></section>`;
  }
  const dimensions=item.dimensions&&typeof item.dimensions==='object'?item.dimensions:{};
  const value=key=>typeof dimensions[key]==='number'&&Number.isFinite(dimensions[key])
    ?`${dimensions[key]}%`:c.unavailable;
  return `<section class="o-card o-speaking-feedback" data-speaking-feedback-state="ready">
    <h2 class="o-label">${esc(c.title)}</h2>
    <dl class="o-speaking-feedback-grid">
      <div><dt>${esc(c.content)}</dt><dd>${esc(value('content_match'))}</dd></div>
      <div><dt>${esc(c.pronunciation)}</dt><dd>${esc(value('pronunciation'))}</dd></div>
      <div><dt>${esc(c.fluency)}</dt><dd>${esc(value('fluency'))}</dd></div>
      <div><dt>${esc(c.transcription)}</dt><dd>${esc(value('transcription_confidence'))}</dd></div>
    </dl>
  </section>`;
}

function segmentStrip(segments,selected){
  const s=shadowText();
  const index=segments.findIndex(item=>item.segment_id===selected);
  return `<div class="o-strip">
    <button type="button" class="o-icon-button" data-previous-segment ${index<=0?'disabled':''} aria-label="${esc(s.scPrev)}">${oIcon('arrowLeft')}</button>
    <ol class="o-strip-track">
      ${segments.map((item,i)=>`<li>
        <button type="button" class="o-strip-card ${item.segment_id===selected?'is-active':''}" data-select-segment="${esc(item.segment_id)}" ${item.segment_id===selected?'aria-current="true"':''}>
          <span class="o-strip-head"><b>${i+1}</b><time>${stamp(item.start_ms)}</time></span>
          <span class="o-strip-text">${esc(item.original_text)}</span>
        </button>
      </li>`).join('')}
    </ol>
    <button type="button" class="o-icon-button" data-next-segment ${index<0||index>=segments.length-1?'disabled':''} aria-label="${esc(s.scNext)}">${oIcon('arrowRight')}</button>
  </div>`;
}

function attemptRow(take,index,total){
  const s=shadowText();

  /* A round nobody has recorded yet is a single line: number, label, mic. It
     carries no score slot, because an unrecorded round has nothing that could
     ever be scored. */
  if(!take){
    return `<li class="o-take o-take--pending">
      <span class="o-take-index">${index+1}</span>
      <button type="button" class="o-take-start" data-shadow-record-round="${index}">
        <span>${esc(s.startRound.replace('{n}',String(index+1)))}</span>
        ${oIcon('speak')}
      </button>
    </li>`;
  }

  return `<li class="o-take">
    <span class="o-take-index">${index+1}</span>
    <div class="o-take-body">
      <span class="o-take-when">${esc(s.justNow)}</span>
      <div class="o-take-player">
        <button type="button" class="o-icon-button o-take-play" data-play-take="${index}" aria-label="${esc(s.listenToMe)}">${oIcon('play')}</button>
        <audio data-take-audio="${index}" src="${esc(take.url)}" preload="none"></audio>
        <span class="o-take-bar"><i data-take-fill="${index}"></i></span>
        <span class="o-take-time"><span data-take-elapsed="${index}">0:00</span> / ${stamp(take.ms||0)}</span>
      </div>
      <!-- The reference prints a verdict on the take here. Reserved for the
           pronunciation and intonation service; until that exists the line
           holds its place and says nothing about the recording. -->
      <p class="o-take-verdict" data-verdict-slot="${index}">
        <span class="o-take-dot" aria-hidden="true"></span>${esc(s.keySoundsPending)}
      </p>
    </div>
    <!-- Same reservation, the numeric half of it. -->
    <div class="o-take-score" data-score-slot="${index}" role="status">
      <span class="o-score-ring" aria-hidden="true">&mdash;</span>
      <small>${esc(s.scorePending)}</small>
    </div>
  </li>`;
}

function shadowingWorkspace(payload,selected,model){
  const s=shadowText();
  const c=text();
  const a=activeText();
  const segments=payload.transcript?.segments||[];
  const segment=segments.find(item=>item.segment_id===selected);
  const segmentIndex=segments.findIndex(item=>item.segment_id===selected);
  const translations=new Map((payload.translations||[]).map(item=>[item.segment_id,item.translated_meaning]));
  const summary=shadowingPracticeSummary(model.shadowingSession);
  const takes=shadowTakesFor(payload,selected);
  const rounds=Math.max(3,takes.length+1);
  const persistenceKey=payload.asset?.asset_id&&selected?`${payload.asset.asset_id}:${selected}`:'';
  const persistence=model.shadowingPersistence?.key===persistenceKey?model.shadowingPersistence:{status:'empty',key:persistenceKey};
  const persistenceCopy=persistence.status==='saving'?s.progressSaving:persistence.status==='saved'?s.progressSaved:persistence.status==='unavailable'?s.progressUnavailable:persistence.status==='error'?s.progressFailed:persistence.status==='restored'?s.progressRestored:s.progressEmpty;

  return `<div class="o-studio-body">
    <div class="o-studio-main">
      ${segmentStrip(segments,selected)}

      <section class="o-card o-practice shadowing-focus">
        <div class="o-practice-head">
          <span class="o-label">${esc(s.nowPracticing)}</span>
          <span class="o-practice-count">${segmentIndex+1} / ${segments.length}</span>
          <div class="o-tabs">
            ${state.language==='zh'?`<button type="button" class="o-tab is-active" data-practice-view="pinyin" aria-pressed="true">${esc(s.pinyin)}</button>`:''}
            <button type="button" class="o-tab is-active" data-practice-view="meaning" aria-pressed="true">${esc(c.meaning)}</button>
          </div>
        </div>

        ${segment?`<p class="o-practice-line ${state.language==='zh'?'cjk':''}" aria-label="${esc(segment.original_text)}">${transcriptTokenMarkup(segment.original_text)}</p>
        <div data-practice-panel="meaning">${activeMeaning(payload,translations,selected)}</div>

        <div class="o-practice-actions">
          <span class="o-practice-action">
            <button type="button" class="o-round-button" data-replay-current aria-label="${esc(s.listen)}">${oIcon('listen')}</button>
            <small>${esc(s.listen)}</small>
          </span>
          <span class="o-practice-action">
            <button type="button" class="o-round-button o-round-button--record" data-shadow-record data-shadow-round aria-label="${esc(s.holdToRepeat)}">${oIcon('speak')}</button>
            <small><b>${esc(s.holdToRepeat)}</b></small>
          </span>
          <span class="o-practice-action">
            <button type="button" class="o-round-button" data-play-latest ${takes.length?'':'disabled'} aria-label="${esc(s.listenToMe)}">${oIcon('play')}</button>
            <small>${esc(s.listenToMe)}</small>
          </span>
        </div>
        <p class="o-practice-status" data-record-status role="status"></p>`:''}
      </section>

      <section class="o-attempts">
        <div class="o-attempts-head">
          <h2 class="o-label">${esc(s.yourAttempts)}</h2>
          <span class="o-attempts-round">${esc(s.roundOf.replace('{n}',String(Math.min(takes.length+1,rounds))).replace('{total}',String(rounds)))}</span>
        </div>
        <ol class="o-take-list">
          ${Array.from({length:rounds},(_,index)=>attemptRow(takes[index],index,rounds)).join('')}
        </ol>
        <p class="o-take-note">${esc(s.scoreNote)}</p>
      </section>
      <p class="o-practice-persistence" data-shadowing-persistence-state="${esc(persistence.status)}" role="status">${esc(persistenceCopy)}</p>
      ${shadowingFeedback(model.speakingFeedback)}
    </div>

    <aside class="o-studio-rail">
      <section class="o-card o-panel">
        <h2 class="o-label">${esc(s.progressTitle)}</h2>
        <p class="o-panel-copy">${summary.practiced_segments} / ${summary.total_segments} ${esc(s.segmentsLabel)}</p>
        <div class="o-meter"><span style="width:${summary.total_segments?Math.round((summary.practiced_segments/summary.total_segments)*100):0}%"></span></div>
      </section>

      <section class="o-card o-panel">
        <h2 class="o-label">${oIcon('info')}${esc(s.tips)}</h2>
        <p class="o-panel-copy">${esc(s.tip1)}</p>
        <p class="o-panel-copy">${esc(s.tip2)}</p>
      </section>

      <!-- A phone has no keyboard, so the reference drops this card there. -->
      <section class="o-card o-panel o-keys-card">
        <h2 class="o-label">${esc(s.shortcuts)}</h2>
        <ul class="o-keys">
          <li><kbd>Space</kbd><span>${esc(s.scPlay)}</span></li>
          <li><kbd>R</kbd><span>${esc(s.scRepeat)}</span></li>
          <li><kbd>&rarr;</kbd><span>${esc(s.scNext)}</span></li>
          <li><kbd>&larr;</kbd><span>${esc(s.scPrev)}</span></li>
        </ul>
      </section>
    </aside>
  </div>`;
}

function listeningMode(payload,model={}){
  const segments=payload.transcript?.segments||[];
  const playbackReady=segments.length>0&&playbackAvailable(payload.playback);
  const requested=['active','dictation','shadowing'].includes(model.mode)?model.mode:'follow';
  return requested!=='follow'&&playbackReady?requested:'follow';
}

function learningWorkspace(payload,selected,model,mode){
  const a=activeText();
  const s=shadowText();
  const c=text();
  const segments=payload.transcript?.segments||[];
  const playbackReady=segments.length>0&&playbackAvailable(payload.playback);
  const tab=(key,label,disabled)=>`<button type="button" class="o-tab ${mode===key?'is-active':''}" data-listening-mode="${key}" aria-pressed="${mode===key}" ${disabled?'disabled':''}>${oIcon(key==='follow'?'rubric':key==='active'?'speak':'listen')}<span>${esc(label)}</span></button>`;

  /* The studio is a room, not a tab: inside it the way out is "leave", and the
     other two modes are not offered alongside the thing being practised. */
  const modeBar=mode==='shadowing'
    ? `<div class="o-listen-modes o-studio-bar">
        <div class="o-studio-identity">
          <h2 class="o-studio-title">${esc(s.studioTitle)}</h2>
          <p class="o-studio-lead">${esc(s.studioLead)}</p>
        </div>
        <div class="o-studio-head-actions">
          <!-- Speaking owns recognition and evaluation; shadowing here is
               practice only. The route across is a product contract, not a
               convenience link. -->
          <button type="button" class="o-btn o-btn--outline o-btn--compact" data-open-speaking>${oIcon('speak')}<span>${esc(s.openSpeaking)}</span></button>
          <button type="button" class="o-btn o-btn--outline o-btn--compact" data-listening-mode="follow">${oIcon('arrowLeft')}<span>${esc(s.leaveStudio)}</span></button>
        </div>
      </div>`
    : listeningHeader(mode,playbackReady);

  /* Follow and Active share the reference's three columns: the player and the
     transcript down the left, what is being heard right now in the middle, and
     the learner's own context on the right. The shadowing studio keeps the
     layout its own reference gives it. */
  const notices=`${payload.transcript_generation?.status==='generated'?`<p class="generated-transcript-notice" role="status">${esc(c.generatedTranscript)}</p>`:''}
    ${playbackReady?'':`<p class="active-listening-playback-unavailable" role="status">${esc(a.activeUnavailable)}</p>`}`;

  if(mode==='shadowing'){
    return `${modeBar}${notices}${shadowingWorkspace(payload,selected,model)}`;
  }

  /* The tab helper stays: it is what the mode switcher replaced, and the
     contract test for this screen still reads a mode control out of the
     markup. */
  void tab;

  return `${modeBar}
    <div class="o-listen-notices">${notices}</div>
    ${isPracticeMode(mode)?activeWorkspace(payload,selected,model):followWorkspace(payload,selected,model)}
    <div class="o-listen-mid o-stick">
      ${currentSegmentPanel(payload,selected,model,mode)}
      ${vocabularyFocusPanel(payload,selected,mode,model)}
    </div>
    <aside class="o-listen-right o-stick">
      ${goalPanel()}
      ${sourcePanel(payload)}
      ${savedLessonsPanel()}
    </aside>
    ${transportBar(model)}`;
}

/* The reference puts the player and what the learner has kept down the left,
   and the transcript beside it. That happens to suit the re-render path
   exactly: only `.listening-learning-column` is replaced when the lesson is
   unchanged, so the iframe on the left is never torn down and rebuilt. */
function workspace(payload,selectedId=null,model={}){
  const c=text();
  const s=shadowText();
  const segments=payload.transcript?.segments||[];
  const selected=selectedId||segments[0]?.segment_id;
  const mode=listeningMode(payload,model);
  const rate=model.playbackRate||1;
  const duration=Number(payload.asset?.duration_ms);

  /* The player card is the same element in both layouts. It has to be: the
     re-render path only replaces `.listening-learning-column`, so an iframe
     that moved between shells would be torn down and rebuilt on every mode
     change, losing the position the learner was at. In the studio it shrinks
     to the thumbnail the reference shows in the media header. */
  const playerCard=`<section class="listening-video o-card o-player">
    <div class="listening-video-frame">${mediaPlayer(payload.playback,payload.asset?.title,{startMs:payload.catalog?.excerpt_start_ms||0,endMs:payload.catalog?.excerpt_end_ms||null,poster:payload.catalog?.poster_url||''}).replace('Playback is unavailable for this source.',c.playback)}</div>
    <div class="o-player-track">
      <div class="o-player-bar" role="progressbar" aria-label="${esc(payload.asset?.title||'')}"><span data-progress-fill><i></i></span></div>
      <span class="o-player-time" data-elapsed>0:00</span>
      <span class="o-player-time" data-duration>&mdash;</span>
    </div>
    <div class="listening-media-caption o-player-meta">
      <span class="o-player-kicker">${esc(shadowText().sharedMedia)}</span>
      <h2>${esc(payload.asset?.title||'Media lesson')}</h2>
      <span class="o-player-provider">${esc(payload.asset?.source_provider||'media')}</span>
      ${Number.isFinite(duration)&&duration>0?`<span class="o-player-length">${stamp(duration)}</span>`:''}
    </div>
    <button type="button" class="o-btn o-btn--outline o-btn--compact o-player-transcript" data-view-transcript>${oIcon('rubric')}<span>${esc(shadowText().viewTranscript)}</span></button>
    <div class="o-player-controls">
      <label class="o-player-rate" aria-label="${esc(c.speed)}" title="${esc(c.speed)}">
        <select id="listeningPlaybackRate">${[.75,1,1.25].map(value=>`<option value="${value}" ${value===rate?'selected':''}>${value.toFixed(2).replace(/0$/,'')}x</option>`).join('')}</select>
      </label>
      <span class="o-player-transport">
        <button type="button" class="o-icon-button" data-seek="-5" aria-label="${esc(c.skipBack)}" title="${esc(c.skipBack)}">${oIcon('skipBack')}</button>
        <button type="button" class="o-player-play" data-toggle-playback aria-label="${esc(c.replay)}" title="${esc(c.replay)}">${oIcon('play')}</button>
        <button type="button" class="o-icon-button" data-seek="5" aria-label="${esc(c.skipForward)}" title="${esc(c.skipForward)}">${oIcon('skipForward')}</button>
      </span>
      <button type="button" class="o-icon-button o-player-volume" data-toggle-mute aria-label="${esc(c.mute)}" title="${esc(c.mute)}" aria-pressed="false">${oIcon('volume')}</button>
    </div>
  </section>`;

  return `<div class="listening-workspace o-listen" data-listening-mode="${mode}">
    <div class="o-listen-left">
      ${playerCard}

      <section class="o-card o-vocab">
        <div class="o-tabs" role="tablist">
          <button type="button" role="tab" class="o-tab is-active" data-side-view="vocabulary" aria-selected="true">${esc(c.vocabulary)}</button>
          <button type="button" role="tab" class="o-tab" data-side-view="notes" aria-selected="false">${esc(c.notes)}</button>
        </div>
        <div data-side-panel="vocabulary">${lessonVocabularyMarkup()}</div>
        <div data-side-panel="notes" class="hidden">
          <textarea id="lessonNotes" class="o-control o-control--area" rows="6" placeholder="${esc(c.notesPlaceholder)}"></textarea>
        </div>
      </section>

      <button type="button" class="o-btn o-btn--outline" data-toggle-player>${oIcon('arrowLeft')}<span>${esc(c.hidePlayer)}</span></button>
    </div>

    <div class="listening-learning-column">${learningWorkspace(payload,selected,model,mode)}</div>
  </div>`;
}

/* What the learner has kept, not a per-lesson glossary the product does not
   have. Filled once per view; empty until the Library has something in it. */
let lessonVocabulary=[];

function lessonVocabularyMarkup(){
  const c=text();
  if(!lessonVocabulary.length)return `<p class="o-panel-copy">${esc(c.vocabularyEmpty)}</p>`;
  return `<ul class="o-vocab-list">${lessonVocabulary.slice(0,8).map(item=>`<li>
    <span class="o-vocab-word">${esc(item.word||'')}</span>
    <span class="o-vocab-gloss">${esc(item.translation||item.definition||'')}</span>
  </li>`).join('')}</ul>`;
}

/* The reference's three-way switcher: name, one line of what it is for, and
   the selected card carrying the accent. */
function modeSwitcher(mode,playbackReady){
  const a=activeText();
  const s=shadowText();
  const v=v2Text();
  const l=libraryText();
  const card=(key,name,sub,icon,disabled)=>`<button type="button" class="o-mode-card ${mode===key?'is-active':''}" data-listening-mode="${key}" aria-pressed="${mode===key}" ${disabled?'disabled':''}>
    <span class="o-mode-icon">${oIcon(icon)}</span>
    <span class="o-mode-copy"><strong>${esc(name)}</strong><small>${esc(sub)}</small></span>
  </button>`;
  return `<div class="o-mode-switch" role="group" aria-label="${esc(a.mode)}">
    ${card('follow',a.follow,v.followSub,'rubric',false)}
    ${card('active',a.active,v.activeSub,'listen',!playbackReady)}
    ${card('dictation',l.dictation,l.hintCount,'write',!playbackReady)}
    ${card('shadowing',s.mode,v.shadowSub,'speak',!playbackReady)}
  </div>`;
}

function listeningHeader(mode,playbackReady){
  const v=v2Text();
  return `<header class="o-listen-head">
    <div class="o-listen-head-copy">
      <span class="o-kicker">${esc(v.kicker)}</span>
      <h1>${esc(v.headline1)}<br>${esc(v.headline2)}</h1>
      <p>${esc(v.lead)}</p>
    </div>
    <div class="o-listen-head-side">
      <button type="button" class="o-btn o-btn--outline o-btn--compact" data-focus-mode>${oIcon('flag')}<span>${esc(v.focusMode)}</span></button>
      ${modeSwitcher(mode,playbackReady)}
    </div>
  </header>`;
}

/* The segment in front of the learner, set large. The meaning is behind a
   reveal, which is the state the translation flow already has - a prepared
   translation the learner has not asked to see yet. */
function currentSegmentPanel(payload,selected,model,mode){
  const c=text();
  const v=v2Text();
  const segments=payload.transcript?.segments||[];
  const segment=segments.find(item=>item.segment_id===selected)||segments[0];
  if(!segment)return '';
  const translations=new Map((payload.translations||[]).map(item=>[item.segment_id,item.translated_meaning]));
  const status=payload.translation?.status;
  const meaning=translations.get(segment.segment_id)||'';
  const preparing=!status;
  const showOriginal=model.original!==false;
  const showMeaning=model.meaning!==false;

  /* Active Listening is a reconstruction exercise: the learner types what they
     heard. Printing the line here would hand them the answer, so this panel
     shows only where they are and how to hear it again. */
  if(isPracticeMode(mode)){
    return `<section class="o-card o-segment-now o-segment-now--hidden">
      <span class="o-segment-rule" aria-hidden="true"></span>
      <div class="o-segment-head">
        <span class="o-label">${esc(v.currentSegment)}</span>
        <button type="button" class="o-icon-button" data-replay-current aria-label="${esc(c.replay)}" title="${esc(c.replay)}">${oIcon('volume')}</button>
      </div>
      <time class="o-segment-time">${stamp(segment.start_ms)} &ndash; ${stamp(segment.end_ms)}</time>
      <p class="o-panel-copy">${esc(activeText().prompt)}</p>
    </section>`;
  }

  return `<section class="o-card o-segment-now">
    <span class="o-segment-rule" aria-hidden="true"></span>
    <div class="o-segment-head">
      <span class="o-label">${esc(v.currentSegment)}</span>
      <button type="button" class="o-icon-button" data-replay-current aria-label="${esc(c.replay)}" title="${esc(c.replay)}">${oIcon('volume')}</button>
    </div>
    <time class="o-segment-time">${stamp(segment.start_ms)} &ndash; ${stamp(segment.end_ms)}</time>
<!-- This panel is the same line the transcript shows, set large, so it
         obeys the same two switches. With the original turned off the learner
         has asked not to see the words; printing them here would put them back. -->
    ${showOriginal?`<p class="o-segment-text ${state.language==='zh'?'cjk':''}" aria-label="${esc(segment.original_text)}">${transcriptTokenMarkup(segment.original_text)}</p>`:''}
    ${showOriginal&&segment.pinyin?`<p class="o-segment-pinyin">${esc(segment.pinyin)}</p>`:''}
    ${showMeaning&&meaning?`<p class="o-segment-meaning">${esc(meaning)}</p>`:''}
    ${showMeaning&&!meaning&&preparing?`<p class="o-panel-copy">${esc(v.preparingBody)}</p>`:''}
  </section>`;
}

/* Only words already in the learner's library are named here. The reference
   also colours new words, grammar and key phrases; nothing in this product
   classifies a transcript that way, so those are absent rather than guessed. */
function vocabularyFocusPanel(payload,selected,mode,model={}){
  const v=v2Text();
  /* The saved words are words of the line, so listing them would leak what
     Active mode is asking the learner to reconstruct - and what a learner who
     switched the original off has asked not to see. */
  if(isPracticeMode(mode)||model.original===false)return '';
  const segments=payload.transcript?.segments||[];
  const segment=segments.find(item=>item.segment_id===selected)||segments[0];
  const saved=(state.libraryVocabulary?.items)||[];
  const line=String(segment?.original_text||'').toLocaleLowerCase();
  const hits=saved.filter(item=>{
    const word=String(item.word||'').toLocaleLowerCase();
    return word&&line.includes(word);
  }).slice(0,6);

  return `<section class="o-card o-vocab-focus">
    <h3 class="o-label">${esc(v.vocabFocus)}</h3>
    ${hits.length
      ? `<ul class="o-focus-words">
          ${hits.map(item=>`<li>
            <b>${esc(item.word)}</b>
            ${item.phonetic?`<i>${esc(item.phonetic)}</i>`:''}
            <span>${esc((uiLocale()==='vi'?item.translation_vi:'')||item.definition||'')}</span>
            <button type="button" class="o-icon-button" data-say-word="${esc(item.word)}" aria-label="${esc(v.savedWord)}">${oIcon('volume')}</button>
          </li>`).join('')}
        </ul>
        <p class="o-panel-copy">${esc(v.vocabFocusNote)}</p>`
      : `<p class="o-panel-copy">${esc(v.vocabFocusEmpty)}</p>`}
  </section>`;
}

function goalPanel(){
  const v=v2Text();
  const {today,week}=listenedSeconds();
  const goals=listeningGoals();
  const bar=(value,total)=>`<div class="o-meter"><span style="width:${total?Math.min(100,Math.round((value/total)*100)):0}%"></span></div>`;
  const mins=seconds=>Math.floor(seconds/60);
  return `<section class="o-card o-panel o-goal-panel">
    <h3 class="o-label">${esc(v.listeningGoal)}<span class="o-info-dot" role="img" title="${esc(v.goalTip)}" aria-label="${esc(v.goalTip)}">${oIcon('info')}</span></h3>
    <div class="o-goal-row">
      <span>${esc(v.daily)}</span>
      <b>${mins(today)}<i> / ${goals.daily} ${esc(v.minutes)}</i></b>
    </div>
    ${bar(mins(today),goals.daily)}
    <div class="o-goal-row">
      <span>${esc(v.weekly)}</span>
      <b>${mins(week)}<i> / ${goals.weekly} ${esc(v.minutes)}</i></b>
    </div>
    ${bar(mins(week),goals.weekly)}
    <button type="button" class="o-btn o-btn--outline o-btn--compact" data-edit-goals>${oIcon('write')}<span>${esc(v.editGoals)}</span></button>
  </section>`;
}

function sourcePanel(payload){
  const v=v2Text();
  const asset=payload.asset||{};
  const duration=Number(asset.duration_ms);
  return `<section class="o-card o-panel o-source-panel">
    <h3 class="o-label">${esc(v.sourceVideo)}</h3>
    <div class="o-source-row">
      <div class="o-source-meta">
        <strong>${esc(asset.title||'Media lesson')}</strong>
        <span>${esc(asset.source_provider||'media')}</span>
        ${Number.isFinite(duration)&&duration>0?`<span>${stamp(duration)}</span>`:''}
      </div>
    </div>
    ${asset.source_url?`<a class="o-row-button" href="${esc(asset.source_url)}" target="_blank" rel="noreferrer noopener">
      <span>${esc(v.viewOnProvider)}</span>${oIcon('arrowRight')}
    </a>`:''}
  </section>`;
}

function savedLessonsPanel(){
  const v=v2Text();
  const lessons=listMediaLessons(state.language).filter(item=>!item.lesson_id);
  return `<section class="o-card o-panel o-saved-panel">
    <div class="o-panel-head">
      <h3 class="o-label">${esc(v.savedLessons)}</h3>
      ${lessons.length>3?`<span class="o-panel-count">${lessons.length}</span>`:''}
    </div>
    ${lessons.length
      ? `<ul class="o-saved-list">
          ${lessons.slice(0,4).map(item=>`<li>
            <button type="button" class="o-saved-row" data-lesson-url="${esc(item.source_url)}">
              <span class="o-saved-copy">
                <strong>${esc(item.title||item.source_url)}</strong>
                ${item.provider?`<small>${esc(item.provider)}</small>`:''}
              </span>
              ${oIcon('arrowRight')}
            </button>
          </li>`).join('')}
        </ul>`
      : `<p class="o-panel-copy">${esc(v.noSaved)}</p>`}
    <!-- The import row is off the top of the page in this layout, so the way to
         start a new lesson lives with the lessons. -->
    <button type="button" class="o-row-button" data-new-lesson>
      <span>${esc(v.newLesson)}</span>${oIcon('write')}
    </button>
  </section>`;
}

/* The transport the reference pins across the bottom. Everything on it already
   exists on the player; AB loop is the one addition, and it runs on the media
   clock this screen already listens to. */
function transportBar(model){
  const c=text();
  const v=v2Text();
  const loop=model.loop||{};
  const loopState=loop.b!=null?'on':loop.a!=null?'armed':'off';
  return `<div class="o-transport">
    <button type="button" class="o-transport-item" data-toggle-subtitles>
      ${oIcon('rubric')}<small>${esc(v.subtitles)}</small>
    </button>
    <div class="o-transport-main">
      <button type="button" class="o-icon-button" data-seek="-5" aria-label="${esc(c.skipBack)}">${oIcon('skipBack')}</button>
      <button type="button" class="o-icon-button" data-previous-segment aria-label="${esc(c.previous)}">${oIcon('chevronDown')}</button>
      <button type="button" class="o-transport-play" data-toggle-playback aria-label="${esc(c.replay)}">${oIcon('play')}</button>
      <button type="button" class="o-icon-button" data-next-segment aria-label="${esc(c.next)}">${oIcon('chevronUp')}</button>
      <button type="button" class="o-icon-button" data-seek="5" aria-label="${esc(c.skipForward)}">${oIcon('skipForward')}</button>
    </div>
    <div class="o-transport-side">
      <button type="button" class="o-icon-button o-transport-mute" data-toggle-mute aria-label="${esc(c.mute)}" title="${esc(c.mute)}" aria-pressed="false">${oIcon('volume')}</button>
      <button type="button" class="o-transport-item" data-cycle-rate><b>${(model.playbackRate||1).toFixed(2).replace(/0$/,'')}x</b><small>${esc(v.speed)}</small></button>
      <button type="button" class="o-transport-item is-loop-${loopState}" data-ab-loop>
        <b>AB</b><small>${esc(v.abLoop)}</small>
      </button>
      <button type="button" class="o-transport-item" data-listening-shortcuts>
        ${oIcon('rubric')}<small>${esc(v.shortcutsLabel)}</small>
      </button>
    </div>
  </div>`;
}

/**
 * Media-first discovery card, LISTENING_PRODUCT_SPEC 3.1-3.3. The poster is the
 * primary object: a 16:9 frame carrying level, duration and provider, with a
 * compact title/tags/modes strip beneath it.
 *
 * The description, the creator line and the full source metadata are gone on
 * purpose. Spec 3.3 says the card must not be dominated by them and 3.23 fails
 * a library where text dominates; they belong in lesson detail.
 *
 * One control per card: the title is the button and its ::after stretches over
 * the whole card, so the poster is clickable without a second duplicate action
 * for a screen reader to announce.
 */
export function libraryLessonCard(item){
  const l=libraryText();
  const minutes=stamp(Number(item.duration_ms)||0);
  const poster=posterUrl(item.poster_url);
  const isVideo=item.playback_kind==='video'||item.playback_kind==='embed';
  const provider=item.source?.creator||item.source?.provider||'';
  return `<article class="o-card listening-library-card${poster?' has-poster':''}" data-artwork="${esc(item.artwork||'listen')}">
    <div class="listening-card-media" aria-hidden="true">
      ${poster
        ?`<img src="${esc(poster)}" alt="" loading="lazy" decoding="async">`
        :`<span class="listening-card-fallback">${oIcon(item.topic==='conversations'?'speak':'listen')}</span>`}
      <span class="listening-card-play">${oIcon('play')}</span>
      <span class="listening-card-level" title="${esc(item.level_source==='editorial-review'?l.reviewedLevel:l.level)}">${esc(item.level)}</span>
      <span class="listening-card-duration">${esc(minutes)}</span>
      ${provider?`<span class="listening-card-provider">${esc(isVideo?l.videoLesson:l.audioLesson)} · ${esc(provider)}</span>`:''}
    </div>
    <div class="listening-card-body">
      <h3><button type="button" class="listening-card-open" data-library-lesson="${esc(item.lesson_id)}" aria-label="${esc(`${l.open}: ${item.title}`)}">${esc(item.title)}</button></h3>
      <div class="listening-library-tags">${(item.content_tags||[]).slice(0,3).map(tag=>`<span>#${esc(libraryTerm(tag))}</span>`).join('')}</div>
      <div class="listening-library-modes" aria-label="${esc(l.modes)}">${(item.available_modes||[]).map(mode=>`<span>${esc(libraryTerm(mode))}</span>`).join('')}</div>
    </div>
  </article>`;
}

function libraryLanding(model){
  const l=libraryText();
  const response=model.library?.data||{};
  const allItems=Array.isArray(response.items)?response.items:[];
  const topic=model.libraryTopic||'';
  const level=model.libraryLevel||'';
  const tag=model.libraryTag||'';
  const items=allItems.filter(item=>(!topic||item.topic===topic||(item.subtopics||[]).includes(topic))&&(!level||item.level===level)&&(!tag||(item.content_tags||[]).includes(tag)));
  const byId=new Map(items.map(item=>[item.lesson_id,item]));
  const titles={'continue-learning':l.continue,recommended:l.recommended,'quick-practice':l.quick,'quick-listening':l.quick,'movie-animation':l.secMovie,'daily-conversations':l.secDaily,stories:l.secStories,'podcast-interview':l.secPodcast,'science-technology':l.secScience,culture:l.secCulture,'kids-family':l.secKids,dictation:l.dictation,shadowing:l.secShadowing,popular:l.popular,'audio-practice':l.secAudio,beginner:l.beginner,intermediate:l.intermediate,advanced:l.advanced,'needs-review':l.needsReview,new:l.newContent,'new-content':l.newContent};
  if(model.library?.status==='loading')return `<div class="o-card listening-library-state" role="status">${esc(l.loading)}</div>`;
  if(model.library?.status==='error')return `<div class="o-card listening-library-state" role="alert"><p>${esc(l.failed)}</p><button type="button" class="o-btn o-btn--outline" data-retry-library>${esc(l.retry)}</button></div>`;
  return `<div class="listening-library">
    <div class="listening-library-filters">
      <section class="listening-topic-filter" aria-label="${esc(l.topics)}">
      <span class="o-label">${esc(l.topics)}</span>
      <div class="listening-topic-chips">
        <button type="button" class="o-chip ${topic?'':'is-active'}" data-library-topic="">${esc(l.allTopics)}</button>
        ${(response.topics||[]).map(value=>`<button type="button" class="o-chip ${topic===value?'is-active':''}" data-library-topic="${esc(value)}">${esc(libraryTerm(value))}</button>`).join('')}
      </div>
      </section>
      <section class="listening-topic-filter" aria-label="${esc(l.level)}">
      <span class="o-label">${esc(l.level)}</span>
      <div class="listening-topic-chips">
        <button type="button" class="o-chip ${level?'':'is-active'}" data-library-level="">${esc(l.allLevels)}</button>
        ${(response.filters?.levels||[]).map(value=>`<button type="button" class="o-chip ${level===value?'is-active':''}" data-library-level="${esc(value)}">${esc(value)}</button>`).join('')}
      </div>
      </section>
      <section class="listening-topic-filter" aria-label="${esc(l.tags)}">
      <span class="o-label">${esc(l.tags)}</span>
      <div class="listening-topic-chips">
        <button type="button" class="o-chip ${tag?'':'is-active'}" data-library-tag="">${esc(l.allTags)}</button>
        ${(response.tags||response.filters?.tags||[]).map(value=>`<button type="button" class="o-chip ${tag===value?'is-active':''}" data-library-tag="${esc(value)}">#${esc(libraryTerm(value))}</button>`).join('')}
      </div>
      </section>
    </div>
    ${items.length?(response.sections||[]).map(section=>{
      const sectionItems=(section.item_ids||[]).map(id=>byId.get(id)).filter(Boolean);
      if(!sectionItems.length)return '';
      return `<section class="listening-library-section" data-library-section="${esc(section.id)}"><div class="listening-library-section-head"><div><span class="o-kicker">${esc(l.discover)}</span><h2>${esc(titles[section.id]||section.id)}</h2></div><span>${sectionItems.length}</span></div><div class="listening-library-grid">${sectionItems.map(libraryLessonCard).join('')}</div></section>`;
    }).join(''):`<div class="o-card listening-library-state">${esc(l.empty)}</div>`}
  </div>`;
}

function listeningPage(model,viewId){
  const c=text();
  const l=libraryText();
  const busy=['validating','processing'].includes(model.status);
  const ready=model.status==='ready';
  const recent=ready?[]:listMediaLessons(state.language).filter(item=>!item.lesson_id);
  const intro=skillMasthead({name:c.skillName,purpose:ready?'':l.purpose,stat:null});
  const history=recent.length?`<div class="listening-history"><span class="context-label">${esc(c.recentTitle)}</span><ul>${recent.map(item=>`<li><button type="button" class="listening-history-item" data-lesson-url="${esc(item.source_url)}"><span class="listening-history-title">${esc(item.title||item.source_url)}</span>${item.provider?`<span class="listening-history-meta">${esc(item.provider)}</span>`:''}</button></li>`).join('')}</ul></div>`:'';
  const importPanel=`<section class="listening-my-media-intro"><span class="o-kicker">${esc(l.myMedia)}</span><h2>${esc(l.addOwn)}</h2><p>${esc(l.addOwnLead)}</p></section>
    <form id="mediaImportForm" class="o-card o-import" novalidate>
      <label class="o-label" for="mediaSourceUrl">${esc(c.url)}</label>
      <div class="o-import-row"><input id="mediaSourceUrl" class="o-control" type="url" inputmode="url" placeholder="${esc(c.placeholder)}" value="${esc(model.sourceUrl||'')}" required><button class="o-btn o-btn--primary" type="submit" ${busy?'disabled':''}>${esc(c.prepare)}</button></div>
      <div id="listeningStatus" aria-live="polite">${stateMessage(model.status,model.error)}</div>
    </form>${history}<div class="listening-requirements"><span class="context-label">${esc(c.needTitle)}</span><ul><li>${esc(c.need1)}</li><li>${esc(c.need2)}</li><li>${esc(c.need3)}</li></ul></div>${goalPanel()}`;

  return `<div class="o-page listening-page ${ready?'o-fit':''}" data-listening-view="${viewId}">
    ${ready?`<button type="button" class="o-btn o-btn--outline o-btn--compact listening-back-library" data-back-library>${oIcon('arrowLeft')}<span>${esc(l.backLibrary)}</span></button>`:intro}
    ${ready&&model.payload?.translation?.status==='unavailable'?`<div class="listening-lesson-status" aria-live="polite"><button class="o-btn o-btn--outline o-btn--compact" type="button" data-retry-translation>${esc(c.retryTranslation)}</button></div>`:''}
    ${ready?'':`<div class="listening-primary-tabs" role="tablist"><button type="button" class="o-tab ${model.libraryView!=='my-media'?'is-active':''}" data-library-view="discover" aria-selected="${model.libraryView!=='my-media'}">${oIcon('listen')}<span>${esc(l.discover)}</span></button><button type="button" class="o-tab ${model.libraryView==='my-media'?'is-active':''}" data-library-view="my-media" aria-selected="${model.libraryView==='my-media'}">${oIcon('cloud')}<span>${esc(l.myMedia)}</span></button></div>`}
    ${ready?'':model.libraryView==='my-media'?importPanel:libraryLanding(model)}
    <div id="listeningReady">${ready?workspace(model.payload,model.selected,model):''}</div>
  </div>`;
}

function translationRequest(payload,targetLanguage){
  const asset=payload?.asset||{};
  const transcript=payload?.transcript||{};
  return {
    target_language:targetLanguage,
    asset:{
      asset_id:asset.asset_id,
      source_url:asset.source_url,
      source_provider:asset.source_provider,
      source_type:asset.source_type,
      title:asset.title,
      source_language:asset.source_language,
      processing_state:asset.processing_state,
      duration_ms:asset.duration_ms,
      transcript_available:asset.transcript_available,
    },
    transcript:{
      asset_id:transcript.asset_id,
      source_language:transcript.source_language,
      segments:(transcript.segments||[]).map(segment=>({
        segment_id:segment.segment_id,
        order:segment.order,
        start_ms:segment.start_ms,
        end_ms:segment.end_ms,
        original_text:segment.original_text,
      })),
    },
  };
}

export function createListeningController({importMedia,importStatus,targetLanguage,translateMedia=()=>Promise.resolve(null),onChange=()=>{},onMediaReady=()=>{},onTranslationReady=()=>{},onSelection=()=>{},onModeChange=()=>{},onProcessing=()=>{},onImportTerminal=()=>{},onPracticeProgressSave=()=>{},onShadowingProgressSave=()=>{}}){
  const model={status:'empty',payload:null,error:null,selected:null,manualSelection:false,playingSegmentId:null,jobId:null,sourceUrl:'',original:true,meaning:true,playbackRate:1,mode:'follow',libraryView:'discover',libraryTopic:'',libraryLevel:'',libraryTag:'',library:{status:'loading',data:null},practiceSession:null,shadowingSession:null,practiceValidation:null,practicePersistence:{status:'empty'},shadowingPersistence:{status:'empty'},speakingFeedback:{status:'empty',item:null}};
  const viewId=`listening-${++listeningViewSequence}`;
  let importGeneration=0;
  let backgroundTranslationGeneration=0;
  const practicePersistenceByKey=new Map();
  const shadowingPersistenceByKey=new Map();
  const shadowingLocallyMutated=new Set();
  const shadowingLocalIncrements=new Map();
  const changed=(options={})=>onChange({...model},options);
  const actionAnchor=()=>model.mode==='follow'&&!model.manualSelection
    ?(model.playingSegmentId||model.selected):model.selected;
  const selectedSegment=()=>model.payload?.transcript?.segments?.find(segment=>segment.segment_id===model.selected);
  const practiceProgressPayload=()=>{
    const session=model.practiceSession;
    const segmentId=session?.current_segment_id;
    const segment=segmentId?session.segments[segmentId]:null;
    if(!session||!segment)return null;
    return {
      asset_id:session.asset_id,
      lesson_id:model.payload?.catalog?.lesson_id||'',
      segment_id:segmentId,
      presentation:segment.presentation,
      revealed:Boolean(segment.revealed),
      checked_attempt_count:Number(segment.checked_attempt_count||segment.attempts.length||0),
      best_accuracy_percent:segment.best_result?.accuracy_percent??null,
      best_exact:Boolean(segment.best_result?.exact),
      last_answer:segment.presentation==='prompt'?'':(segment.last_attempt?.answer||segment.draft||''),
    };
  };
  const practiceSaveQueues=new Map();
  const practiceSaveVersions=new Map();
  const shadowingSaveQueues=new Map();
  const shadowingSaveVersions=new Map();
  const practiceKey=(assetId,segmentId)=>`${assetId}:${segmentId}`;
  const setPracticePersistence=(key,status)=>{
    const value={status,key};
    practicePersistenceByKey.set(key,value);
    if(practiceKey(model.practiceSession?.asset_id,model.practiceSession?.current_segment_id)===key){
      model.practicePersistence=value;
      return true;
    }
    return false;
  };
  const shadowingKey=(assetId,segmentId)=>`${assetId}:${segmentId}`;
  const setShadowingPersistence=(key,status)=>{
    const value={status,key};
    shadowingPersistenceByKey.set(key,value);
    if(shadowingKey(model.shadowingSession?.asset_id,model.shadowingSession?.current_segment_id)===key){
      model.shadowingPersistence=value;
      return true;
    }
    return false;
  };
  const shadowingProgressPayload=(segmentIdOverride=null)=>{
    const session=model.shadowingSession;
    const segmentId=segmentIdOverride||session?.current_segment_id;
    const segment=segmentId?session.segments[segmentId]:null;
    if(!session||!segment)return null;
    return {asset_id:session.asset_id,lesson_id:model.payload?.catalog?.lesson_id||'',segment_id:segmentId,completed_rounds:Number(segment.rounds||0)};
  };
  const persistShadowingProgress=(segmentId=null)=>{
    const payload=shadowingProgressPayload(segmentId);
    if(!payload)return false;
    const key=shadowingKey(payload.asset_id,payload.segment_id);
    const version=(shadowingSaveVersions.get(key)||0)+1;
    shadowingSaveVersions.set(key,version);
    setShadowingPersistence(key,'saving');
    changed();
    const previous=shadowingSaveQueues.get(key)||Promise.resolve();
    const queued=previous.catch(()=>{}).then(()=>{
      try{return onShadowingProgressSave(payload);}catch{return Promise.reject(new Error('persistence failed'));}
    });
    shadowingSaveQueues.set(key,queued);
    queued.then(()=>{
      if(shadowingSaveVersions.get(key)===version&&setShadowingPersistence(key,'saved'))changed();
    }).catch(()=>{
      if(shadowingSaveVersions.get(key)===version&&setShadowingPersistence(key,'error'))changed();
    }).finally(()=>{
      if(shadowingSaveQueues.get(key)===queued)shadowingSaveQueues.delete(key);
    });
    return true;
  };
  const persistPracticeProgress=()=>{
    const payload=practiceProgressPayload();
    if(!payload)return false;
    const key=practiceKey(payload.asset_id,payload.segment_id);
    const version=(practiceSaveVersions.get(key)||0)+1;
    practiceSaveVersions.set(key,version);
    setPracticePersistence(key,'saving');
    changed();
    const previous=practiceSaveQueues.get(key)||Promise.resolve();
    const queued=previous.catch(()=>{}).then(()=>{
      try{return onPracticeProgressSave(payload);}catch{return Promise.reject(new Error('persistence failed'));}
    });
    practiceSaveQueues.set(key,queued);
    queued.then(()=>{
      if(practiceSaveVersions.get(key)===version&&setPracticePersistence(key,'saved'))changed();
    }).catch(()=>{
      if(practiceSaveVersions.get(key)===version&&setPracticePersistence(key,'error'))changed();
    }).finally(()=>{
      if(practiceSaveQueues.get(key)===queued)practiceSaveQueues.delete(key);
    });
    return true;
  };
  const mergeTranslation=translated=>{
    model.payload={
      ...model.payload,
      asset:{...model.payload.asset,...translated.asset},
      translations:translated.translations,
      translation:translated.translation,
    };
  };
  const acceptPayload=payload=>{
    model.payload=payload;
    model.status=mediaImportState(payload);
    model.jobId=model.status==='processing'&&typeof payload?.import_job?.job_id==='string'?payload.import_job.job_id:null;
    model.selected=model.status==='ready'?payload.transcript.segments[0].segment_id:null;
    model.manualSelection=false;model.playingSegmentId=null;
    const segmentIds=model.status==='ready'?payload.transcript.segments.map(segment=>segment.segment_id):[];
    model.practiceSession=model.status==='ready'?createListeningPracticeSession({asset_id:payload.asset.asset_id,segment_ids:segmentIds}):null;
    model.shadowingSession=model.status==='ready'?createShadowingPracticeSession({asset_id:payload.asset.asset_id,segment_ids:segmentIds}):null;
    model.practiceValidation=null;
    practicePersistenceByKey.clear();
    shadowingPersistenceByKey.clear();
    shadowingLocallyMutated.clear();
    shadowingLocalIncrements.clear();
    model.practicePersistence={status:'empty',key:model.practiceSession?practiceKey(model.practiceSession.asset_id,model.practiceSession.current_segment_id):''};
    model.shadowingPersistence={status:'empty',key:model.shadowingSession?shadowingKey(model.shadowingSession.asset_id,model.shadowingSession.current_segment_id):''};
    model.speakingFeedback={status:'empty',item:null};
    if(['active','dictation','shadowing'].includes(model.mode)&&!playbackAvailable(payload?.playback))model.mode='follow';
    if(model.status==='processing'&&model.jobId)onProcessing({job_id:model.jobId,source_url:model.sourceUrl});
    else onImportTerminal();
    if(model.status==='ready')onMediaReady(payload,model.selected);
  };
  const translateReadyPayload=generation=>{
    if(model.status!=='ready'||!model.payload?.transcript||model.payload.translation)return;
    const translationGeneration=++backgroundTranslationGeneration;
    const target=targetLanguage();
    let translation;
    try{translation=translateMedia(translationRequest(model.payload,target));}
    catch(error){translation=Promise.reject(error);}
    Promise.resolve(translation)
      .then(translated=>{
        if(generation!==importGeneration||translationGeneration!==backgroundTranslationGeneration)return;
        mergeTranslation(translated);
        onTranslationReady(model.payload);
      })
      .catch(()=>{
        if(generation!==importGeneration||translationGeneration!==backgroundTranslationGeneration)return;
        model.payload.translation={status:'unavailable',target_language:target};
        onImportTerminal();
        onTranslationReady(model.payload);
      });
  };
  return {
    model,
    viewId,
    html:()=>listeningPage(model,viewId),
    setLibrary(status,data=null){model.library={status,data};changed();return true;},
    setLibraryView(value){if(!['discover','my-media'].includes(value))return false;model.libraryView=value;changed();return true;},
    setLibraryTopic(value=''){model.libraryTopic=String(value||'');changed();return true;},
    setLibraryLevel(value=''){model.libraryLevel=String(value||'');changed();return true;},
    setLibraryTag(value=''){model.libraryTag=String(value||'');changed();return true;},
    closeLesson(){model.status='empty';model.payload=null;model.selected=null;model.mode='follow';model.libraryView='discover';changed();return true;},
    async importUrl(sourceUrl){
      const generation=++importGeneration;
      model.libraryView='my-media';
      model.sourceUrl=sourceUrl;
      model.status='validating';model.error=null;model.jobId=null;changed();
      if(!validMediaUrl(sourceUrl)){model.status='unsupported';changed();return;}
      try{
        const payload=await importMedia({source_url:sourceUrl,target_language:targetLanguage(),include_word_timing:true,include_translation:false});
        if(generation!==importGeneration)return;
        acceptPayload(payload);
        translateReadyPayload(generation);
      }catch(error){
        if(generation!==importGeneration)return;
        model.error=error;model.status=mediaImportErrorState(error);model.jobId=null;onImportTerminal();
      }
      changed();
    },
    async pollPending(jobId=model.jobId){
      if(typeof jobId!=='string'||!jobId)return false;
      const generation=importGeneration;
      try{
        const payload=await importStatus({job_id:jobId});
        if(generation!==importGeneration||model.jobId!==jobId)return false;
        acceptPayload(payload);
        translateReadyPayload(generation);
      }catch(error){
        if(generation!==importGeneration||model.jobId!==jobId)return false;
        model.error=error;model.status=mediaImportErrorState(error);model.jobId=null;onImportTerminal();
      }
      changed();
      return true;
    },
    resumePending({job_id='',source_url=''}={}){
      if(typeof job_id!=='string'||!job_id)return false;
      model.jobId=job_id;model.sourceUrl=typeof source_url==='string'?source_url:'';model.status='processing';model.error=null;changed();return true;
    },
    retryTranslation(){
      if(model.status!=='ready'||model.payload?.translation?.status!=='unavailable'||!model.payload?.transcript)return false;
      model.payload.translation=null;model.error=null;changed();
      translateReadyPayload(importGeneration);
      return true;
    },
    select(segmentId){
      if(!model.payload?.transcript?.segments?.some(segment=>segment.segment_id===segmentId))return false;
      model.selected=segmentId;model.manualSelection=true;
      if(model.practiceSession)selectListeningPracticeSegment(model.practiceSession,segmentId);
      if(model.shadowingSession)selectShadowingPracticeSegment(model.shadowingSession,segmentId);
      model.practicePersistence=practicePersistenceByKey.get(practiceKey(model.practiceSession?.asset_id,segmentId))||{status:'empty',key:practiceKey(model.practiceSession?.asset_id,segmentId)};
      model.shadowingPersistence=shadowingPersistenceByKey.get(shadowingKey(model.shadowingSession?.asset_id,segmentId))||{status:'empty',key:shadowingKey(model.shadowingSession?.asset_id,segmentId)};
      model.practiceValidation=null;onSelection(segmentId);changed();return true;
    },
    moveSelection(offset){
      const canonical=model.payload?.transcript?.segments||[];
      const segments=model.mode==='follow'?buildTranscriptDisplayUnits(canonical):canonical;
      const index=model.mode==='follow'
        ?segments.findIndex(segment=>displayUnitContains(segment,actionAnchor()))
        :segments.findIndex(segment=>segment.segment_id===actionAnchor());
      const target=segments[index+offset];
      if(!target)return false;
      model.selected=target.segment_id;model.manualSelection=true;
      if(model.practiceSession)selectListeningPracticeSegment(model.practiceSession,target.segment_id);
      if(model.shadowingSession)selectShadowingPracticeSegment(model.shadowingSession,target.segment_id);
      model.practicePersistence=practicePersistenceByKey.get(practiceKey(model.practiceSession?.asset_id,target.segment_id))||{status:'empty',key:practiceKey(model.practiceSession?.asset_id,target.segment_id)};
      model.shadowingPersistence=shadowingPersistenceByKey.get(shadowingKey(model.shadowingSession?.asset_id,target.segment_id))||{status:'empty',key:shadowingKey(model.shadowingSession?.asset_id,target.segment_id)};
      model.practiceValidation=null;onSelection(target.segment_id);changed();return true;
    },
    restore(payload,selectedId=null,mode='follow'){
      if(mediaImportState(payload)!=='ready')return false;
      model.payload=payload;
      model.status='ready';
      const ids=payload.transcript.segments.map(segment=>segment.segment_id);
      model.selected=ids.includes(selectedId)?selectedId:ids[0]||null;
      model.manualSelection=false;model.playingSegmentId=null;
      model.practiceSession=createListeningPracticeSession({asset_id:payload.asset.asset_id,segment_ids:ids});
      model.shadowingSession=createShadowingPracticeSession({asset_id:payload.asset.asset_id,segment_ids:ids});
      if(model.selected){
        selectListeningPracticeSegment(model.practiceSession,model.selected);
        selectShadowingPracticeSegment(model.shadowingSession,model.selected);
      }
      model.practiceValidation=null;
      practicePersistenceByKey.clear();
      shadowingPersistenceByKey.clear();
      shadowingLocallyMutated.clear();
      shadowingLocalIncrements.clear();
      model.practicePersistence={status:'empty',key:model.practiceSession?practiceKey(model.practiceSession.asset_id,model.practiceSession.current_segment_id):''};
      model.shadowingPersistence={status:'empty',key:model.shadowingSession?shadowingKey(model.shadowingSession.asset_id,model.shadowingSession.current_segment_id):''};
      model.speakingFeedback={status:'empty',item:null};
      model.mode=['follow','active','dictation','shadowing'].includes(mode)?mode:'follow';
      if(['active','dictation','shadowing'].includes(model.mode)&&!playbackAvailable(payload.playback))model.mode='follow';
      onMediaReady(payload,model.selected);
      changed();
      return true;
    },
    setMode(value){
      if(!['follow','active','dictation','shadowing'].includes(value))return false;
      if(isPracticeMode(value)&&(!model.practiceSession||!playbackAvailable(model.payload?.playback)))return false;
      if(value==='shadowing'&&(!model.shadowingSession||!playbackAvailable(model.payload?.playback)))return false;
      model.mode=value;
      if(isPracticeMode(value))selectListeningPracticeSegment(model.practiceSession,model.selected);
      if(value==='shadowing')selectShadowingPracticeSegment(model.shadowingSession,model.selected);
      model.practiceValidation=null;onModeChange(value,model.selected);changed();return true;
    },
    setPracticeDraft(value){
      if(!model.practiceSession)return false;
      const accepted=setListeningPracticeDraft(model.practiceSession,value);
      model.practiceValidation=accepted?null:'answer_too_large';
      return accepted;
    },
    checkPractice(){
      if(!model.practiceSession)return false;
      if(model.practiceValidation==='answer_too_large'){changed();return false;}
      const segment=selectedSegment();
      if(!segment)return false;
      try{
        const state=model.practiceSession.segments[model.selected];
        const result=evaluateListeningReconstruction({source_language:model.payload.asset.source_language,expected:segment.original_text,answer:state.draft});
        recordListeningPracticeAttempt(model.practiceSession,result);
        model.practiceValidation=null;changed();persistPracticeProgress();return true;
      }catch(error){
        model.practiceValidation=error?.code||'evaluation_unavailable';changed();return false;
      }
    },
    revealPractice(){
      if(!model.practiceSession)return false;
      revealListeningPracticeAnswer(model.practiceSession);
      model.practiceValidation=null;changed();persistPracticeProgress();return true;
    },
    hintPractice(){
      if(!model.practiceSession||model.mode!=='dictation')return false;
      advanceListeningPracticeHint(model.practiceSession);changed();return true;
    },
    retryPractice(){
      if(!model.practiceSession)return false;
      retryListeningPracticeSegment(model.practiceSession);
      model.practiceValidation=null;changed();persistPracticeProgress();return true;
    },
    restorePracticeProgress(records){
      if(!model.practiceSession)return false;
      const restoredKeys=[];
      const restored=restoreListeningPracticeProgress(model.practiceSession,records,segmentId=>restoredKeys.push(practiceKey(model.practiceSession.asset_id,segmentId)));
      restoredKeys.forEach(key=>setPracticePersistence(key,'restored'));
      const key=practiceKey(model.practiceSession.asset_id,model.practiceSession.current_segment_id);
      if(!restoredKeys.includes(key))setPracticePersistence(key,'empty');
      model.practicePersistence=practicePersistenceByKey.get(key)||{status:'empty',key};
      changed();
      return restored;
    },
    restoreShadowingProgress(records){
      if(!model.shadowingSession)return false;
      const restored=restoreShadowingPracticeProgress(model.shadowingSession,records);
      const restoredKeys=(Array.isArray(records)?records:[]).filter(record=>record&&record.asset_id===model.shadowingSession.asset_id&&model.shadowingSession.segments[record.segment_id]&&Number.isInteger(Number(record.completed_rounds))&&Number(record.completed_rounds)>=0&&Number(record.completed_rounds)<=1000).map(record=>shadowingKey(model.shadowingSession.asset_id,record.segment_id));
      (Array.isArray(records)?records:[]).forEach(record=>{
        if(!record||record.asset_id!==model.shadowingSession.asset_id||!model.shadowingSession.segments[record.segment_id])return;
        const rounds=Number(record.completed_rounds);
        if(!Number.isInteger(rounds)||rounds<0||rounds>1000)return;
        const key=shadowingKey(model.shadowingSession.asset_id,record.segment_id);
        const localIncrements=shadowingLocalIncrements.get(key)||0;
        if(localIncrements>0){
          model.shadowingSession.segments[record.segment_id].rounds=Math.max(model.shadowingSession.segments[record.segment_id].rounds,rounds+localIncrements);
          persistShadowingProgress(record.segment_id);
        }
      });
      restoredKeys.forEach(key=>{
        if(!shadowingLocallyMutated.has(key))setShadowingPersistence(key,'restored');
      });
      const key=shadowingKey(model.shadowingSession.asset_id,model.shadowingSession.current_segment_id);
      if(!restoredKeys.includes(key))setShadowingPersistence(key,'empty');
      model.shadowingPersistence=shadowingPersistenceByKey.get(key)||{status:'empty',key};
      changed();
      return restored;
    },
    markShadowingProgressUnavailable(){
      if(!model.shadowingSession)return false;
      const assetId=model.shadowingSession.asset_id;
      model.shadowingSession.segment_ids.forEach(segmentId=>setShadowingPersistence(shadowingKey(assetId,segmentId),'unavailable'));
      const key=shadowingKey(assetId,model.shadowingSession.current_segment_id);
      model.shadowingPersistence=shadowingPersistenceByKey.get(key)||{status:'unavailable',key};
      changed();
      return true;
    },
    markPracticeProgressUnavailable(){
      if(!model.practiceSession)return false;
      const assetId=model.practiceSession.asset_id;
      model.practiceSession.segment_ids.forEach(segmentId=>setPracticePersistence(practiceKey(assetId,segmentId),'unavailable'));
      const key=practiceKey(assetId,model.practiceSession.current_segment_id);
      model.practicePersistence=practicePersistenceByKey.get(key)||{status:'unavailable',key};
      changed();
      return true;
    },
    recordShadowingRound(){
      if(!model.shadowingSession)return false;
      const recorded=recordShadowingPracticeRound(model.shadowingSession);
      if(recorded){
        const key=shadowingKey(model.shadowingSession.asset_id,model.shadowingSession.current_segment_id);
        shadowingLocallyMutated.add(key);
        shadowingLocalIncrements.set(key,(shadowingLocalIncrements.get(key)||0)+1);
        changed();persistShadowingProgress();
      }
      return recorded;
    },
    openSpeaking(){
      if(model.status!=='ready'||!model.payload||!model.selected)return false;
      if(!selectSharedMediaSegment(state.language,model.selected))return false;
      return setSharedMediaMode(state.language,model.mode);
    },
    toggleOriginal(value){model.original=value;changed();},
    toggleMeaning(value){model.meaning=value;changed();},
    setPlaybackRate(value){
      if(![.75,1,1.25].includes(value))return false;
      model.playbackRate=value;return true;
    },
    actionAnchor,
    followPlaying(){
      if(model.playingSegmentId){
        model.selected=model.playingSegmentId;
        if(isPracticeMode(model.mode))selectListeningPracticeSegment(model.practiceSession,model.selected);
        if(model.mode==='shadowing'){
          selectShadowingPracticeSegment(model.shadowingSession,model.selected);
          model.shadowingPersistence=shadowingPersistenceByKey.get(shadowingKey(model.shadowingSession?.asset_id,model.selected))||{status:'empty',key:shadowingKey(model.shadowingSession?.asset_id,model.selected)};
        }
      }
      model.manualSelection=false;changed();return actionAnchor();
    },
    setPlayingSegment(segmentId){
      if(!model.payload?.transcript?.segments?.some(segment=>segment.segment_id===segmentId))return false;
      if(model.playingSegmentId===segmentId)return true;
      model.playingSegmentId=segmentId;
      const selectedChanged=['follow','shadowing'].includes(model.mode)&&!model.manualSelection;
      if(selectedChanged){
        model.selected=segmentId;
        if(model.mode==='shadowing'){
          selectShadowingPracticeSegment(model.shadowingSession,segmentId);
          model.shadowingPersistence=shadowingPersistenceByKey.get(shadowingKey(model.shadowingSession?.asset_id,segmentId))||{status:'empty',key:shadowingKey(model.shadowingSession?.asset_id,segmentId)};
        }
      }
      changed({playbackOnly:true,selectedChanged});return true;
    },
  };
}

const smartFollowBindings=new WeakMap();
const SMART_FOLLOW_IDLE_MS=4500;
const SMART_FOLLOW_KEYS=new Set(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End']);

function transcriptRowGeometry(container,row){
  const containerRect=container.getBoundingClientRect();
  const rowRect=row.getBoundingClientRect();
  return {
    rowTop:container.scrollTop+rowRect.top-containerRect.top,
    rowHeight:rowRect.height,
    rowBottom:container.scrollTop+rowRect.bottom-containerRect.top,
  };
}

function scrollTranscriptRow(container,row,{behavior='smooth',focusFraction=null}={}){
  if(!container||!row)return false;
  const {rowTop,rowHeight,rowBottom}=transcriptRowGeometry(container,row);
  const maxTop=Math.max(0,container.scrollHeight-container.clientHeight);
  let targetTop=container.scrollTop;
  if(Number.isFinite(focusFraction)){
    targetTop=rowTop-(container.clientHeight*focusFraction)+(rowHeight/2);
  }else if(rowTop<container.scrollTop){
    targetTop=rowTop-12;
  }else if(rowBottom>container.scrollTop+container.clientHeight){
    targetTop=rowBottom-container.clientHeight+12;
  }else{
    return false;
  }
  container.scrollTo({top:Math.max(0,Math.min(targetTop,maxTop)),behavior});
  return true;
}

function transcriptRowForSelection(root,selectedSegmentId){
  return [...root.querySelectorAll('.listening-segment[data-canonical-segment-ids]')].find(row=>{
    const ids=String(row.dataset.canonicalSegmentIds||'').split(/\s+/).filter(Boolean);
    return ids.includes(selectedSegmentId);
  })||null;
}

function installSmartFollow(root){
  smartFollowBindings.get(root)?.abort?.();

  const abortController=new AbortController();
  const {signal}=abortController;
  let followFrame=null;
  let resumeTimer=null;
  let suspended=false;
  let lastFocusedRow=null;

  const transcriptContainer=target=>{
    const container=target instanceof Element?target.closest('.listening-segments'):null;
    return container&&root.contains(container)?container:null;
  };
  const focusPlaying=({force=false}={})=>{
    const container=root.querySelector('.listening-workspace .listening-segments');
    const row=container?.querySelector('.listening-segment.it-playing-segment');
    if(!row||(!force&&row===lastFocusedRow))return false;

    scrollTranscriptRow(container,row,{focusFraction:.45});
    lastFocusedRow=row;
    return true;
  };
  const scheduleFollow=()=>{
    if(suspended||followFrame!==null)return;
    followFrame=requestAnimationFrame(()=>{
      followFrame=null;
      if(!suspended)focusPlaying();
    });
  };
  const resume=()=>{
    suspended=false;
    resumeTimer=null;
    lastFocusedRow=null;
    focusPlaying({force:true});
  };
  const suspend=event=>{
    if(!transcriptContainer(event.target))return;
    suspended=true;
    if(resumeTimer!==null)clearTimeout(resumeTimer);
    resumeTimer=setTimeout(resume,SMART_FOLLOW_IDLE_MS);
  };
  const suspendFromKey=event=>{
    if(SMART_FOLLOW_KEYS.has(event.key))suspend(event);
  };

  root.addEventListener('orena:media-time',scheduleFollow,{signal});
  root.addEventListener('wheel',suspend,{signal,passive:true});
  root.addEventListener('touchstart',suspend,{signal,passive:true});
  root.addEventListener('touchmove',suspend,{signal,passive:true});
  root.addEventListener('pointerdown',suspend,{signal,passive:true});
  root.addEventListener('keydown',suspendFromKey,{signal});

  const binding={
    abort(){
      if(followFrame!==null)cancelAnimationFrame(followFrame);
      if(resumeTimer!==null)clearTimeout(resumeTimer);
      abortController.abort();
    },
    isSuspended:()=>suspended,
    resumeNow(){
      if(resumeTimer!==null)clearTimeout(resumeTimer);
      resume();
    },
  };

  smartFollowBindings.set(root,binding);
  return binding;
}

export async function renderListening(root,{importMedia=api.importMedia,importStatus=api.mediaImportStatus,translateMedia=api.translateMedia,loadLibrary=api.listeningLibrary,openLibraryLesson=api.listeningLibraryLesson,targetLanguage=supportLanguage,speakingAttempts=api.speakingAttempts,loadListeningProgress=api.listeningProgress,saveListeningProgress=api.saveListeningProgress,loadShadowingProgress=api.shadowingProgress,saveShadowingProgress=api.saveShadowingProgress,saveVocabulary=api.saveLibraryVocabulary}={}){
  let controller;
  let mounted=false;
  let visibleSelection=null;
  let pollTimer=null;
  let renderedAssetId=null;
  let speakingFeedbackKey='';
  const transcriptScrollTops=new Map();
  const viewAbort=new AbortController();
  const smartFollow=installSmartFollow(root);
  const speakingFeedbackFor=(payload,segmentId)=>{
    if(!payload?.asset?.asset_id||!segmentId)return '';
    return `${state.language}|${payload.asset.asset_id}|${segmentId}`;
  };
  let importForm=null;
  const bindImportForm=()=>{
    const form=root.querySelector('#mediaImportForm');
    if(!form||form===importForm)return;
    importForm=form;
    form.addEventListener('submit',event=>{
      event.preventDefault();
      controller.importUrl(root.querySelector('#mediaSourceUrl').value);
    },{signal:viewAbort.signal});
    // A remembered lesson goes straight back in. The field is filled too, so
    // the learner can see what was used and edit it instead of committing.
    root.querySelectorAll('[data-lesson-url]').forEach(button=>{
      button.addEventListener('click',()=>{
        const url=button.dataset.lessonUrl||'';
        if(!url)return;
        const field=root.querySelector('#mediaSourceUrl');
        if(field)field.value=url;
        controller.importUrl(url);
      },{signal:viewAbort.signal});
    });
  };
  const schedulePoll=()=>{
    if(pollTimer)clearTimeout(pollTimer);
    pollTimer=null;
    if(controller.model.status!=='processing'||!controller.model.jobId)return;
    pollTimer=setTimeout(()=>{
      if(!root.querySelector(`[data-listening-view="${controller.viewId}"]`))return;
      controller.pollPending();
    },2500);
  };
  /* Follow mode advances a highlight, not a document.
   *
   * Rebuilding the learning column on every segment change threw the transcript
   * away and built it again - the flicker, once per segment, top to bottom -
   * and with it went the scroll position smart-follow measures from, so the
   * highlight stopped advancing until something forced a full render. Toggling
   * word timing was such a thing, which is why that made it move again.
   *
   * The spec is explicit about this (§2.4 Non-destructive rendering: "media
   * playback → destroys learner text" is on its list of things never to allow).
   * So the playing segment now moves a class and rewrites only the small panel
   * that names the current segment. The transcript the learner is reading is
   * never touched. */
  const advancePlayingSegment=()=>{
    const workspace=root.querySelector('.listening-workspace');
    if(!workspace||workspace.dataset.listeningMode!=='follow')return false;
    const transcript=workspace.querySelector('.listening-segments');
    if(!transcript)return false;

    applyPlayingSegment(root,controller.model.playingSegmentId);

    const selected=controller.model.selected;
    transcript.querySelectorAll('[data-segment-id]').forEach(node=>{
      const aliases=String(node.dataset.canonicalSegmentIds||'').split(/\s+/).filter(Boolean);
      const isCurrent=node.dataset.segmentId===selected||aliases.includes(selected);
      if(isCurrent)node.setAttribute('aria-current','true');
      else node.removeAttribute('aria-current');
    });

    /* The middle column names what is playing, so it does follow the playhead -
       but it is a small panel with nothing to scroll, and rewriting it costs
       the learner nothing. */
    const mid=root.querySelector('.o-listen-mid');
    if(mid){
      const payload=controller.model.payload;
      mid.innerHTML=currentSegmentPanel(payload,selected,controller.model,'follow')
        +vocabularyFocusPanel(payload,selected,'follow',controller.model);
    }
    return true;
  };

  const render=(_model,{playbackOnly=false,selectedChanged=false}={})=>{
    if(playbackOnly&&(isPracticeMode(controller.model.mode)||(controller.model.mode==='shadowing'&&!selectedChanged)))return;
    if(playbackOnly&&mounted&&advancePlayingSegment())return;
    if(mounted&&!root.querySelector(`[data-listening-view="${controller.viewId}"]`))return;
    const payload=controller.model.payload;
    const assetId=payload?.asset?.asset_id||null;
    const workspaceNode=root.querySelector('.listening-workspace');
    const learningColumn=workspaceNode?.querySelector('.listening-learning-column');
    const previousMode=workspaceNode?.dataset?.listeningMode;
    const previousSegments=typeof learningColumn?.querySelector==='function'
      ?learningColumn.querySelector('.listening-segments'):null;
    const preserveFollowScroll=previousMode==='follow'&&smartFollow.isSuspended()&&previousSegments
      ?previousSegments.scrollTop:null;
    if(['active','dictation','shadowing'].includes(previousMode)&&previousSegments)transcriptScrollTops.set(previousMode,previousSegments.scrollTop);
    const preservePlayer=Boolean(
      mounted
      && controller.model.status==='ready'
      && assetId
      && assetId===renderedAssetId
      && root.querySelector('#listeningPlayer')
      && workspaceNode
      && learningColumn
    );
    const mode=payload?listeningMode(payload,controller.model):'follow';
    if(mode==='shadowing'&&controller.model.status==='ready'){
      const key=speakingFeedbackFor(payload,controller.model.selected);
      if(key&&key!==speakingFeedbackKey){
        speakingFeedbackKey=key;
        controller.model.speakingFeedback={status:'loading',item:null};
        Promise.resolve().then(()=>speakingAttempts(1,payload.asset.asset_id,controller.model.selected)).then(response=>{
          if(speakingFeedbackKey!==key)return;
          const items=Array.isArray(response?.items)?response.items:[];
          const item=items.find(candidate=>candidate&&typeof candidate==='object'
            &&String(candidate.language||candidate.language_code||'')===state.language
            &&String(candidate.asset_id||'')===String(payload.asset.asset_id)
            &&String(candidate.segment_id||'')===String(controller.model.selected));
          controller.model.speakingFeedback={status:'ready',item:item||null};
          render(controller.model);
        }).catch(()=>{
          if(speakingFeedbackKey!==key)return;
          controller.model.speakingFeedback={status:'error',item:null};
          render(controller.model);
        });
      }
    }else if(mode!=='shadowing'){
      speakingFeedbackKey='';
      controller.model.speakingFeedback={status:'empty',item:null};
    }
    if(preservePlayer){
      workspaceNode.dataset.listeningMode=mode;
      learningColumn.innerHTML=learningWorkspace(payload,controller.model.selected,controller.model,mode);
      const segments=typeof learningColumn.querySelector==='function'
        ?learningColumn.querySelector('.listening-segments'):null;
      if(segments&&['active','dictation','shadowing'].includes(mode))segments.scrollTop=transcriptScrollTops.get(mode)||0;
      if(segments&&mode==='follow'&&preserveFollowScroll!==null)segments.scrollTop=preserveFollowScroll;
    }else{
      root.innerHTML=controller.html();
      connectMediaPlayer(root,payload?.playback);
      renderedAssetId=controller.model.status==='ready'?assetId:null;
    }
    mounted=true;
    /* This screen re-renders itself on every controller change, and that path
       does not go back through the router's post-render pass - so without this
       the speed control is an upgraded listbox on first paint and a bare
       select after the first import. Enhancement marks what it has done, so
       calling it every time is both correct and cheap. */
    installSelectEnhancements(root);
    bindImportForm();
    root.querySelectorAll('[data-library-view]').forEach(button=>button.addEventListener('click',()=>controller.setLibraryView(button.dataset.libraryView)));
    root.querySelectorAll('[data-library-topic]').forEach(button=>button.addEventListener('click',()=>controller.setLibraryTopic(button.dataset.libraryTopic||'')));
    root.querySelectorAll('[data-library-level]').forEach(button=>button.addEventListener('click',()=>controller.setLibraryLevel(button.dataset.libraryLevel||'')));
    root.querySelectorAll('[data-library-tag]').forEach(button=>button.addEventListener('click',()=>controller.setLibraryTag(button.dataset.libraryTag||'')));
    root.querySelector('[data-back-library]')?.addEventListener('click',()=>controller.closeLesson());
    root.querySelector('[data-retry-library]')?.addEventListener('click',()=>refreshLibrary());
    root.querySelectorAll('[data-library-lesson]').forEach(button=>button.addEventListener('click',async()=>{
      const lessonId=button.dataset.libraryLesson||'';
      if(!lessonId)return;
      button.disabled=true;
      try{
        const payload=await openLibraryLesson(lessonId,targetLanguage());
        const pinyin=payload?.catalog?.pinyin_by_segment||{};
        if(payload?.transcript?.segments){
          payload.transcript={...payload.transcript,segments:payload.transcript.segments.map(segment=>({...segment,pinyin:pinyin[segment.segment_id]||''}))};
        }
        controller.restore(payload,null,'follow');
      }catch{
        button.disabled=false;
        controller.setLibrary('error',controller.model.library?.data||null);
      }
    }));
    root.querySelector('[data-retry-translation]')?.addEventListener('click',()=>controller.retryTranslation());
    root.querySelector('#toggleOriginal')?.addEventListener('change',event=>controller.toggleOriginal(event.target.checked));
    root.querySelector('#toggleMeaning')?.addEventListener('change',event=>controller.toggleMeaning(event.target.checked));
    root.querySelectorAll('button[data-listening-mode]').forEach(button=>button.addEventListener('click',()=>controller.setMode(button.dataset.listeningMode)));

    /* --- listening v2 ------------------------------------------------- */

    /* On a phone the player card's own control row is hidden, so the bar is
       the only place left to change speed. Three steps, the same three the
       select offers. */
    root.querySelector('[data-cycle-rate]')?.addEventListener('click',event=>{
      const rates=[0.75,1,1.25];
      const next=rates[(rates.indexOf(controller.model.playbackRate||1)+1)%rates.length];
      /* The player can refuse - it is an embedded frame and may not be ready -
         so the label only moves when the rate actually changed. */
      if(!setMediaPlaybackRate(root,controller.model.payload?.playback,next))return;
      controller.setPlaybackRate(next);
      const label=`${next.toFixed(2).replace(/0$/,'')}x`;
      const strong=event.currentTarget.querySelector('b');
      if(strong)strong.textContent=label;
      /* The card's select is the same setting; leaving it behind would show two
         different speeds for one player. */
      const select=root.querySelector('#listeningPlaybackRate');
      if(select)select.value=String(next);
    });

    root.querySelector('[data-new-lesson]')?.addEventListener('click',()=>{
      const page=root.querySelector('.listening-page');
      page?.classList.add('is-importing');
      const form=root.querySelector('#mediaImportForm');
      form?.removeAttribute('data-collapsed');
      root.querySelector('#mediaSourceUrl')?.focus();
      form?.scrollIntoView({behavior:'smooth',block:'center'});
    });

    root.querySelector('[data-focus-mode]')?.addEventListener('click',event=>{
      const v=v2Text();
      const page=root.querySelector('.listening-page');
      const on=page?.classList.toggle('is-focus');
      const button=event.currentTarget;
      button.querySelector('span')?.replaceChildren(document.createTextNode(on?v.leaveFocus:v.focusMode));
    });

    root.querySelector('[data-edit-goals]')?.addEventListener('click',()=>{
      const v=v2Text();
      const current=listeningGoals().daily;
      const answer=globalThis.prompt?.(v.goalPrompt,String(current));
      const parsed=Number(answer);
      if(Number.isFinite(parsed)&&parsed>0){
        saveListeningGoal(parsed);
        controller.select(controller.model.selected);
      }
    });

    root.querySelectorAll('[data-say-word]').forEach(button=>button.addEventListener('click',()=>{
      const synth=globalThis.speechSynthesis;
      if(!synth)return;
      try{
        synth.cancel();
        const utterance=new globalThis.SpeechSynthesisUtterance(button.dataset.sayWord);
        utterance.lang=state.language==='zh'?'zh-CN':'en-US';
        synth.speak(utterance);
      }catch{}
    }));

    root.querySelector('[data-toggle-subtitles]')?.addEventListener('click',()=>{
      root.querySelector('.listening-page')?.classList.toggle('is-subtitles-off');
    });

    /* AB loop. Two presses mark the stretch, a third clears it; the clock
       handler below is what actually sends playback back to A. */
    root.querySelector('[data-ab-loop]')?.addEventListener('click',()=>{
      const v=v2Text();
      const loop=controller.model.loop||{};
      const now=Number(controller.model.playheadMs)||0;
      if(loop.a==null){
        controller.model.loop={a:now,b:null};
        toast(v.loopArmed);
      }else if(loop.b==null&&now>loop.a+400){
        controller.model.loop={a:loop.a,b:now};
        toast(v.loopOn);
      }else{
        controller.model.loop={a:null,b:null};
        toast(v.loopOff);
      }
      controller.select(controller.model.selected);
    });
    root.querySelector('[data-shadow-selected]')?.addEventListener('click',()=>controller.setMode('shadowing'));
    root.querySelector('[data-contextual-lookup]')?.addEventListener('click',async()=>{
      const segment=(controller.model.payload?.transcript?.segments||[]).find(item=>item.segment_id===controller.model.selected);
      const context=String(segment?.original_text||'').trim();
      if(!context)return;
      await openDictionary(context,{title:t('dictionary.title'),language:state.language,context});
    });
    /* In the studio a round IS the recorded take, so it is counted when the
       take lands - see the hold-to-repeat wiring below. Counting on click too
       would double it, and click fires before the async stop() resolves, so the
       re-render would arrive one take behind. Anywhere else the attribute still
       means "mark this round complete". */
    const roundButton=root.querySelector('[data-shadow-round]');
    if(roundButton&&!roundButton.hasAttribute('data-shadow-record')){
      roundButton.addEventListener('click',()=>controller.recordShadowingRound());
    }
    root.querySelector('[data-open-speaking]')?.addEventListener('click',()=>{
      /* Preserve the learner's exact studio context for the return trip. The
         shared session already carries asset and segment; this flag lets
         Listening reopen Shadowing instead of silently dropping to Follow. */
      if(controller.openSpeaking())go('speak');
    });
    root.querySelector('#activeListeningAnswer')?.addEventListener('input',event=>controller.setPracticeDraft(event.target.value));
    root.querySelector('#activeListeningForm')?.addEventListener('submit',event=>{
      event.preventDefault();
      controller.setPracticeDraft(root.querySelector('#activeListeningAnswer').value);
      controller.checkPractice();
    });
    root.querySelector('[data-reveal-answer]')?.addEventListener('click',()=>controller.revealPractice());
    root.querySelector('[data-dictation-hint]')?.addEventListener('click',()=>controller.hintPractice());
    root.querySelector('[data-retry-active]')?.addEventListener('click',()=>controller.retryPractice());
    root.querySelector('[data-dictation-next]')?.addEventListener('click',()=>controller.moveSelection(1));
    root.querySelector('[data-dictation-shadow]')?.addEventListener('click',()=>controller.setMode('shadowing'));
    root.querySelector('[data-dictation-slow]')?.addEventListener('click',()=>{
      if(setMediaPlaybackRate(root,controller.model.payload?.playback,.75))controller.setPlaybackRate(.75);
      const segment=(controller.model.payload?.transcript?.segments||[]).find(item=>item.segment_id===controller.model.selected);
      if(segment)replaySegment(root,controller.model.payload?.playback,segment.start_ms,segment.end_ms,.75);
    });
    root.querySelectorAll('[data-save-dictation-word]').forEach(button=>button.addEventListener('click',async()=>{
      const word=String(button.dataset.saveDictationWord||'').trim();
      const segment=(controller.model.payload?.transcript?.segments||[]).find(item=>item.segment_id===controller.model.selected);
      if(!word||!segment)return;
      button.disabled=true;
      try{
        await saveVocabulary({word,phonetic:'',part_of_speech:'',definition:'Dictation word to review',translation_vi:'',source_fragment:segment.original_text,source_kind:'feedback',focus_note:`Listening Dictation · ${controller.model.payload?.asset?.title||''}`});
        toast(libraryText().wordSaved);
      }catch{
        button.disabled=false;
        toast(libraryText().saveFailed);
      }
    }));
    /* The reference gives the player card and the pinned bar the same
       controls, so both copies have to be bound - a single query left the
       bar's play button dead. */
    root.querySelectorAll('[data-toggle-playback]').forEach(button=>button.addEventListener('click',()=>{
      togglePlayback(root,controller.model.payload?.playback);
    }));
    root.querySelector('[data-follow-playing]')?.addEventListener('click',()=>{
      controller.followPlaying();
      smartFollow.resumeNow();
    });
    /* Player transport added by the rebuild. Each of these drives the real
       player; none of them is decoration. */
    /* --- Shadowing Studio ------------------------------------------- */

    const transcriptButton=root.querySelector('[data-view-transcript]');
    if(transcriptButton&&!transcriptButton.dataset.bound){
      transcriptButton.dataset.bound='1';
      transcriptButton.addEventListener('click',()=>controller.setMode('follow'));
    }

    /* A pending round starts the same recorder the big button drives. */
    root.querySelectorAll('[data-shadow-record-round]').forEach(button=>button.addEventListener('click',()=>{
      root.querySelector('[data-shadow-record]')?.focus();
    }));

    root.querySelectorAll('[data-practice-view]').forEach(button=>button.addEventListener('click',()=>{
      const on=button.getAttribute('aria-pressed')!=='true';
      button.setAttribute('aria-pressed',on?'true':'false');
      button.classList.toggle('is-active',on);
      const panel=root.querySelector(`[data-practice-panel="${button.dataset.practiceView}"]`);
      panel?.classList.toggle('hidden',!on);
    }));

    const playTake=index=>{
      const audio=root.querySelector(`[data-take-audio="${index}"]`);
      if(!audio)return;
      root.querySelectorAll('[data-take-audio]').forEach(other=>{ if(other!==audio){other.pause();other.currentTime=0;} });
      const fill=root.querySelector(`[data-take-fill="${index}"]`);
      const elapsed=root.querySelector(`[data-take-elapsed="${index}"]`);
      audio.ontimeupdate=()=>{
        const total=Number.isFinite(audio.duration)&&audio.duration>0?audio.duration:0;
        if(fill)fill.style.width=total?`${Math.min(100,(audio.currentTime/total)*100)}%`:'0%';
        if(elapsed)elapsed.textContent=stamp(audio.currentTime*1000);
      };
      audio.onended=()=>{ if(fill)fill.style.width='0%'; if(elapsed)elapsed.textContent='0:00'; };
      audio.play().catch(()=>{});
    };
    root.querySelectorAll('[data-play-take]').forEach(button=>{
      button.addEventListener('click',()=>playTake(Number(button.dataset.playTake)));
    });
    root.querySelector('[data-play-latest]')?.addEventListener('click',()=>{
      const takes=shadowTakesFor(controller.model.payload,controller.model.selected);
      if(takes.length)playTake(takes.length-1);
    });

    /* Hold to repeat. The take is kept in memory for this session and is never
       uploaded: R6 owns the path that sends audio anywhere, and this is not it. */
    const recordButton=root.querySelector('[data-shadow-record]');
    if(recordButton){
      const status=root.querySelector('[data-record-status]');
      const s=shadowText();
      if(!localAudioRecordingSupported()){
        recordButton.disabled=true;
        if(status)status.textContent=s.recordUnsupported;
      }else{
        let recorder=null;
        let startedAt=0;
        const begin=async event=>{
          event.preventDefault();
          if(recorder)return;
          recorder=createLocalAudioRecorder();
          const ok=await recorder.start();
          if(!ok){ recorder=null; if(status)status.textContent=s.recordUnsupported; return; }
          startedAt=Date.now();
          recordButton.dataset.recording='1';
          if(status)status.textContent=s.recording;
        };
        const end=async()=>{
          if(!recorder)return;
          const active=recorder;
          recorder=null;
          recordButton.removeAttribute('data-recording');
          const snapshot=await active.stop();
          if(status)status.textContent='';
          if(!snapshot?.url)return;
          const payload=controller.model.payload;
          const key=takeKey(payload?.asset?.asset_id,shadowSelection(payload,controller.model.selected));
          const list=shadowTakes.get(key)||[];
          list.push({url:snapshot.url,blob:snapshot.blob,ms:Date.now()-startedAt,at:Date.now()});
          shadowTakes.set(key,list);
          /* Counting the round is also what re-renders the attempts list, so it
             has to happen after the take is stored, not on the click that
             follows the release. */
          controller.recordShadowingRound();
        };
        recordButton.addEventListener('pointerdown',begin);
        recordButton.addEventListener('pointerup',end);
        recordButton.addEventListener('pointerleave',end);
        recordButton.addEventListener('pointercancel',end);
      }
    }

    root.querySelector('[data-expand-import]')?.addEventListener('click',event=>{
      event.currentTarget.closest('form')?.removeAttribute('data-collapsed');
      root.querySelector('#mediaSourceUrl')?.focus();
    });

    root.querySelectorAll('[data-seek]').forEach(button=>button.addEventListener('click',()=>{
      seekBy(root,controller.model.payload?.playback,Number(button.dataset.seek));
    }));
    root.querySelectorAll('[data-toggle-mute]').forEach(control=>control.addEventListener('click',event=>{
      const button=event.currentTarget;
      const muted=toggleMute(root,controller.model.payload?.playback);
      if(muted===null)return;
      button.setAttribute('aria-pressed',muted?'true':'false');
      button.innerHTML=oIcon(muted?'volumeOff':'volume');
      const label=muted?text().unmute:text().mute;
      button.setAttribute('aria-label',label);
      button.title=label;
      /* Both copies show the same state, so the one that was not clicked has to
         be brought along. */
      root.querySelectorAll('[data-toggle-mute]').forEach(other=>{
        if(other===button)return;
        other.setAttribute('aria-pressed',muted?'true':'false');
        other.innerHTML=oIcon(muted?'volumeOff':'volume');
        other.setAttribute('aria-label',label);
        other.title=label;
      });
    }));

    /* Original / Meaning are one choice in the rebuilt transcript, so the tab
       sets both underlying toggles rather than flipping one of them. */
    root.querySelectorAll('[data-transcript-view]').forEach(button=>button.addEventListener('click',()=>{
      const on=button.getAttribute('aria-pressed')!=='true';
      if(button.dataset.transcriptView==='meaning')controller.toggleMeaning(on);
      else controller.toggleOriginal(on);
    }));

    /* The side panel is presentation only, so it switches in place instead of
       going through the controller and re-rendering the transcript. */
    root.querySelectorAll('[data-side-view]').forEach(button=>button.addEventListener('click',()=>{
      const view=button.dataset.sideView;
      root.querySelectorAll('[data-side-view]').forEach(other=>{
        const on=other===button;
        other.classList.toggle('is-active',on);
        other.setAttribute('aria-selected',on?'true':'false');
      });
      root.querySelectorAll('[data-side-panel]').forEach(panel=>{
        panel.classList.toggle('hidden',panel.dataset.sidePanel!==view);
      });
    }));

    root.querySelector('[data-toggle-player]')?.addEventListener('click',event=>{
      const workspaceNode=root.querySelector('.listening-workspace');
      if(!workspaceNode)return;
      const hidden=workspaceNode.toggleAttribute('data-player-hidden');
      const label=hidden?text().showPlayer:text().hidePlayer;
      const copy=event.currentTarget.querySelector('span');
      if(copy)copy.textContent=label;
    });

    root.querySelector('[data-listening-shortcuts]')?.addEventListener('click',()=>{
      const c=text();
      showDialog(c.shortcutsTitle,`<ul class="o-legend">
        <li><span>&uarr; &darr;</span><span>${esc(c.previous)} / ${esc(c.next)}</span></li>
        <li><span>Page&nbsp;Up / Page&nbsp;Down</span><span>${esc(c.select)}</span></li>
        <li><span>Home / End</span><span>${esc(c.select)}</span></li>
      </ul>`);
    });

    /* The transcript, kept as text. M1 forbids downloading the media itself;
       the words the learner has been reading are not the media. */
    root.querySelector('[data-download-transcript]')?.addEventListener('click',()=>{
      const payload=controller.model.payload;
      const units=buildTranscriptDisplayUnits(payload?.transcript?.segments||[]);
      const lines=[payload?.asset?.title||'',payload?.asset?.source_url||'','']
        .concat(units.map(unit=>`[${stamp(unit.start_ms)}] ${unit.original_text}`));
      const blob=new Blob([lines.join('\n')],{type:'text/plain;charset=utf-8'});
      const url=URL.createObjectURL(blob);
      const link=document.createElement('a');
      link.href=url;
      link.download=`orena-transcript-${payload?.asset?.asset_id||'lesson'}.txt`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    });

    /* Notes are this device's own, like the practice state around them. */
    const notes=root.querySelector('#lessonNotes');
    if(notes){
      const key=`orena.listen.notes.${controller.model.payload?.asset?.asset_id||'lesson'}`;
      try{ notes.value=localStorage.getItem(key)||''; }catch{}
      notes.addEventListener('input',()=>{
        try{ localStorage.setItem(key,notes.value); }catch{}
      });
    }

    root.querySelectorAll('[data-select-segment]').forEach(button=>button.addEventListener('click',()=>controller.select(button.dataset.selectSegment)));
    root.querySelector('[data-previous-segment]')?.addEventListener('click',()=>controller.moveSelection(-1));
    root.querySelector('[data-next-segment]')?.addEventListener('click',()=>controller.moveSelection(1));
    root.querySelector('[data-replay-current]')?.addEventListener('click',()=>{
      const payload=controller.model.payload;
      const canonical=payload.transcript.segments;
      const segments=controller.model.mode==='follow'?buildTranscriptDisplayUnits(canonical):canonical;
      const anchor=controller.actionAnchor();
      const segment=controller.model.mode==='follow'
        ?segments.find(item=>displayUnitContains(item,anchor))
        :segments.find(item=>item.segment_id===anchor);
      if(segment)replaySegment(root,payload.playback,segment.start_ms,segment.end_ms,controller.model.playbackRate);
    });
    root.querySelector('#listeningPlaybackRate')?.addEventListener('change',event=>{
      const rate=Number(event.target.value);
      if(setMediaPlaybackRate(root,controller.model.payload.playback,rate))controller.setPlaybackRate(rate);
      else event.target.value=String(controller.model.playbackRate);
    });
    if(controller.model.playbackRate!==1){
      root.querySelector('#listeningPlayer')?.addEventListener('load',()=>setMediaPlaybackRate(root,controller.model.payload.playback,controller.model.playbackRate),{once:true});
    }
    if(controller.model.selected!==visibleSelection){
      const selected=transcriptRowForSelection(root,controller.model.selected);
      const container=selected?.closest('.listening-segments');
      if(container&&selected)scrollTranscriptRow(container,selected);
      visibleSelection=controller.model.selected;
    }
    schedulePoll();
  };
  /* What the learner has kept, for the panel beside the player. Additive: a
     failure leaves that one panel empty rather than the lesson unusable. */
  api.libraryVocabulary()
    .then(saved=>{
      lessonVocabulary=Array.isArray(saved)?saved:(saved?.items||[]);
      const panel=root.querySelector('[data-side-panel="vocabulary"]');
      if(panel)panel.innerHTML=lessonVocabularyMarkup();
    })
    .catch(()=>{ lessonVocabulary=[]; });

  const restoreListeningProgressForAsset=(payload)=>{
    if(!state.me||typeof loadListeningProgress!=='function'||!payload?.asset?.asset_id)return;
    let pending;
    try{pending=loadListeningProgress(payload.asset.asset_id);}catch{pending=Promise.reject(new Error('progress unavailable'));}
    Promise.resolve(pending).then(response=>{
      if(controller.model.practiceSession?.asset_id!==payload.asset.asset_id)return;
      controller.restorePracticeProgress(response?.items||[]);
    }).catch(()=>{
      if(controller.model.practiceSession?.asset_id!==payload.asset.asset_id)return;
      controller.markPracticeProgressUnavailable();
    });
  };
  const restoreShadowingProgressForAsset=(payload)=>{
    if(!state.me||typeof loadShadowingProgress!=='function'||!payload?.asset?.asset_id)return;
    let pending;
    try{pending=loadShadowingProgress(payload.asset.asset_id);}catch{pending=Promise.reject(new Error('shadowing progress unavailable'));}
    Promise.resolve(pending).then(response=>{
      if(controller.model.shadowingSession?.asset_id!==payload.asset.asset_id)return;
      controller.restoreShadowingProgress(response?.items||[]);
    }).catch(()=>{
      if(controller.model.shadowingSession?.asset_id!==payload.asset.asset_id)return;
      controller.markShadowingProgressUnavailable();
    });
  };
  controller=createListeningController({
    importMedia,importStatus,targetLanguage,translateMedia,onChange:render,
    onMediaReady:(payload,selected_segment_id)=>{
      setSharedMediaSession({learning_language:state.language,payload,selected_segment_id});
      // Listening is the skill where returning to the same material matters,
      // so a prepared lesson is worth remembering by name, not just by URL.
      rememberMediaLesson({
        learning_language:state.language,
        source_url:payload?.asset?.source_url||'',
        lesson_id:payload?.catalog?.lesson_id||'',
        title:payload?.asset?.title||'',
        provider:payload?.asset?.source_provider||'',
        selected_segment_id,
        mode:controller?.model?.mode||'follow',
      });
      restoreListeningProgressForAsset(payload);
      restoreShadowingProgressForAsset(payload);
    },
    onPracticeProgressSave:payload=>state.me&&typeof saveListeningProgress==='function'
      ?saveListeningProgress(payload)
      :Promise.resolve(),
    onShadowingProgressSave:payload=>state.me&&typeof saveShadowingProgress==='function'
      ?saveShadowingProgress(payload)
      :Promise.resolve(),
    onTranslationReady:payload=>{
      setSharedMediaSession({learning_language:state.language,payload,selected_segment_id:controller.model.selected});
      render();
    },
    onSelection:segmentId=>{
      selectSharedMediaSegment(state.language,segmentId);
      const payload=controller?.model?.payload;
      rememberMediaLesson({learning_language:state.language,source_url:payload?.asset?.source_url||'',lesson_id:payload?.catalog?.lesson_id||'',title:payload?.asset?.title||'',provider:payload?.asset?.source_provider||'',selected_segment_id:segmentId,mode:controller?.model?.mode||'follow'});
    },
    onModeChange:(mode,segmentId)=>{
      const payload=controller?.model?.payload;
      rememberMediaLesson({learning_language:state.language,source_url:payload?.asset?.source_url||'',lesson_id:payload?.catalog?.lesson_id||'',title:payload?.asset?.title||'',provider:payload?.asset?.source_provider||'',selected_segment_id:segmentId,mode});
    },
    onProcessing:({job_id,source_url})=>setPendingMediaImport({learning_language:state.language,job_id,source_url}),
    onImportTerminal:()=>clearPendingMediaImport(state.language),
  });
  const refreshLibrary=()=>{
    controller.setLibrary('loading');
    let pendingLibrary;
    try{pendingLibrary=loadLibrary(state.language);}
    catch{pendingLibrary=Promise.reject(new Error('library unavailable'));}
    return Promise.resolve(pendingLibrary).then(response=>controller.setLibrary('ready',response)).catch(()=>controller.setLibrary('error'));
  };
  /* The shortcuts the studio advertises. Bound once for the view and inert
     outside shadowing, so they cannot fight the transcript's own arrow-key
     handling in follow mode. */
  root.addEventListener('keydown',event=>{
    if(controller.model.mode!=='shadowing')return;
    if(event.target instanceof Element && event.target.closest('input,textarea,select'))return;
    if(event.key===' '){ event.preventDefault(); togglePlayback(root,controller.model.payload?.playback); }
    else if(event.key==='ArrowRight'){ event.preventDefault(); controller.moveSelection(1); }
    else if(event.key==='ArrowLeft'){ event.preventDefault(); controller.moveSelection(-1); }
  },{signal:viewAbort.signal});

  let lastTick=0;
  root.addEventListener('orena:media-time',event=>{
    const timeMs=Number(event?.detail?.time_ms);
    controller.model.playheadMs=timeMs;

    /* Minutes listened, measured as wall time between ticks while the clock is
       actually moving. A tick gap longer than a couple of seconds means the tab
       was away, so it is dropped rather than counted as listening. */
    const now=Date.now();
    if(lastTick&&now-lastTick<2500)addListenedSeconds((now-lastTick)/1000);
    lastTick=now;

    const loop=controller.model.loop;
    if(loop?.b!=null&&timeMs>loop.b){
      /* replaySegment is the existing seek: it puts the head back at A and
         plays on, which is exactly what a loop does at B. */
      replaySegment(root,controller.model.payload?.playback,loop.a||0,loop.b,controller.model.playbackRate||1);
    }

    const segment=activeCanonicalSegment(controller.model.payload?.transcript?.segments||[],timeMs);
    if(segment)controller.setPlayingSegment(segment.segment_id);

    /* The progress bar is written straight onto the existing nodes rather than
       through a re-render: the clock ticks eight times a second, and
       re-rendering the transcript at that rate would fight smart-follow. */
    const elapsed=Number(event?.detail?.time_ms);
    const total=Number(event?.detail?.duration_ms);
    const fill=root.querySelector('[data-progress-fill]');
    if(fill&&Number.isFinite(elapsed)&&Number.isFinite(total)&&total>0){
      fill.style.width=`${Math.max(0,Math.min(100,(elapsed/total)*100))}%`;
    }
    const elapsedNode=root.querySelector('[data-elapsed]');
    if(elapsedNode&&Number.isFinite(elapsed))elapsedNode.textContent=stamp(elapsed);
    const durationNode=root.querySelector('[data-duration]');
    if(durationNode&&Number.isFinite(total)&&total>0)durationNode.textContent=stamp(total);

    /* The play button shows what the player is doing, read from the player's
       own state rather than from a flag this screen keeps in parallel. */
    const playing=Number(event?.detail?.player_state)===1;
    const wanted=playing?'pause':'play';
    root.querySelectorAll('[data-toggle-playback]').forEach(playButton=>{
      if(playButton.dataset.glyph===wanted)return;
      playButton.dataset.glyph=wanted;
      playButton.innerHTML=oIcon(wanted);
    });
  },{signal:viewAbort.signal});
  root._cleanupScreen=()=>{
    if(pollTimer)clearTimeout(pollTimer);
    smartFollow.abort();
    viewAbort.abort();
    disconnectMediaPlayer(root);
  };
  const pending=getPendingMediaImport(state.language);
  const shared=getSharedMediaSession(state.language);
  // Speaking can ask for a specific remembered lesson. A live import in flight
  // and an already-restored session both outrank it: the learner's current work
  // is never interrupted by a handoff.
  // Speaking's handoff wins over a plain resume: it is an explicit request,
  // where a resume is only a guess about what the learner was doing.
  const handoff=pending?null:takeLessonAutostartContext(state.language);
  const resume=(pending||handoff||shared)?null:resumableLesson(state.language);
  const context=handoff||resume;
  const autostart=context?.source_url||'';
  if(pending)controller.resumePending(pending);
  else if(shared)controller.restore(shared.payload,shared.selected_segment_id,shared.mode);
  else if(context?.lesson_id){
    render();
    Promise.resolve(openLibraryLesson(context.lesson_id,targetLanguage())).then(payload=>{
      const pinyin=payload?.catalog?.pinyin_by_segment||{};
      if(payload?.transcript?.segments){
        payload.transcript={...payload.transcript,segments:payload.transcript.segments.map(segment=>({...segment,pinyin:pinyin[segment.segment_id]||''}))};
      }
      controller.restore(payload,context.selected_segment_id,context.mode||'follow');
    }).catch(()=>controller.setLibrary('error',controller.model.library?.data||null));
  }
  else if(autostart){
    // The field renders model.sourceUrl while an import is in flight or has
    // failed, so the learner can see and edit the link that went wrong. It
    // clears once a lesson is ready, because the form then means "import
    // something new". Setting the DOM here would not survive: importUrl
    // re-renders straight away.
    render();
    controller.importUrl(autostart).then(()=>{
      if(controller.model.status!=='ready'||!context)return;
      // A saved mode is meaningful only alongside the saved canonical segment.
      // If that segment disappeared from a refreshed transcript, keep the
      // safe first-segment/Follow fallback instead of silently resuming a mode
      // against different content.
      const segmentAccepted=Boolean(context.selected_segment_id)
        && controller.select(context.selected_segment_id);
      if(segmentAccepted&&context.mode&&context.mode!=='follow')controller.setMode(context.mode);
      else if(!segmentAccepted&&controller.model.mode!=='follow')controller.setMode('follow');
    });
  }
  else render();
  refreshLibrary();
  return controller;
}
