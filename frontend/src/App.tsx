import { useEffect, useRef, useState } from "react";

import UrlInput from "./components/UrlInput";
import Progress from "./components/Progress";
import Transcript from "./components/Transcript";

import { streamTranscription } from "./api/transcription";
import type { TranscriptionEvent } from "./types/transcription";
import { formatTime } from "./utils/format";

import "./App.css";

function App() {
  const abortController = useRef<AbortController | null>(null);

  const [url, setUrl] = useState("");
  const [language, setLanguage] = useState("zh");
  const [transcript, setTranscript] = useState("");

  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("");

  const [currentTime, setCurrentTime] = useState(0);
  const [totalDuration, setTotalDuration] = useState(0);
  const [elapsed, setElapsed] = useState(0);

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

  const appendChunk = (text: string) => {
    if (!text) {
      return;
    }

    setTranscript((previous) => (previous ? `${previous}\n\n${text}` : text));
  };

  const handleEvent = (event: TranscriptionEvent) => {
    switch (event.status) {
      case "downloaded":
        setStatus("Audio downloaded ✓");
        break;

      case "duration":
        setTotalDuration(event.duration);
        setStatus("Starting transcription...");
        break;

      case "chunk_started":
        setStatus(
          `Transcribing ${formatTime(event.start)}–${formatTime(event.end)}...`
        );
        break;

      case "chunk":
        setStatus(`Transcribed ${formatTime(event.start)}–${formatTime(event.end)}`);
        setCurrentTime(event.end);
        appendChunk(event.text);
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
    setTranscript("");
    setStatus("Starting...");
    setCurrentTime(0);
    setTotalDuration(0);
    setElapsed(0);

    try {
      await streamTranscription(
        url,
        language,
        handleEvent,
        abortController.current.signal
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

        {/* TRANSCRIPT */}
        <Transcript transcript={transcript} />
      </div>
    </main>
  );
}

export default App;
