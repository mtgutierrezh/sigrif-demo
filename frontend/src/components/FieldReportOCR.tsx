import { useState } from "react";

import type { FieldReport, OcrResult, Zone } from "../features/zones/types";
import { postForm, postJson } from "../lib/api";
import { useSession } from "./session";

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : "No pudimos completar la operación.";
}

export function FieldReportOCR({ zone }: { zone: Zone }) {
  const { token } = useSession();
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<OcrResult | null>(null);
  const [text, setText] = useState("");
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const extract = async () => {
    if (!file) {
      return;
    }
    setExtracting(true);
    setError(null);
    setNotice(null);
    setResult(null);
    try {
      const form = new FormData();
      form.append("file", file, file.name);
      const ocr = await postForm<OcrResult>("/api/v1/field-reports/ocr", token, form);
      setResult(ocr);
      setText(ocr.text);
      if (!ocr.text) {
        setNotice("La imagen no contenía texto legible. Puedes escribirlo manualmente.");
      }
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setExtracting(false);
    }
  };

  const save = async () => {
    if (!result || !text.trim()) {
      return;
    }
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await postJson<FieldReport>(`/api/v1/zones/${zone.id}/field-reports`, token, {
        extracted_text: result.text || text.trim(),
        confirmed_text: text.trim(),
        model_id: result.model_id,
        source_filename: result.filename,
        content_type: result.content_type,
        size_bytes: result.size_bytes,
      });
      setNotice("Reporte guardado y asociado a la zona.");
    } catch (caught) {
      setError(messageOf(caught));
    } finally {
      setSaving(false);
    }
  };

  return (
    <details className="mt-5 border border-iron">
      <summary className="cursor-pointer select-none px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.08em] text-bone">
        Digitalizar ficha de terreno
      </summary>
      <div className="border-t border-iron p-3">
        <p className="text-[11px] leading-snug text-bone-muted">
          Sube una foto de una ficha o reporte. El OCR transcribe el texto y tú lo revisas antes de
          guardarlo. La imagen no se almacena.
        </p>
        <input
          className="mt-3 block w-full font-mono text-[11px] text-ash file:mr-3 file:border-0 file:bg-iron file:px-3 file:py-2 file:text-bone"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            setResult(null);
            setText("");
            setError(null);
            setNotice(null);
          }}
        />
        <button
          type="button"
          className="btn btn-primary mt-3 w-full"
          onClick={extract}
          disabled={!file || extracting}
        >
          {extracting ? "Extrayendo texto…" : "Extraer texto con OCR"}
        </button>

        {error ? (
          <p className="mt-3 border border-ember/40 p-2 font-mono text-[10px] text-ember" role="alert">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p className="mt-3 font-mono text-[10px] text-surveyor" aria-live="polite">
            {notice}
          </p>
        ) : null}

        {result ? (
          <div className="mt-3">
            <p className="font-mono text-[9px] uppercase tracking-[0.06em] text-ash">
              {result.model_id} · {result.latency_ms.toFixed(0)} ms ·{" "}
              {result.usage.input_tokens + result.usage.output_tokens} tokens
              {result.cached ? " · caché" : ""}
            </p>
            {result.truncated ? (
              <p className="mt-1 font-mono text-[10px] text-ember">
                La transcripción alcanzó el límite de tokens; revisa el texto completo.
              </p>
            ) : null}
            <label className="mt-2 block">
              <span className="font-mono text-[9px] uppercase tracking-[0.06em] text-ash">
                Texto revisado
              </span>
              <textarea
                className="input mt-1 min-h-32 w-full p-2 font-mono text-[12px]"
                value={text}
                onChange={(event) => setText(event.target.value)}
              />
            </label>
            <button
              type="button"
              className="btn btn-primary mt-2 w-full"
              onClick={save}
              disabled={saving || !text.trim()}
            >
              {saving ? "Guardando…" : "Guardar reporte confirmado"}
            </button>
          </div>
        ) : null}
      </div>
    </details>
  );
}
