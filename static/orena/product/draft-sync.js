/* A Writing draft kept with the account, when the deployment keeps work there.

   The device always keeps the draft too (learner memory), so nothing here can
   lose words: the account copy is added when `/api/account-backbone` says
   `active`, and the room says which of the two is true. Anything else -
   `disabled`, `unavailable`, a network failure - leaves the draft on this
   device and the room says exactly that, never "saved to your account".

   Versions decide, not clocks. The device remembers the version it last
   agreed with the server and a digest of the text it agreed on:

   - the server has nothing yet: a draft already in the box is sent;
   - the device has not changed the text since it last agreed: the server's
     text is simply the draft (another device may have moved it on);
   - the device changed it and the server did not move: the device's text is
     sent;
   - both moved: the learner is shown the other device's version and chooses.
     Nothing is merged, and the text in the box is never replaced silently. */

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
   same text I last agreed on" from "something else". Not a security digest. */
export function textDigest(text) {
  let hash = 0x811c9dc5;
  const value = String(text || '');
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash.toString(16).padStart(8, '0');
}

const syncKey = (id) => `${id}::sync`;

export function readAgreement(memory, id) {
  const raw = memory.value.expressions[syncKey(id)] || '';
  const match = /^(\d+):([0-9a-f]{8})$/.exec(raw);
  return match
    ? { version: Number(match[1]), digest: match[2] }
    : { version: 0, digest: '' };
}

function agree(memory, id, version, text) {
  try {
    memory.write(syncKey(id), `${version}:${textDigest(text)}`);
  } catch {
    // Device memory refused; the account copy still stands.
  }
}

export function draftSync({
  api,
  memory,
  id,
  task = () => '',
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

  async function send(text) {
    if (sending) {
      queued = text;
      return sending;
    }
    const { version } = readAgreement(memory, id);
    // The same words from the same version are the same operation: a retry
    // after a lost answer replays instead of conflicting with itself.
    if (!attempt || attempt.version !== version || attempt.text !== text)
      attempt = { version, text, operationId: `op-${crypto.randomUUID()}` };
    const body = {
      operationId: attempt.operationId,
      expectedVersion: version,
      text,
      task: String(task() || '').slice(0, 240),
    };
    sending = api
      .saveDraft(id, body)
      .then((answer) => {
        agree(memory, id, answer.version, text);
        attempt = null;
        say('account');
      })
      .catch((error) => {
        if (error?.status === 409 && error.context) {
          const server = {
            version: Number(error.context.serverVersion) || 0,
            text: String(error.context.serverText || ''),
          };
          // Our own earlier write, whose answer never arrived.
          if (server.text === text) {
            agree(memory, id, server.version, text);
            say('account');
            return;
          }
          elsewhere = server;
          onElsewhere(server);
          return;
        }
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
    /* Returns the text the box should show when the account's copy is the
       draft, or null when the box is already right. */
    async open(localText) {
      const state = await accountWorkState(api);
      if (state !== 'active') {
        say('device');
        return null;
      }
      let server = null;
      try {
        server = (await api.draft(id)).draft;
      } catch (error) {
        if (error?.status !== 404) {
          say('device');
          return null;
        }
      }
      active = true;
      const local = String(localText || '');
      const agreed = readAgreement(memory, id);
      if (!server) {
        say('account');
        if (local.trim()) await send(local);
        return null;
      }
      const untouched = !local.trim() || textDigest(local) === agreed.digest;
      if (untouched) {
        agree(memory, id, server.version, server.text);
        say('account');
        return server.text === local ? null : server.text;
      }
      if (agreed.version === server.version) {
        say('account');
        await send(local);
        return null;
      }
      if (server.text === local) {
        agree(memory, id, server.version, local);
        say('account');
        return null;
      }
      elsewhere = { version: server.version, text: server.text };
      onElsewhere(elsewhere);
      return null;
    },
    edit(text) {
      if (!active || elsewhere) return;
      if (timer) cancel(timer);
      timer = schedule(() => {
        timer = null;
        send(String(text));
      }, delay);
    },
    // The learner takes the other device's version: it is now the draft.
    useElsewhere() {
      if (!elsewhere) return null;
      const chosen = elsewhere;
      elsewhere = null;
      agree(memory, id, chosen.version, chosen.text);
      say('account');
      return chosen.text;
    },
    // The learner keeps this device's words: they become the next version.
    keepHere(text) {
      if (!elsewhere) return;
      const over = elsewhere;
      elsewhere = null;
      agree(memory, id, over.version, over.text);
      return send(String(text));
    },
    flush() {
      return sending || Promise.resolve();
    },
  };
}
