export type TranscriptionEvent =
  | {
      status: "downloaded";
    }
  | {
      status: "duration";
      duration: number;
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