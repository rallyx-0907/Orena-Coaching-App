/* A learner picture that does not load (a provider URL answering an error, naturalWidth 0) falls back to the initial
   the design draws (kit/avatar.js), wherever the avatar is drawn: the shell, Profile, onboarding. No browser: a
   minimal element stands in for the image and its holder. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const avatar = await import('../static/orena/kit/avatar.js');

const withPicture = String(avatar.avatarMarkup({ picture: 'https://lh3.example/a.png', initial: 'C' }, 'o-avatar'));
assert.match(withPicture, /<img src="https:\/\/lh3\.example\/a\.png" alt="" data-avatar-initial="C">/);
assert.equal(String(avatar.avatarMarkup({ picture: '', initial: 'C' })), '<span class="o-avatar" aria-hidden="true">C</span>');
assert.match(String(avatar.avatarMarkup({ picture: 'https://x/a.png', initial: '"><b>' })), /data-avatar-initial="&quot;&gt;&lt;b&gt;"/, 'the initial is escaped');

function image({ complete = true, naturalWidth = 0, initial = 'C' } = {}) {
  const holder = { attrs: {}, textContent: '<img>', setAttribute(name, value) { this.attrs[name] = value; } };
  return {
    holder, tagName: 'IMG', complete, naturalWidth, parentElement: holder,
    hasAttribute: (name) => name === 'data-avatar-initial' && initial !== null,
    getAttribute: (name) => (name === 'data-avatar-initial' ? initial : null),
  };
}

/* A broken picture becomes the initial; a loaded one is left alone; an image that is not an avatar is not touched. */
assert.equal(avatar.avatarFailed(image()), true, 'loaded with nothing to show');
assert.equal(avatar.avatarFailed(image({ naturalWidth: 96 })), false);
assert.equal(avatar.avatarFailed(image({ complete: false })), false, 'still loading is not failed');
const broken = image();
assert.equal(avatar.fallBackToInitial(broken), true);
assert.equal(broken.holder.textContent, 'C');
assert.equal(broken.holder.attrs['aria-hidden'], 'true');
assert.equal(avatar.fallBackToInitial(image({ initial: null })), false, 'a cover or any other image is not an avatar');

/* One capture-phase listener catches the error (it does not bubble); a picture already broken is swept. */
const listeners = [];
const already = image();
const doc = { addEventListener: (type, fn, capture) => listeners.push({ type, fn, capture }), querySelectorAll: () => [already, image({ naturalWidth: 50 })] };
assert.equal(avatar.installAvatarFallback(doc), true);
assert.equal(avatar.installAvatarFallback(doc), false, 'installed once');
assert.deepEqual(listeners.map((l) => [l.type, l.capture]), [['error', true]]);
assert.equal(already.holder.textContent, 'C', 'a picture that failed before the listener is swept');
const later = image();
listeners[0].fn({ target: later });
assert.equal(later.holder.textContent, 'C');

/* Every avatar the app draws goes through the kit, and the boot installs the fallback. */
const read = (path) => readFileSync(new URL(`../static/orena/${path}`, import.meta.url), 'utf8');
assert.match(read('shell/frame.js'), /return avatarMarkup\(context, className\)/);
assert.match(read('screens/profile/screen.js'), /kitAvatar\(model, 's-profile-avatar o-avatar'\)/);
assert.match(read('screens/onboarding/screen.js'), /avatarMarkup\(id, 's-onboarding__avatar o-avatar'\)/);
assert.match(read('main.js'), /installAvatarFallback\(document\)/);
for (const path of ['shell/frame.js', 'screens/profile/screen.js', 'screens/onboarding/screen.js']) {
  assert.doesNotMatch(read(path), /<img src="\$\{(context|model|id)\.picture\}"/, `${path}: no avatar image outside the kit`);
}

console.log('Avatar fallback: a picture that does not load shows the initial, everywhere the avatar is drawn: PASS');
