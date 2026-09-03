export type TranscriptionEvent =
  | {
      status: "downloaded";
    }
  | {
      status: "video_downloaded";
    }
  | {
      status: "duration";
      duration: number;
    }
  | {
      status: "scanning_frame";
      timestamp: number;
      text_found: string | null;
      thumbnail: string;
    }
  | {
      status: "ocr_window";
      start: number;
      end: number;
      text: string;
    }
  | {
      status: "chunk";
      start: number;
      end: number;
      text: string;
    }
  | {
      status: "merged_chunk";
      start: number;
      end: number;
      text: string;
      source: "ocr" | "whisper";
    }
  | {
      status: "complete";
    }
  | {
      status: "error";
      message: string;
    };
