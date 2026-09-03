export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  source?: "ocr" | "whisper";
}
