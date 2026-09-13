import {directMediaKind, listeningUnits, playbackAvailable, posterSource, reconstructionDiff, segmentAt, stamp, textMatch} from './transcript';

describe('stamp', () => {
  it('reads media positions as M:SS', () => {
    expect(stamp(0)).toBe('0:00');
    expect(stamp(65_400)).toBe('1:05');
    expect(stamp(600_000)).toBe('10:00');
  });

  it('never renders a negative or non-finite position', () => {
    expect(stamp(-1)).toBe('0:00');
    expect(stamp(Number.NaN)).toBe('0:00');
  });
});

describe('playbackAvailable', () => {
  const embed = {kind: 'embed', provider: 'youtube', url: 'https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ'};

  it('accepts the only playback shape the backend produces', () => {
    expect(playbackAvailable(embed)).toBe(true);
  });

  it('gates Active and Shadowing when there is nothing playable', () => {
    expect(playbackAvailable(undefined)).toBe(false);
    expect(playbackAvailable({...embed, url: 'https://www.youtube-nocookie.com/watch'})).toBe(false);
    expect(playbackAvailable({...embed, provider: 'vimeo'})).toBe(false);
  });

  /**
   * The curated real-media lessons. Native shipped video support after the web,
   * and while it was missing these two lessons were real videos in a browser
   * and "playback unavailable" on a phone. That is the regression these guard.
   */
  const enVideo = {kind: 'video', provider: 'wikimedia-commons', url: 'https://upload.wikimedia.org/wikipedia/commons/transcoded/b/bc/cosmic.webm/cosmic.webm.480p.vp9.webm'};
  const zhVideo = {kind: 'video', provider: 'wikimedia-commons', url: 'https://upload.wikimedia.org/wikipedia/commons/transcoded/b/b1/zh.ogv/zh.ogv.480p.vp9.webm'};

  it('never degrades curated EN or ZH video to unavailable', () => {
    expect(playbackAvailable(enVideo)).toBe(true);
    expect(playbackAvailable(zhVideo)).toBe(true);
    expect(directMediaKind(enVideo)).toBe('video');
    expect(directMediaKind(zhVideo)).toBe('video');
  });

  it('keeps curated audio on the audio adapter', () => {
    const audio = {kind: 'audio', provider: 'wikimedia-commons', url: 'https://upload.wikimedia.org/wikipedia/commons/1/1e/pen.ogg'};
    expect(playbackAvailable(audio)).toBe(true);
    expect(directMediaKind(audio)).toBe('audio');
    expect(directMediaKind(embed)).toBeNull();
  });

  it('refuses direct media from anywhere the rights review did not cover', () => {
    for (const bad of [
      {...enVideo, url: 'https://evil.example/x.webm'},
      {...enVideo, provider: 'evil'},
      {...enVideo, url: 'http://upload.wikimedia.org/x.webm'},
      {...enVideo, kind: 'stream'},
      // Credentials and a port both keep the allowlisted hostname, so they have
      // to be refused by name rather than left to the shape of a pattern.
      {...enVideo, url: 'https://user:password@upload.wikimedia.org/x.webm'},
      {...enVideo, url: 'https://upload.wikimedia.org:8443/x.webm'},
      {...enVideo, url: 'https://upload.wikimedia.org.evil.example/x.webm'},
    ]) {
      expect(playbackAvailable(bad)).toBe(false);
      expect(directMediaKind(bad)).toBeNull();
    }
  });
});

describe('posterSource', () => {
  it('accepts a reviewed Commons poster and rejects every other origin', () => {
    expect(posterSource('https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/x.jpg')).toBe('https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/x.jpg');
    // A YouTube lesson's poster lives on YouTube's image CDN.
    expect(posterSource('https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg')).toBe('https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg');
    // Playback is still Commons-only; a poster host must not become a media host.
    expect(directMediaKind({kind: 'video', provider: 'wikimedia-commons', url: 'https://i.ytimg.com/x.webm'})).toBeNull();
    for (const bad of [
      'https://evil.example/x.jpg',
      'http://upload.wikimedia.org/x.jpg',
      'https://user:password@upload.wikimedia.org/x.jpg',
      'https://upload.wikimedia.org:8443/x.jpg',
      'https://upload.wikimedia.org.evil.example/x.jpg',
      'javascript:alert(1)',
    ]) {
      expect(posterSource(bad)).toBeNull();
    }
    expect(posterSource(undefined)).toBeNull();
    expect(posterSource('')).toBeNull();
  });
});

describe('listeningUnits', () => {
  it('counts words outside Chinese and characters inside it', () => {
    expect(listeningUnits('The quick brown fox', 'en')).toHaveLength(4);
    expect(listeningUnits('我今天很好', 'zh')).toHaveLength(5);
  });

  it('ignores spacing in a Chinese line', () => {
    expect(listeningUnits('我 今天 很好', 'zh')).toHaveLength(5);
  });
});

describe('textMatch', () => {
  it('reports an exact reconstruction as exact', () => {
    expect(textMatch('the quick brown fox', 'The quick brown fox', 'en')).toEqual({accuracy_percent: 100, exact: true});
  });

  it('uses ordered edit distance so wrong order does not receive full credit', () => {
    const result = textMatch('fox brown quick the', 'The quick brown fox', 'en');
    expect(result.exact).toBe(false);
    expect(result.accuracy_percent).toBeLessThan(100);
  });

  it('scores a partial reconstruction by ordered overlap', () => {
    expect(textMatch('the quick', 'The quick brown fox', 'en')).toEqual({accuracy_percent: 50, exact: false});
  });

  it('does not credit a repeated unit twice', () => {
    expect(textMatch('the the the the', 'the quick brown fox', 'en').accuracy_percent).toBe(25);
  });

  it('works the same way for Chinese', () => {
    expect(textMatch('我今天很好', '我今天很好', 'zh').exact).toBe(true);
  });
});

describe('language-aware dictation feedback', () => {
  it('ignores harmless punctuation and capitalization', () => {
    expect(textMatch('LISTEN to this idea', 'Listen, to this idea!', 'en').exact).toBe(true);
  });

  it('marks missing and extra units without scoring punctuation', () => {
    expect(reconstructionDiff('Take train safely home', 'Take the train home.', 'en').map((item) => item.status)).toEqual(['correct', 'missing', 'correct', 'extra', 'correct']);
    expect(reconstructionDiff('\u6211 \u4eca\u5929 \u597d', '\u6211\u4eca\u5929\u5f88\u597d\u3002', 'zh').map((item) => item.status)).toEqual(['correct', 'correct', 'correct', 'missing', 'correct']);
  });
});

describe('segmentAt', () => {
  const segments = [
    {segment_id: 'a', start_ms: 0, end_ms: 2000},
    {segment_id: 'b', start_ms: 2000, end_ms: 4000},
  ];

  it('finds the segment that owns a position', () => {
    expect(segmentAt(segments, 1999)).toBe('a');
    expect(segmentAt(segments, 2000)).toBe('b');
  });

  it('returns nothing past the end of the transcript', () => {
    expect(segmentAt(segments, 9000)).toBeNull();
  });
});
