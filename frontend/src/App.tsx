import { useEffect, useRef, useState } from "react";

import UrlInput from "./components/UrlInput";
import Progress from "./components/Progress";
import Transcript from "./components/Transcript";
import OcrTrace from "./components/OcrTrace";

import { streamTranscription } from "./api/transcription";
import type { TranscriptionEvent } from "./types/transcription";
import type { TranscriptSegment } from "./types/transcript";

import "./App.css";

function App() {
  const abortController = useRef<AbortController | null>(null);

  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("zh");
  const [enableOcr, setEnableOcr] = useState(true);
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [elapsed, setElapsed] = useState(0);

  // Live feed of "checking frame at ..." events, so the user watches the
  // scan happening frame-by-frame — the same verification they'll do
  // manually against the video, done visibly up front to earn trust.
  const [scanEvents, setScanEvents] = useState<
    { timestamp: number; textFound: string | null }[]
  >([]);

  // The single most recent frame image, shown live so the scan visibly
  // looks like it's checking the actual video rather than just logging
  // text. Only the latest thumbnail is kept in state (not the whole
  // history) to avoid piling up base64 images over a long video.
  const [currentFrame, setCurrentFrame] = useState<
    { timestamp: number; thumbnail: string } | null
  >(null);

  // Long silent stretches (yt-dlp downloading/solving JS challenges,
  // a cold-started Render instance waking up) can otherwise look like
  // the app has frozen. An elapsed-time counter makes it visible that
  // work is still happening even before we have real progress data.
  useEffect(() => {
    if (!loading) {
      return;
    }

    const interval = setInterval(() => {
      setElapsed((previous) => previous + 1);
    }, 1000);

    return () => clearInterval(interval);
  }, [loading]);

  const handleEvent = (event: TranscriptionEvent) => {
    switch (event.status) {
      case "downloaded":
        setStatus("Audio downloaded ✓");
        break;

      case "video_downloaded":
        setStatus("Video downloaded ✓");
        break;

      case "duration":
        setTotalDuration(event.duration);
        setStatus("Starting transcription...");
        break;

      case "scanning_frame":
        setScanEvents((previous) => [
          ...previous,
          { timestamp: event.timestamp, textFound: event.text_found },
        ]);
        setCurrentFrame({ timestamp: event.timestamp, thumbnail: event.thumbnail });
        break;

      case "chunk":
        setStatus(`Transcribing ${event.start}s – ${event.end}s`);
        setCurrentTime(event.end);

        // Always show the raw Whisper text immediately as a pending
        // (source: undefined) segment - this is what makes the full
        // transcript appear on the left as soon as it's produced. When OCR
        // is enabled, the matching "merged_chunk" event later updates this
        // same segment in place once it's been checked against subtitles.
        setSegments((previous) => [
          ...previous,
          { start: event.start, end: event.end, text: event.text, source: undefined },
        ]);
        break;

      case "merged_chunk":
        // Update the existing pending segment in place (flips it from
        // grey/pending to green/red) rather than appending a duplicate.
        setSegments((previous) =>
          previous.map((segment) =>
            segment.start === event.start && segment.end === event.end
              ? { ...segment, text: event.text, source: event.source }
              : segment
          )
        );
        break;

      case "complete":
        setStatus("Transcription complete ✓");
        break;

      case "error":
        setStatus(`Error: ${event.message}`);
        break;
    }
  };

  const handleTranscribe = async () => {
    if (!url.trim()) {
      return;
    }

    // Create cancellation controller
    abortController.current = new AbortController();

    setLoading(true);
    setSegments([]);
    setScanEvents([]);
    setCurrentFrame(null);
    setStatus("Starting...");
    setCurrentTime(0);
    setTotalDuration(0);
    setElapsed(0);

    try {
      await streamTranscription(
        url,
        language,
        handleEvent,
        abortController.current.signal,
        enableOcr
      );
    } catch (error: any) {
      // Don't show an error when user intentionally stopped
      if (error.name === "AbortError") {
        setStatus("Transcription stopped.");
      } else {
        console.error(error);
        setStatus("Something went wrong.");
      }
    } finally {
      setLoading(false);
      abortController.current = null;
    }
  };

  const handleStop = () => {
    if (abortController.current) {
      abortController.current.abort();
      abortController.current = null;
    }

    setLoading(false);
    setStatus("Transcription stopped.");
  };

  return (
    <main className="app">
      <div className="container">
        <h1>YouTube Transcriber</h1>

        <p className="subtitle">
          Convert YouTube videos into searchable transcripts.
        </p>

        {/* URL INPUT */}
        <UrlInput
          url={url}
          setUrl={setUrl}
          language={language}
          setLanguage={setLanguage}
          enableOcr={enableOcr}
          setEnableOcr={setEnableOcr}
          onSubmit={handleTranscribe}
          onStop={handleStop}
          loading={loading}
        />

        {/* PROGRESS */}
        {(loading || status) && (
          <Progress
            status={status}
            currentTime={currentTime}
            totalDuration={totalDuration}
            loading={loading}
            elapsed={elapsed}
          />
        )}

        {/* LIVE FRAME-BY-FRAME SUBTITLE SCAN */}
        {enableOcr && loading && (
          <OcrTrace events={scanEvents} currentFrame={currentFrame} />
        )}

        {/* TRANSCRIPT */}
        <Transcript segments={segments} enableOcr={enableOcr} />
      </div>
    </main>
  );
}

export default App;
