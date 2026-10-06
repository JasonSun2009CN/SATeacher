import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type AppSettings, type ProbeResult } from "../api/client";

const DEFAULT_BASE: Record<string, string> = {
  openai: "https://api.openai.com/v1",
  anthropic: "https://api.anthropic.com/v1",
};

const MODEL_SUGGESTIONS: Record<string, string[]> = {
  openai: ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
  anthropic: ["claude-sonnet-4-5", "claude-haiku-4-5"],
};

function errText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

export default function SettingsPage() {
  const [provider, setProvider] = useState("openai");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [stored, setStored] = useState<AppSettings | null>(null);
  const [busy, setBusy] = useState<"save" | "test" | null>(null);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const [probe, setProbe] = useState<ProbeResult | null>(null);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => {
        setStored(s);
        setProvider(s.provider);
        setBaseUrl(s.base_url);
        setModel(s.model);
      })
      .catch((err) => setMessage({ kind: "err", text: errText(err) }));
  }, []);

  function onProviderChange(next: string) {
    const previousDefault = DEFAULT_BASE[provider];
    setProvider(next);
    if (!baseUrl || baseUrl === previousDefault) setBaseUrl(DEFAULT_BASE[next]);
  }

  async function onSave() {
    setBusy("save");
    setMessage(null);
    setProbe(null);
    try {
      const saved = await api.saveSettings({
        provider,
        base_url: baseUrl.trim(),
        model: model.trim(),
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
      });
      setStored(saved);
      setApiKey("");
      setMessage({ kind: "ok", text: "Settings saved." });
    } catch (err) {
      setMessage({ kind: "err", text: errText(err) });
    } finally {
      setBusy(null);
    }
  }

  async function onTest() {
    setBusy("test");
    setMessage(null);
    setProbe(null);
    try {
      setProbe(
        await api.testSettings({
          provider,
          base_url: baseUrl.trim(),
          model: model.trim(),
          ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        }),
      );
    } catch (err) {
      setProbe({ ok: false, detail: errText(err) });
    } finally {
      setBusy(null);
    }
  }

  async function onRemoveKey() {
    setBusy("save");
    setMessage(null);
    try {
      const saved = await api.saveSettings({ clear_key: true });
      setStored(saved);
      setApiKey("");
      setMessage({ kind: "ok", text: "API key removed." });
    } catch (err) {
      setMessage({ kind: "err", text: errText(err) });
    } finally {
      setBusy(null);
    }
  }

  const input =
    "w-full rounded-md border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none";
  const label = "block text-sm font-medium text-slate-700 mb-1";

  return (
    <div className="mx-auto max-w-2xl px-4 py-8">
      <Link to="/" className="text-sm text-blue-700 underline">
        ← Library
      </Link>

      <header className="mb-6 mt-4">
        <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
        <p className="mt-1 text-slate-600">
          Configure the LLM API used for on-demand explanations and import fallback.
          Everything is stored locally; the key never leaves this machine except to call
          the provider you name below.
        </p>
      </header>

      {message && (
        <div
          className={`mb-6 rounded-lg border px-4 py-3 text-sm ${
            message.kind === "ok"
              ? "border-green-300 bg-green-50 text-green-800"
              : "border-red-300 bg-red-50 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="space-y-5 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div>
          <label className={label} htmlFor="provider">
            Provider
          </label>
          <select
            id="provider"
            className={input}
            value={provider}
            onChange={(e) => onProviderChange(e.target.value)}
          >
            <option value="openai">OpenAI</option>
            <option value="anthropic">Anthropic</option>
          </select>
        </div>

        <div>
          <label className={label} htmlFor="base-url">
            Base URL
          </label>
          <input
            id="base-url"
            className={input}
            value={baseUrl}
            placeholder={DEFAULT_BASE[provider]}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
          <p className="mt-1 text-xs text-slate-500">
            OpenAI-compatible proxies work too — point this at any{" "}
            <code className="rounded bg-slate-100 px-1">…/v1</code> endpoint.
          </p>
        </div>

        <div>
          <label className={label} htmlFor="api-key">
            API Key
          </label>
          <div className="flex gap-2">
            <input
              id="api-key"
              type="password"
              autoComplete="off"
              className={input}
              value={apiKey}
              placeholder={
                stored?.api_key_set
                  ? `Stored: ${stored.api_key_masked} — leave blank to keep`
                  : "sk-…"
              }
              onChange={(e) => setApiKey(e.target.value)}
            />
            {stored?.api_key_set && (
              <button
                type="button"
                onClick={() => void onRemoveKey()}
                disabled={busy !== null}
                className="shrink-0 rounded-md border border-red-300 px-3 text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
              >
                Remove
              </button>
            )}
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Saved keys are shown masked and are never sent back to the browser.
          </p>
        </div>

        <div>
          <label className={label} htmlFor="model">
            Model
          </label>
          <input
            id="model"
            className={input}
            value={model}
            list="model-suggestions"
            placeholder={MODEL_SUGGESTIONS[provider][0]}
            onChange={(e) => setModel(e.target.value)}
          />
          <datalist id="model-suggestions">
            {MODEL_SUGGESTIONS[provider].map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>

        <div className="flex gap-3 pt-1">
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={busy !== null}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {busy === "save" ? "Saving…" : "Save settings"}
          </button>
          <button
            type="button"
            onClick={() => void onTest()}
            disabled={busy !== null}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {busy === "test" ? "Testing…" : "Test connection"}
          </button>
        </div>

        {probe && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              probe.ok
                ? "border-green-300 bg-green-50 text-green-800"
                : "border-red-300 bg-red-50 text-red-800"
            }`}
          >
            {probe.ok ? "✓ " : "✗ "}
            {probe.detail}
          </div>
        )}
      </div>
    </div>
  );
}
