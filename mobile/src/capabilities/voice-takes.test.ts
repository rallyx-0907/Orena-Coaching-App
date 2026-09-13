import {keepTake, releaseTakes, takeKey, type ShadowTake, type TakeFileSystem} from './voice-takes';

const fakeFs = (overrides: Partial<TakeFileSystem> = {}): TakeFileSystem & {copies: [string, string][]; removed: string[]} => {
  const copies: [string, string][] = [];
  const removed: string[] = [];
  return {
    copies, removed,
    cacheDirectory: 'file:///cache/',
    copy: (from, to) => { copies.push([from, to]); },
    remove: (uri) => { removed.push(uri); },
    ...overrides,
  };
};

describe('takeKey', () => {
  it('scopes takes to one segment of one asset', () => {
    expect(takeKey('asset-1', 'segment-2')).toBe('asset-1:segment-2');
    expect(takeKey('asset-1', 'segment-2')).not.toBe(takeKey('asset-1', 'segment-3'));
  });

  it('stays a usable key when the lesson is not resolved yet', () => {
    expect(takeKey(undefined, undefined)).toBe('asset:segment');
  });
});

describe('keepTake', () => {
  /* TransientAudioService deletes the previous recording on the next
     startRecording(), so a take that is not copied out of the way is gone the
     moment the learner starts the next round. */
  it('copies the recording out of the transient slot', () => {
    const fs = fakeFs();
    const take = keepTake('file:///tmp/recording.m4a', 2400, fs, 1000);
    expect(take).not.toBeNull();
    expect(fs.copies).toHaveLength(1);
    expect(fs.copies[0]![0]).toBe('file:///tmp/recording.m4a');
    expect(take!.uri).toBe(fs.copies[0]![1]);
    expect(take!.ms).toBe(2400);
  });

  it('keeps the take inside the app cache, not a shared location', () => {
    const fs = fakeFs();
    expect(keepTake('file:///tmp/r.m4a', 100, fs, 1)!.uri.startsWith('file:///cache/')).toBe(true);
  });

  it('preserves the recording extension so playback knows the format', () => {
    const fs = fakeFs();
    expect(keepTake('file:///tmp/r.wav', 100, fs, 1)!.uri.endsWith('.wav')).toBe(true);
  });

  it('never gives two rounds the same file', () => {
    const fs = fakeFs();
    const first = keepTake('file:///tmp/r.m4a', 100, fs, 1)!;
    const second = keepTake('file:///tmp/r.m4a', 100, fs, 2)!;
    expect(first.uri).not.toBe(second.uri);
  });

  it('reports failure instead of throwing, so a lost file does not cost the round', () => {
    const fs = fakeFs({copy: () => { throw new Error('no space'); }});
    expect(keepTake('file:///tmp/r.m4a', 100, fs, 1)).toBeNull();
  });

  it('refuses when there is nowhere to keep it', () => {
    expect(keepTake('file:///tmp/r.m4a', 100, fakeFs({cacheDirectory: null}), 1)).toBeNull();
    expect(keepTake('', 100, fakeFs(), 1)).toBeNull();
  });

  it('never records a negative length', () => {
    expect(keepTake('file:///tmp/r.m4a', -50, fakeFs(), 1)!.ms).toBe(0);
  });
});

describe('releaseTakes', () => {
  /* Leaving the studio has to remove the recordings: the web keeps takes only
     in memory for the session, and this is how that guarantee is met on a
     device that had to write them to disk. */
  it('deletes every take from the device', () => {
    const fs = fakeFs();
    const takes: ShadowTake[] = [
      {uri: 'file:///cache/a.m4a', ms: 1, recordedAt: 1},
      {uri: 'file:///cache/b.m4a', ms: 1, recordedAt: 2},
    ];
    releaseTakes(takes, fs);
    expect(fs.removed).toEqual(['file:///cache/a.m4a', 'file:///cache/b.m4a']);
  });

  it('keeps deleting after one file is already gone', () => {
    const removed: string[] = [];
    const fs = fakeFs({remove: (uri) => { if (uri.endsWith('/a.m4a')) throw new Error('missing'); removed.push(uri); }});
    releaseTakes([
      {uri: 'file:///cache/a.m4a', ms: 1, recordedAt: 1},
      {uri: 'file:///cache/b.m4a', ms: 1, recordedAt: 2},
    ], fs);
    expect(removed).toEqual(['file:///cache/b.m4a']);
  });
});

