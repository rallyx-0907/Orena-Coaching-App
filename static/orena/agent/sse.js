/* Server-sent events (AGENT_CONTRACT §2): `event: <name>\ndata: <json>\n\n`, read from a fetch body
   or any async iterable of text chunks. A chunk may end mid-line or mid-event; comments (":") and
   unknown fields are skipped; multi-line data joins with "\n". DOM-free. */

export async function* parseEvents(chunks) {
  let buffer = '';
  let name = 'message';
  let data = [];
  const flush = function* () {
    if (data.length) {
      const text = data.join('\n');
      let payload;
      try {
        payload = JSON.parse(text);
      } catch {
        payload = { raw: text };
      }
      yield { event: name, data: payload };
    }
    name = 'message';
    data = [];
  };
  for await (const chunk of chunks) {
    buffer += typeof chunk === 'string' ? chunk : new TextDecoder().decode(chunk, { stream: true });
    let newline;
    while ((newline = buffer.search(/\r\n|\r|\n/)) >= 0) {
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + (buffer[newline] === '\r' && buffer[newline + 1] === '\n' ? 2 : 1));
      if (line === '') {
        yield* flush();
        continue;
      }
      if (line.startsWith(':')) continue;
      const colon = line.indexOf(':');
      const field = colon < 0 ? line : line.slice(0, colon);
      const value = colon < 0 ? '' : line.slice(colon + 1).replace(/^ /, '');
      if (field === 'event') name = value || 'message';
      else if (field === 'data') data.push(value);
    }
  }
  if (buffer) {
    if (buffer.startsWith('data:')) data.push(buffer.slice(5).replace(/^ /, ''));
  }
  yield* flush();
}

/* A fetch Response body as an async iterable of text. */
export async function* bodyChunks(body) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      yield decoder.decode(value, { stream: true });
    }
  } finally {
    reader.releaseLock();
  }
}
