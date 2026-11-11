// VELA Creator: composite the existing 3D avatar canvas and TalkingHead audio
// into a portrait WebM file. Browser-side rendering, no server-side GPU needed.
const MIME_TYPES = [
  'video/webm;codecs=vp9,opus',
  'video/webm;codecs=vp8,opus',
  'video/webm'
];

export class VelaCreatorRecorder {
  constructor({ renderCanvas, audioContext, audioOutputNode, onStatus = () => {} }) {
    this.renderCanvas = renderCanvas;
    this.audioContext = audioContext;
    this.audioOutputNode = audioOutputNode;
    this.onStatus = onStatus;
    this.recorder = null;
    this.active = false;
    this._saving = false;
  }

  static isSupported() {
    return typeof MediaRecorder !== 'undefined'
      && typeof HTMLCanvasElement !== 'undefined'
      && typeof HTMLCanvasElement.prototype.captureStream === 'function';
  }

  start() {
    if (!VelaCreatorRecorder.isSupported()) {
      throw new Error('Video recording requires a desktop Chromium-compatible browser with MediaRecorder and canvas.captureStream.');
    }
    if (this.active) throw new Error('Recording is already running.');
    if (!this.renderCanvas || !this.audioContext || !this.audioOutputNode) {
      throw new Error('VELA renderer and TalkingHead audio output must be initialized before recording.');
    }
    const mimeType = MIME_TYPES.find(type => MediaRecorder.isTypeSupported(type));
    if (!mimeType) throw new Error('This browser does not support WebM video recording.');

    const portrait = document.createElement('canvas');
    portrait.width = 720;
    portrait.height = 1280;
    const ctx = portrait.getContext('2d', { alpha: false });
    if (!ctx) throw new Error('Could not initialize the portrait video canvas.');

    const videoCapture = portrait.captureStream(30);
    const audioCapture = this.audioContext.createMediaStreamDestination();
    this.audioOutputNode.connect(audioCapture);
    const stream = new MediaStream([
      ...videoCapture.getVideoTracks(),
      ...audioCapture.stream.getAudioTracks()
    ]);

    let recorder;
    try {
      recorder = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 3_000_000 });
    } catch (error) {
      this.audioOutputNode.disconnect(audioCapture);
      stream.getTracks().forEach(track => track.stop());
      throw error;
    }

    this.recorder = recorder;
    this.active = true;
    this._saving = true;
    this._frameCount = 0;
    this._audioCapture = audioCapture;
    this._stream = stream;
    this._failure = null;
    const chunks = [];
    const promise = new Promise((resolve, reject) => {
      recorder.ondataavailable = event => {
        if (event.data && event.data.size > 0) chunks.push(event.data);
      };
      recorder.onerror = event => {
        this._failure = event.error || new Error('MediaRecorder failed.');
        this.stop(false);
      };
      recorder.onstop = () => {
        const shouldSave = this._saving;
        const failure = this._failure;
        this._cleanup();
        if (failure) return reject(failure);
        if (!shouldSave) return resolve(null);
        const blob = new Blob(chunks, { type: mimeType });
        if (!blob.size || this._frameCount < 2) {
          return reject(new Error('Recording produced no usable video frames.'));
        }
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'vela-creator-' + new Date().toISOString().replace(/[:.]/g, '-') + '.webm';
        link.style.display = 'none';
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
        this.onStatus('Video exported · portrait WebM with voice audio');
        resolve(blob);
      };
    });
    this._drawActive = true;
    this.copyFrame = () => {
      if (!this._drawActive) return;
      ctx.fillStyle = '#070d18';
      ctx.fillRect(0, 0, portrait.width, portrait.height);
      const source = this.renderCanvas;
      const width = source.width;
      const height = source.height;
      if (width > 0 && height > 0) {
        // Center-crop, rather than stretching faces into portrait proportions.
        const srcRatio = width / height;
        const dstRatio = portrait.width / portrait.height;
        let x = 0, y = 0, w = width, h = height;
        if (srcRatio > dstRatio) {
          w = height * dstRatio;
          x = (width - w) / 2;
        } else {
          h = width / dstRatio;
          y = (height - h) / 2;
        }
        try {
          ctx.drawImage(source, x, y, w, h, 0, 0, portrait.width, portrait.height);
          this._frameCount++;
        } catch (_) {
          // Keep the recording alive; the onstop frame check rejects empty exports.
        }
      }
    };
    const draw = () => {
      if (!this._drawActive) return;
      this.copyFrame(); // Synthetic canvases / browsers without a renderer hook.
      requestAnimationFrame(draw);
    };
    requestAnimationFrame(draw);
    try {
      recorder.start(250);
      this.onStatus('Recording 720×1280 portrait video with speech…');
    } catch (error) {
      this._failure = error;
      this._cleanup();
      throw error;
    }
    return promise;
  }

  watchSpeech(isSpeaking) {
    const started = performance.now();
    let seenSpeech = false;
    let quietSince = 0;
    const poll = () => {
      if (!this.active) return;
      const now = performance.now();
      const speaking = Boolean(isSpeaking());
      if (speaking) {
        seenSpeech = true;
        quietSince = 0;
      } else if (seenSpeech) {
        if (!quietSince) quietSince = now;
        if (now - quietSince >= 1000) {
          this.stop(true);
          return;
        }
      }
      if (now - started > (seenSpeech ? 90_000 : 20_000)) {
        this._failure = new Error(seenSpeech
          ? 'Speech recording exceeded the 90-second limit.'
          : 'No speech playback was detected after synthesis.');
        this.stop(false);
        return;
      }
      setTimeout(poll, 100);
    };
    setTimeout(poll, 100);
  }

  stop(save = true) {
    if (!this.active) return;
    this._saving = save;
    this.active = false;
    if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
  }

  _cleanup() {
    this.active = false;
    this._drawActive = false;
    this.copyFrame = null;
    try { this.audioOutputNode.disconnect(this._audioCapture); } catch (_) {}
    if (this._stream) this._stream.getTracks().forEach(track => track.stop());
    this._stream = null;
    this._audioCapture = null;
    this.recorder = null;
  }
}
