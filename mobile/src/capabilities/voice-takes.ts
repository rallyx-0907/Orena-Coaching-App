import {File, Paths} from 'expo-file-system';

/** Device-local recording storage; no routing or upload responsibilities. */

export type ShadowTake = {
  /** Where the take lives on this device, for playback only. */
  uri: string;
  /** Wall-clock length of the take, measured while recording. */
  ms: number;
  recordedAt: number;
};

/**
 * The two file operations this needs, behind a seam so the store is testable
 * without a device. expo-file-system 19's `File`/`Paths` API is synchronous.
 */
export type TakeFileSystem = {
  copy: (fromUri: string, toUri: string) => void;
  remove: (uri: string) => void;
  cacheDirectory: string | null;
};

const defaultFileSystem: TakeFileSystem = {
  copy: (fromUri, toUri) => { new File(fromUri).copy(new File(toUri)); },
  remove: (uri) => { new File(uri).delete(); },
  get cacheDirectory() { return Paths.cache.uri; },
};

/** `takeKey()`: takes belong to one segment of one asset. */
export const takeKey = (assetId: string | undefined, segmentId: string | undefined): string =>
  `${assetId || 'asset'}:${segmentId || 'segment'}`;

const extensionOf = (uri: string): string => {
  const match = /\.([A-Za-z0-9]{1,5})(?:\?|$)/.exec(uri);
  return match ? `.${match[1]}` : '.m4a';
};

/**
 * Move a just-finished recording somewhere the next round will not delete.
 * Returns null rather than throwing: a take that cannot be kept must not cost
 * the learner the round they just practised.
 */
export function keepTake(
  recordingUri: string,
  ms: number,
  fs: TakeFileSystem = defaultFileSystem,
  now: number = Date.now(),
): ShadowTake | null {
  const directory = fs.cacheDirectory;
  if (!recordingUri || !directory) return null;
  const separator = directory.endsWith('/') ? '' : '/';
  const target = `${directory}${separator}orena-shadow-${now}-${Math.floor(Math.random() * 1e6)}${extensionOf(recordingUri)}`;
  try {
    fs.copy(recordingUri, target);
    return {uri: target, ms: Math.max(0, Math.round(ms)), recordedAt: now};
  } catch {
    return null;
  }
}

/** Delete takes from the device. Best effort -- a file already gone is fine. */
export function releaseTakes(takes: readonly ShadowTake[], fs: TakeFileSystem = defaultFileSystem): void {
  for (const take of takes) {
    try { fs.remove(take.uri); } catch { /* cache cleanup is best effort */ }
  }
}

