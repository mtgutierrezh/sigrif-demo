let context: AudioContext | null = null;

export function playHighRiskAlert() {
  if (typeof window === "undefined") {
    return;
  }
  const AudioCtor =
    window.AudioContext ??
    (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AudioCtor) {
    return;
  }
  const audio = context ?? new AudioCtor();
  context = audio;
  const now = audio.currentTime;
  const gain = audio.createGain();
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(0.035, now + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.5);
  gain.connect(audio.destination);
  [660, 880].forEach((frequency, index) => {
    const oscillator = audio.createOscillator();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    oscillator.connect(gain);
    const start = now + index * 0.18;
    oscillator.start(start);
    oscillator.stop(start + 0.22);
  });
}
