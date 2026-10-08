/* A Writing draft kept with the account, when the deployment keeps work there.

   A draft is a snapshot: the words and the Writing task they answer
   ({text, task}). The two travel together everywhere - agreement, adoption,
   conflict and both conflict choices - so a draft is never shown, kept or sent
   under another task than its own.

   The device always keeps the draft too (learner memory), so nothing here can
   lose words: the account copy is added when `/api/account-backbone` says
   `active`. The room says "kept with your account" only when this exact
   snapshot is known to be the account's copy - a save the server acknowledged,
   or a read that showed the server already holds it. Until then, and whenever
   anything fails, it says "on this device".

   Versions decide, not clocks. The device remembers the version it last
   agreed with the server and a digest of the snapshot it agreed on, plus the
   digests of saves it sent whose answer has not arrived:

   - the server has nothing yet: a draft already on the device is sent;
   - the device's snapshot is the one it last agreed on: the server's is the
     draft (another device may have moved it on);
   - the server holds a save this device sent but never heard back about: that
     is this device's own predecessor, agreed on, and anything typed since is
     sent on top of it - not a conflict;
   - the device changed and the server did not move: the device's is sent;
   - both moved: the learner is shown the other device's snapshot and
     chooses. Nothing is merged, and the box is never replaced silently. */

let statePromise = null;

export function accountWorkState(api) {
  if (!statePromise)
    statePromise = api.accountBackbone().then(
      (answer) => String(answer?.state || 'disabled'),
      () => 'unknown',
    );
  return statePromise;
}

// Test seam: a fresh page asks again.
export function forgetAccountWorkState() {
  statePromise = null;
}

/* FNV-1a over the UTF-16 code units: small, stable and enough to tell "the
   snapshot I last agreed on" from "something else". Not a security digest. */
