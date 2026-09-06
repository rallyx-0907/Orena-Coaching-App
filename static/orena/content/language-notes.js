// Prepared support-language notes. They are editorial content, never live feedback.
const notes={
 en:{
  'gave way to':{zh:'这里说店铺逐渐从视野中消失，取而代之的是田野。',vi:'Ở đây, những cửa hàng dần khuất khỏi tầm mắt và nhường chỗ cho đồng ruộng.'},
  'in no hurry':{zh:'并不急着做某事。Mara 开始享受旅途本身。',vi:'Không cảm thấy cần làm điều gì thật nhanh. Mara bắt đầu tận hưởng chính hành trình.'},
  'something that needs tomorrow':{zh:'一种富有想象力的说法：需要你继续照顾的东西。这棵树给了她期待明天的理由。',vi:'Một cách nói giàu hình ảnh về điều cần được tiếp tục chăm sóc. Cái cây cho cô một lý do để mong đợi ngày mai.'},
  'Is anyone sitting here?':{zh:'礼貌而间接地询问这个座位是否有人。',vi:'Cách hỏi thân thiện, gián tiếp xem ghế này có người ngồi chưa.'},
  'It might be a while':{zh:'可能还要等一段时间。“Might” 表示不确定。',vi:'Có thể phải chờ khá lâu. “Might” thể hiện sự không chắc chắn.'},
  'took the long way':{zh:'选择了更费时间的路线。这里的主动选择，表现出新的好奇。',vi:'Chọn con đường mất nhiều thời gian hơn. Ở đây, lựa chọn đó cho thấy sự tò mò mới.'},
  'things you still love':{zh:'“Still” 表示这种感情一直持续，即使东西已经旧了或坏了。',vi:'“Still” cho thấy tình cảm vẫn tiếp tục, dù đồ vật có thể đã cũ hoặc hỏng.'},
 },
 zh:{
  '本来':{en:'An earlier intention that changes. Lin An planned to look at her phone, then became interested in the people around her.',vi:'Ý định ban đầu nhưng sau đó thay đổi. Lâm An định xem điện thoại rồi bị thu hút bởi người trước mặt.'},
  '不急着':{en:'Not feeling a need to do something immediately. She is beginning to enjoy the journey itself.',vi:'Không cảm thấy cần làm ngay. Cô bắt đầu tận hưởng thời gian trên đường.'},
  '舍不得':{en:'Being reluctant to leave or let go because you care about something. Here, a person grows attached to a place.',vi:'Không nỡ rời xa hay từ bỏ vì yêu thích hoặc lưu luyến. Ở đây là tình cảm dần gắn bó với một nơi.'},
  '这里有人吗':{en:'In a café or station, this asks whether a seat is taken, rather than whether a person is physically there.',vi:'Ở quán ăn hay nhà ga, câu này hỏi ghế đã có người ngồi chưa, không phải trước mắt có người hay không.'},
  '还得':{en:'Still needing to do something. Here 得 is pronounced děi and expresses necessity.',vi:'Vẫn cần phải làm điều gì. “得” đọc là děi, thể hiện sự cần thiết.'},
  '迟迟':{en:'Something expected has not happened for a long time. Often used with 没 or 不.',vi:'Điều mong đợi vẫn chưa xảy ra sau một thời gian dài. Thường dùng cùng “没” hoặc “不”.'},
  '特意':{en:'Doing something deliberately, for a particular purpose. The longer route is now a choice.',vi:'Cố ý làm việc gì vì một mục đích cụ thể. Đi đường vòng giờ đã là lựa chọn chủ động.'},
 },
};
export function preparedMeaning(phrase,learningLanguage,supportLanguage){
 if(learningLanguage===supportLanguage)return {text:phrase.definition,language:learningLanguage};
 const value=notes[learningLanguage]?.[phrase.word]?.[supportLanguage];
 return {text:value||phrase.definition,language:value?supportLanguage:learningLanguage};
}
