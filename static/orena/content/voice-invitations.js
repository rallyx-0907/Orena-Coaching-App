// Orena-authored situations, not simulated conversation history or recommendations.
// `context` is the authored delivery context (how the learner would really say it): Situation
// Reaction's chip above the scenario (D-139 HD-13). It is written in the learning language, like the
// scenario it belongs to.
const invitations = {
  en: [
    {
      key: 'invitation',
      title: 'Make room for someone',
      prompt:
        'A friend has just moved to your city. Invite them somewhere you love. Tell them why you want to take them there.',
      cue: 'Picture one person. Give them a reason to say yes.',
      context: 'Chat message to a friend',
    },
    {
      key: 'change',
      title: 'A small change, a better day',
      prompt:
        'Tell someone about a small change that made your day better. What was it like before, and what happened next?',
      cue: 'Start with a moment, then tell us what changed.',
      context: 'Voice message to a friend',
    },
    {
      key: 'opinion',
      title: 'See it another way',
      prompt:
        'A friend thinks being busy means being productive. Do you agree? Offer your view and one example.',
      cue: 'You can disagree warmly. Help the other person see what you see.',
      context: 'Talking it over with a friend',
    },
  ],
  zh: [
    {
      key: 'invitation',
      title: '带一个人认识你的城市',
      prompt:
        '一位朋友刚搬到你的城市。邀请对方去一个你喜欢的地方，说说你为什么想带他去。',
      cue: '想象一个具体的人，给对方一个愿意出门的理由。',
      context: '发给朋友的聊天消息',
    },
    {
      key: 'change',
      title: '一个小改变，让日子更好',
      prompt:
        '告诉一个朋友，什么小改变让你的一天变得更好。以前是什么样的？后来发生了什么？',
      cue: '从一个具体的瞬间说起，再说说改变。',
      context: '发给朋友的语音消息',
    },
    {
      key: 'opinion',
      title: '换个角度看',
      prompt:
        '朋友觉得忙碌就代表有成效。你同意吗？说说你的看法，再举一个例子。',
      cue: '不同意也可以温和地表达，让对方看见你的角度。',
      context: '和朋友当面聊聊',
    },
  ],
};
export const voiceInvitations = (language) =>
  invitations[language] || invitations.en;
