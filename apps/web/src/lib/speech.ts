// Reads replies aloud with the browser's built-in speech synthesis (free, offline
// on most OSes). `onSpeakingChange` lets the avatar lip-sync to real playback.

export function canSpeak(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export function speak(
  text: string,
  onSpeakingChange?: (speaking: boolean) => void,
): void {
  if (!canSpeak()) return;
  window.speechSynthesis.cancel(); // never talk over ourselves
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 0.95;
  utterance.onstart = () => onSpeakingChange?.(true);
  utterance.onend = () => onSpeakingChange?.(false);
  utterance.onerror = () => onSpeakingChange?.(false);
  window.speechSynthesis.speak(utterance);
}

export function stopSpeaking(): void {
  if (canSpeak()) window.speechSynthesis.cancel();
}
