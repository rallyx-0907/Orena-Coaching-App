// AudioWorklet: the microphone as 16 kHz, 16-bit little-endian PCM in ~40 ms chunks, with each chunk's level
// (for the page's own speech detection, used only to time things). Nothing is kept.
class Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.pos = 0;
    this.chunk = new Int16Array(640);
    this.filled = 0;
    this.energy = 0;
  }

  process(inputs) {
    const input = inputs[0] && inputs[0][0];
    if (!input) return true;
    // Linear resampling to 16 kHz.
    while (this.pos < input.length) {
      const i = Math.floor(this.pos);
      const frac = this.pos - i;
      const a = input[i];
      const b = i + 1 < input.length ? input[i + 1] : a;
      const s = Math.max(-1, Math.min(1, a + (b - a) * frac));
      this.chunk[this.filled++] = s < 0 ? s * 0x8000 : s * 0x7fff;
      this.energy += s * s;
      if (this.filled === this.chunk.length) {
        const level = Math.sqrt(this.energy / this.chunk.length);
        this.port.postMessage({ pcm: this.chunk.buffer, level }, [this.chunk.buffer]);
        this.chunk = new Int16Array(640);
        this.filled = 0;
        this.energy = 0;
      }
      this.pos += this.ratio;
    }
    this.pos -= input.length;
    return true;
  }
}

registerProcessor("orena-capture", Capture);
