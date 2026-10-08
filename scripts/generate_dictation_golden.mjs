/* Regenerates tests/fixtures/dictation_golden.json by RUNNING the browser evaluator. The Python port
   (writing_coach/dictation_evaluator.py) and scripts/test_dictation_golden.mjs both consume the file,
   so drift on either side fails CI (D4 I18). Run: node scripts/generate_dictation_golden.mjs */
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { evaluateListeningReconstruction } from '../static/orena/capabilities/dictation-evaluator.js';

const long = (unit, n) => Array.from({ length: n }, () => unit).join(' ');
const cases = [
  ['en', 'Listen to this idea.', 'Listen to this idea.'],
  ['en', 'Listen to this idea.', 'LISTEN TO THIS IDEA'],
  ['en', 'Listen, to this idea!', 'Listen to this idea'],
  ['en', 'Listen to this complete idea', 'Listen to this idea'],
  ['en', 'Listen to this idea', 'Please listen to this idea'],
  ['en', 'Listen to this idea', 'Listen to that idea'],
  ['en', "Don't stop listening", 'Dont stop listening'],
  ['en', 'Don’t stop listening', "Don't stop listening"],
  ['en', 'Donʼs place', "don's place"],
  ['en', 'well-known facts', 'well known facts'],
  ['en', 'well‐known facts', 'well-known facts'],
  ['en', 'well−known facts', 'well-known facts'],
  ['en', 'It costs 12 dollars', 'it costs twelve dollars'],
  ['en', 'Ｈｅｌｌｏ ｗｏｒｌｄ', 'hello world'],
  ['en', 'café au lait', 'cafe au lait'],
  ['en', 'café au lait', 'café au lait'],
  ['en', 'ORDER   of\tthe\nday', 'order of the day'],
  ['en', 'A B　C', 'a b c'],
  ['en', 'straße', 'STRASSE'],
  ['en', 'ΑΣ', 'ας'],
  ['en', 'İstanbul', 'i̇stanbul'],
  ['en', 'rock ’n’ roll', "rock 'n' roll"],
  ['en', '...', 'hello'],
  ['en', 'hello', '...'],
  ['en', 'hello', ''],
  ['en', '', 'hello'],
  ['en', '   ', 'hello'],
  ['en', 'one two three four', 'one two three four five six seven'],
  ['en', 'a b c d e f g h i j', 'j i h g f e d c b a'],
  ['en', 'a', 'b'],
  ['en', 'one two three', 'one two four'],
  ['en', 'hello world', 'x'.repeat(2001)],
  ['en', 'hello world', 'x'.repeat(2000)],
  ['en', 'hello world', '😀'.repeat(1001)],
  ['en', 'hello world', '😀'.repeat(1000)],
  ['en', long('word', 501), 'word'],
  ['en', 'word', long('word', 501)],
  ['en', long('word', 500), long('word', 500)],
  ['en', 'naïve café', 'naive cafe'],
  ['en', '你好 world', '你好 world'],
  ['en', 'ab12 cd', 'ab12 cd'],
  ['en', 'x² + y²', 'x2 + y2'],
  ['zh', '我们一起练习听力。', '我们一起练习听力。'],
  ['zh', '我们一起练习听力！', '我们一起练习听力'],
  ['zh', '我 们 一 起 练 习', '我们一起练习'],
  ['zh', '我们一起练习听力', '我们一起练习'],
  ['zh', '我们一起练习', '我们一起练习听力'],
  ['zh', '我们练习听力', '你们练习听力'],
  ['zh', '我用 GPT-4 学习 123', '我用 gpt-4 学习 123'],
  ['zh', '我用GPT-4学习', '我用gpt4学习'],
  // LEX-041: a Latin word ends where the Han text begins.
  ['zh', '另外用MonoBook 、MySkin等版本也有相同功能', '另外用MonoBook、MySkin等版本也有相同功能'],
  ['zh', '另外用MonoBook 、MySkin等版本也有相同功能', '另外用MonoBook MySkin版本有相同功能'],
  ['zh', 'abc中文def', 'abc中文def'],
  ['zh', "I don't know不知道", 'I dont know不知道'],
  ['zh', '１２３块', '123块'],
  ['zh', '你好——世界', '你好 世界'],
  ['zh', '〇一二三', '〇一二三'],
  ['zh', '々人', '人人'],
  ['zh', '。！？', '你'],
  ['zh', '你', ''],
  ['zh', '', '你'],
  ['zh', '你好', '你'.repeat(2001)],
  ['zh', '你好', '你'.repeat(2000)],
  ['zh', '你好', '你'.repeat(600)],
  ['zh', '你'.repeat(501), '你'],
  ['zh', '你'.repeat(500), '你'.repeat(500)],
  ['zh', '\u{20000}\u{2a6d6}中', '\u{20000}\u{2a6d6}中'],
  ['zh', '豈中', '豈中'],
  ['zh', '⼀⺀', '一⺀'],
  ['zh', '今天天气很好', '今天天气很'],
  ['zh', '我爱你', '我爱你们们们'],
  ['zh', '一二三四五六七', '一二三'],
  ['zh', '一二三四五六七八九十一', '一二三'],
  ['zh', 'こんにちは', 'こんにちは'],
  ['zh', 'Café 你好', 'café 你好'],
  ['xx', 'Listen to this', 'listen to this'],
];

const results = cases.map(([source_language, expected, answer]) => {
  const input = { source_language, expected, answer };
  try {
    return { input, result: evaluateListeningReconstruction(input) };
  } catch (error) {
    return { input, error: error.code };
  }
});
const target = fileURLToPath(new URL('../tests/fixtures/dictation_golden.json', import.meta.url));
writeFileSync(target, `${JSON.stringify({ generated_by: 'scripts/generate_dictation_golden.mjs (runs static/orena/capabilities/dictation-evaluator.js)', cases: results }, null, 1)}\n`, 'utf8');
console.log(`wrote ${results.length} golden vectors to tests/fixtures/dictation_golden.json`);