export function textDigest(text) {
  let hash = 0x811c9dc5;
  const value = String(text || '');
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

export const snapshot = (text = '', task = '') => ({
  text: String(text || ''),
  task: String(task || '').slice(0, 240),
});
// The unit separator cannot be typed into either field, so no pair of
// (text, task) spells another pair.
const SEPARATOR = String.fromCharCode(31);
export const snapshotDigest = (value) => textDigest(`${value.text}${SEPARATOR}${value.task}`);
const same = (a, b) => a.text === b.text && a.task === b.task;
const isEmpty = (value) => !value.text.trim() && !value.task.trim();

const syncKey = (id) => `${id}::sync`;
const pendingKey = (id) => `${id}::pending`;

export function readAgreement(memory, id) {
  const raw = memory.value.expressions[syncKey(id)] || '';
  const match = /^(\d+):([0-9a-f]{8})$/.exec(raw);
  return match
    ? { version: Number(match[1]), digest: match[2] }
    : { version: 0, digest: '' };
}

/* Saves sent from one agreed version and not yet answered: the base version
   and the digests of what was sent. Kept on the device so a reload after a
   lost answer still recognises its own write. */
export function readPending(memory, id) {
  const raw = memory.value.expressions[pendingKey(id)] || '';
  const match = /^(\d+):((?:[0-9a-f]{8},?){1,8})$/.exec(raw);
  return match
    ? { version: Number(match[1]), digests: match[2].split(',').filter(Boolean) }
    : { version: -1, digests: [] };
}

function remember(memory, key, value) {
  try {
    memory.write(key, value);
  } catch {
    // Device memory refused; the account copy still stands on its own.
  }
}

function agree(memory, id, version, value) {
  remember(memory, syncKey(id), `${version}:${snapshotDigest(value)}`);
  remember(memory, pendingKey(id), '');
}

function markSent(memory, id, version, value) {
  const pending = readPending(memory, id);
  const digests = pending.version === version ? pending.digests : [];
  const digest = snapshotDigest(value);
  const next = [...digests.filter((d) => d !== digest), digest].slice(-8);
  remember(memory, pendingKey(id), `${version}:${next.join(',')}`);
}

// Is `server` a save this device sent from `pending.version`?
function ownPredecessor(memory, id, server) {
  const pending = readPending(memory, id);
  return (
    pending.version >= 0 &&
    server.version === pending.version + 1 &&
    pending.digests.includes(snapshotDigest(server))
  );
}

export function draftSync({
  api,
  memory,
  id,
  onWhere = () => {},
  onElsewhere = () => {},
  delay = 1200,
  schedule = (fn, ms) => setTimeout(fn, ms),
  cancel = (handle) => clearTimeout(handle),
}) {
  let active = false,
    elsewhere = null,
    timer = null,
    sending = null,
    queued = null,
    attempt = null;

  const say = (where) => onWhere(where);

  function showElsewhere(server) {
    elsewhere = server;
    say('device');
    onElsewhere(server);
  }

  async function send(value) {
    if (sending) {
      queued = value;
      return sending;
    }
    const { version } = readAgreement(memory, id);
    // The same snapshot from the same version is the same operation: a retry
    // after a lost answer replays instead of conflicting with itself.
    if (!attempt || attempt.version !== version || !same(attempt.value, value))
      attempt = { version, value, operationId: `op-${crypto.randomUUID()}` };
    markSent(memory, id, version, value);
    const body = {
      operationId: attempt.operationId,
      expectedVersion: version,
      text: value.text,
      task: value.task,
    };
    sending = api
      .saveDraft(id, body)
      .then((answer) => {
        agree(memory, id, answer.version, value);
        attempt = null;
        say('account');
      })
      .catch((error) => {
        if (error?.status === 409 && error.context) {
          const server = {
            version: Number(error.context.serverVersion) || 0,
            ...snapshot(error.context.serverText, error.context.serverTask),
          };
          if (same(server, value)) {
            // This very save landed earlier; its answer never came back.
            agree(memory, id, server.version, value);
            attempt = null;
            say('account');
            return;
          }
          if (ownPredecessor(memory, id, server)) {
            // An earlier save of ours landed and its answer was lost while
            // the learner kept typing: agree on it and send what is newer.
            agree(memory, id, server.version, server);
            attempt = null;
            if (queued === null) queued = value;
            return;
          }
          showElsewhere(server);
          return;
        }
        // Not answered: the words are on this device, and only there.
        say('device');
      })
      .finally(() => {
        sending = null;
        if (queued !== null && !elsewhere) {
          const next = queued;
          queued = null;
          send(next);
        }
      });
    return sending;
  }

  return {
    get active() {
      return active;
    },
    get elsewhere() {
      return elsewhere;
    },
    /* `local` is the device's snapshot. Returns the snapshot the room should
       show when the account's copy is the draft, or null when the room is
       already right. */
    async open(local) {
      local = snapshot(local?.text, local?.task);
      const state = await accountWorkState(api);
      if (state !== 'active') {
        say('device');
        return null;
      }
      let server = null;
      try {
        const answer = (await api.draft(id)).draft;
        server = { version: Number(answer.version) || 0, ...snapshot(answer.text, answer.task) };
      } catch (error) {
        if (error?.status !== 404) {
          say('device');
          return null;
        }
      }
      active = true;
      if (!server) {
        // Nothing kept with the account yet. An empty room has nothing to
        // claim; a draft on the device is sent, and only its answer may say
        // "account".
        say('device');
        if (!isEmpty(local)) await send(local);
        return null;
      }
      if (ownPredecessor(memory, id, server)) agree(memory, id, server.version, server);
      const current = readAgreement(memory, id);
      if (same(server, local)) {
        agree(memory, id, server.version, local);
        say('account');
        return null;
      }
      if (isEmpty(local) || snapshotDigest(local) === current.digest) {
        agree(memory, id, server.version, server);
        say('account');
        return { text: server.text, task: server.task };
      }
      if (current.version === server.version) {
        say('device');
        await send(local);
        return null;
      }
      showElsewhere(server);
      return null;
    },
    edit(value) {
      if (!active || elsewhere) return;
      // Changed and not yet acknowledged: on this device until it is.
      say('device');
      if (timer) cancel(timer);
      const next = snapshot(value?.text, value?.task);
      timer = schedule(() => {
        timer = null;
        send(next);
      }, delay);
    },
    // The learner takes the other device's snapshot - its words and its task.
    useElsewhere() {
      if (!elsewhere) return null;
      const chosen = elsewhere;
      elsewhere = null;
      agree(memory, id, chosen.version, chosen);
      say('account');
      return { text: chosen.text, task: chosen.task };
    },
    // The learner keeps this device's snapshot: it becomes the next version.
    keepHere(value) {
      if (!elsewhere) return Promise.resolve();
      const over = elsewhere;
      elsewhere = null;
      agree(memory, id, over.version, over);
      say('device');
      return send(snapshot(value?.text, value?.task));
    },
    // Settles once nothing is in flight, including a save queued behind one.
    async flush() {
      while (sending) await sending;
    },
  };
}
