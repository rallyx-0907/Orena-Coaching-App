/* The Speaking audio analysis measures; it does not guess. A known tone must come back as its
   frequency, a rising sweep must rise, silence must be unvoiced, and the drawing must break at
   silence rather than connect across it. */
import assert from 'node:assert/strict';
import { waveformBars, pitchTrack, contour, contourPolylines, analyse } from '../static/orena/capabilities/audio-analysis.js';

const rate = 16000;
const tone = (hz, seconds, amplitude = 0.5) => Float32Array.from({ length: rate * seconds }, (_, i) => amplitude * Math.sin((2 * Math.PI * hz * i) / rate));
const concat = (...parts) => {
  const out = new Float32Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const part of parts) {
    out.set(part, at);
    at += part.length;
  }
  return out;
};

// A 220 Hz tone is measured as 220 Hz.
const steady = pitchTrack(tone(220, 0.5), rate).filter((p) => p.hz);
assert.ok(steady.length > 30);
const median = steady.map((p) => p.hz).sort((a, b) => a - b)[Math.floor(steady.length / 2)];
assert.ok(Math.abs(median - 220) < 3, `measured ${median}`);

// A rising sweep (150 -> 300 Hz) rises.
const sweep = Float32Array.from({ length: rate }, (_, i) => {
  const t = i / rate;
  return 0.5 * Math.sin(2 * Math.PI * (150 * t + 75 * t * t));
});
const rising = pitchTrack(sweep, rate).filter((p) => p.hz);
assert.ok(rising[rising.length - 1].hz > rising[0].hz * 1.6, 'the sweep rises');

// Silence is unvoiced, and the drawing breaks there.
const withGap = concat(tone(200, 0.3), new Float32Array(rate * 0.3), tone(260, 0.3));
const track = pitchTrack(withGap, rate);
assert.ok(track.some((p) => p.hz === null), 'silence is not given a pitch');
const lines = contourPolylines(contour(track));
assert.equal(lines.length, 2, 'two voiced runs, two lines, no line across the silence');

// Contours are relative to the recording's own median.
const shape = contour(pitchTrack(concat(tone(200, 0.3), tone(400, 0.3)), rate)).filter((p) => p.st != null);
assert.ok(Math.abs(Math.max(...shape.map((p) => p.st)) - Math.min(...shape.map((p) => p.st)) - 12) < 1.5, 'an octave is 12 semitones');

// Loudness bars are relative and bounded.
const bars = waveformBars(concat(tone(200, 0.2, 0.1), tone(200, 0.2, 0.8)), 10);
assert.equal(bars.length, 10);
assert.equal(Math.max(...bars), 1);
assert.ok(bars[0] < 0.2 && bars[9] > 0.9);
assert.deepEqual(waveformBars(new Float32Array(0), 4), [0, 0, 0, 0]);

// Nothing for nothing.
const empty = analyse({ samples: new Float32Array(rate * 0.2), sampleRate: rate, duration: 0.2 });
assert.ok(empty.contour.every((p) => p.st === null));
assert.deepEqual(contourPolylines(empty.contour), []);

// A lone glitch frame and an octave jump are not drawn as pitch movement.
{
  const points = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => ({ t: i / 100, hz: 200 }));
  points[5].hz = 400; // one octave error inside a steady tone
  const smoothed = contour(points);
  assert.ok(smoothed.every((p) => p.st === null || Math.abs(p.st) < 1), 'a one-frame octave error is smoothed away');
  const short = contour([{ t: 0, hz: null }, { t: 0.01, hz: 220 }, { t: 0.02, hz: 221 }, { t: 0.03, hz: null }]);
  assert.ok(short.every((p) => p.st === null), 'a voiced run shorter than 60 ms is not drawn');
  const jump = [...Array(8)].map((_, i) => ({ t: i / 100, st: 0 })).concat([...Array(8)].map((_, i) => ({ t: (8 + i) / 100, st: 6 })));
  assert.equal(contourPolylines(jump).length, 2, 'a jump of more than 3 semitones breaks the line');
}

console.log('Speaking audio analysis (waveform, YIN pitch, contour): PASS');
