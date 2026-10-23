// Reads replies aloud with the browser's built-in speech synthesis (free, offline
// on most OSes). `onSpeakingChange` lets the avatar lip-sync to real playback.

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

// Higher-quality voices first: Edge "Natural"/"Online" (neural) voices, then
// Chrome's "Google" voices, then whatever English voice the OS has.
const VOICE_HINTS = ["natural", "online", "neural", "google"];

export function pickVoice(
  voices: SpeechSynthesisVoice[],
  lang = "en",
): SpeechSynthesisVoice | undefined {
  const english = voices.filter((v) => v.lang?.toLowerCase().startsWith(lang));
  for (const hint of VOICE_HINTS) {
    const match = english.find((v) => v.name.toLowerCase().includes(hint));
    if (match) return match;
  }
  return english.find((v) => v.default) ?? english[0];
}

export function speak(
  text: string,
  onSpeakingChange?: (speaking: boolean) => void,
): void {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel(); // never talk over ourselves
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  // getVoices() can be empty until the browser fires "voiceschanged"; then the
  // default voice is used, which is fine.
  const voice = pickVoice(window.speechSynthesis.getVoices?.() ?? []);
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  }
  utterance.onstart = () => onSpeakingChange?.(true);
  utterance.onend = () => onSpeakingChange?.(false);
  utterance.onerror = () => onSpeakingChange?.(false);
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}
