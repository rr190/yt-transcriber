interface UrlInputProps {
  url: string;
  setUrl: (url: string) => void;
  language: string;
  setLanguage: (language: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  loading: boolean;
}

export default function UrlInput({
  url,
  setUrl,
  language,
  setLanguage,
  onSubmit,
  onStop,
  loading,
}: UrlInputProps) {
  return (
    <div className="url-input">
      <input
        type="text"
        placeholder="Paste YouTube URL..."
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        disabled={loading}
      />

      <select
        value={language}
        onChange={(e) => setLanguage(e.target.value)}
        disabled={loading}
        aria-label="Video language"
      >
        <option value="zh">中文 (Chinese)</option>
        <option value="auto">Auto-detect</option>
      </select>

      <button
        onClick={loading ? onStop : onSubmit}
        disabled={!url.trim() && !loading}
      >
        {loading ? "Stop Transcribing" : "Transcribe"}
      </button>
    </div>
  );
}
