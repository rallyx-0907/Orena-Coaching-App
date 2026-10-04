import { defineCopy } from '../../copy/index.js';
const keys = ['choose','play','stop','next','finish','again','correct','incorrect','question','result','evidence','replayEvidence'];
export const t = defineCopy('listeningQuestions', {
  layers: Object.fromEntries(keys.map(key => [key,'interface'])),
  en: {choose:'Choose lesson',play:'Listen',stop:'Stop',next:'Next question',finish:'See result',again:'Try again',correct:'Correct',incorrect:'Incorrect',question:'Question {n}/{total}',result:'This practice: {n}/{total} correct',evidence:'What was said',replayEvidence:'Hear the evidence'},
  vi: {choose:'Chọn bài khác',play:'Nghe',stop:'Dừng',next:'Câu tiếp theo',finish:'Xem kết quả',again:'Làm lại',correct:'Đúng',incorrect:'Chưa đúng',question:'Câu {n}/{total}',result:'Lượt luyện này: đúng {n}/{total} câu',evidence:'Nội dung đã nghe',replayEvidence:'Nghe câu làm căn cứ'},
  zh: {choose:'选择其他课程',play:'听音频',stop:'停止',next:'下一题',finish:'查看结果',again:'再练一次',correct:'正确',incorrect:'不正确',question:'第 {n}/{total} 题',result:'本次练习：答对 {n}/{total} 题',evidence:'听到的内容',replayEvidence:'听依据片段'},
});
