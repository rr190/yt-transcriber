interface UrlInputProps {
  url: string;
  setUrl: (url: string) => void;
  language: string;
  setLanguage: (language: string) => void;
  enableOcr: boolean;
  setEnableOcr: (enableOcr: boolean) => void;
  onSubmit: () => void;
  onStop: () => void;
  loading: boolean;
}

export default function UrlInput({
  url,
  setUrl,
  language,
  setLanguage,
  enableOcr,
  setEnableOcr,
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

      <label className="ocr-toggle">
        <input
          type="checkbox"
          checked={enableOcr}
          onChange={(e) => setEnableOcr(e.target.checked)}
          disabled={loading}
        />
        Scan for burned-in subtitles (Traditional Chinese)
      </label>

      <button
        onClick={loading ? onStop : onSubmit}
        disabled={!url.trim() && !loading}
      >
        {loading ? "Stop Transcribing" : "Transcribe"}
      </button>
    </div>
  );
}
