/* The microphone as 16 kHz mono PCM16 for Orena's live voice (AGENT_CONTRACT §9, R28): an AudioWorklet that
   averages the context's own rate down to 16 kHz and posts 100 ms frames (1600 samples) as Int16 buffers. It runs
   on the audio thread, so it imports nothing. */
class Pcm16Capture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / 16000;
    this.carry = 0; // input samples not yet folded into an output sample
    this.sum = 0;
    this.frame = new Int16Array(1600);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0]?.[0];
    if (!channel) return true;
    for (let i = 0; i < channel.length; i += 1) {
      this.sum += channel[i];
      this.carry += 1;
      if (this.carry >= this.ratio) {
        const value = Math.max(-1, Math.min(1, this.sum / this.carry));
        this.frame[this.filled] = value < 0 ? value * 0x8000 : value * 0x7fff;
        this.filled += 1;
        this.sum = 0;
        this.carry -= this.ratio;
        if (this.filled === this.frame.length) {
          this.port.postMessage(this.frame.buffer, [this.frame.buffer]);
          this.frame = new Int16Array(1600);
          this.filled = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('orena-pcm16-capture', Pcm16Capture);
