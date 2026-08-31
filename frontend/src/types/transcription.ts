export type TranscriptionEvent =
  | {
      status: "downloaded";
    }
  | {
      status: "duration";
      duration: number;
    }
  | {
      status: "chunk_started";
      start: number;
      end: number;
    }
  | {
      status: "chunk";
      start: number;
      end: number;
      text: string;
    }
  | {
      status: "complete";
    }
  | {
      status: "error";
      message: string;
    };