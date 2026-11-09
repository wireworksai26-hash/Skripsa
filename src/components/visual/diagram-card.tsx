"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Label, Select, Textarea } from "@/components/ui/field";
import { Pill } from "@/components/ui/pill";
import { useProject } from "@/lib/store";
import type { DiagramEngine } from "@/lib/types";
import { diagramPresets } from "@/lib/diagram-presets";
import { renderDiagramPng, type RasterImage } from "@/lib/visuals";
import { cn } from "@/lib/utils";
import { Workflow } from "lucide-react";
import { useEffect, useState } from "react";

const ENGINE_LABEL: Record<DiagramEngine, string> = { mermaid: "Mermaid", plantuml: "PlantUML" };

export function DiagramCard() {
  const project = useProject((s) => s.project);
  const addDiagram = useProject((s) => s.addDiagram);

  const [engine, setEngine] = useState<DiagramEngine>("mermaid");
  const [title, setTitle] = useState("");
  const [code, setCode] = useState("");
  const [chapter, setChapter] = useState("2");
  const [preview, setPreview] = useState<RasterImage | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Pratinjau milik kode atau mesin lama tidak boleh disimpan sebagai diagram yang baru.
    setPreview(null);
  }, [code, engine]);

  if (!project) return null;
  const isTeknik = project.form.domain === "INFORMATIKA";
  const presets = diagramPresets(project.form).filter((p) => p.engine === engine && (isTeknik || !p.uml));
  const chapters = project.template.chapters;

  const renderPreview = async () => {
    setBusy(true);
    setError(null);
    try {
      setPreview(await renderDiagramPng(engine, code));
    } catch (e) {
      setPreview(null);
      setError(`Gagal merender: ${e instanceof Error ? e.message : "kroki.io tidak terjangkau"}`);
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const img = preview ?? (await renderDiagramPng(engine, code));
      const name = title.trim() || "Diagram";
      await addDiagram({ engine, title: name, code, caption: name, image: img.dataUrl, width: img.width, height: img.height, chapter });
      setCode("");
      setTitle("");
    } catch (e) {
      setError(`Diagram tidak disimpan: ${e instanceof Error ? e.message : "kroki.io tidak terjangkau"}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <Pill tone="midnight">
          <Workflow size={12} /> {ENGINE_LABEL[engine]} via kroki.io
        </Pill>
        <Pill>Kerangka berpikir &amp; alur metodologi{isTeknik ? " · UML" : ""}</Pill>
      </div>
      <h2 className="t-heading-sm mt-3">Diagram konseptual</h2>

      <div className="mt-4 inline-flex rounded-btn bg-black/5 p-0.5 text-[12px] font-medium" role="group" aria-label="Mesin diagram">
        {(Object.keys(ENGINE_LABEL) as DiagramEngine[]).map((e) => (
          <button
            key={e}
            type="button"
            onClick={() => {
              setEngine(e);
              setError(null);
            }}
            className={cn("rounded-btn px-3 py-2.5 transition-colors sm:py-1.5", engine === e ? "bg-white shadow-sm" : "text-black/55")}
          >
            {ENGINE_LABEL[e]}
          </button>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {presets.map((p) => (
          <Button
            key={`${p.engine}-${p.title}`}
            variant="outline"
            size="sm"
            onClick={() => {
              setCode(p.code);
              setTitle(p.title);
              setChapter(p.chapter);
              setError(null);
            }}
          >
            {p.title}
          </Button>
        ))}
      </div>

      <div className="mt-4 space-y-3">
        <div>
          <Label htmlFor="dtitle">Judul diagram</Label>
          <Input id="dtitle" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Kerangka berpikir penelitian" />
        </div>
        <div>
          <Label htmlFor="dchapter">Disisipkan di</Label>
          <Select id="dchapter" value={chapter} onChange={(e) => setChapter(e.target.value)}>
            {chapters.map((c) => (
              <option key={c.chapter_number} value={c.chapter_number}>
                BAB {c.chapter_number} · {c.chapter_title}
              </option>
            ))}
          </Select>
        </div>
        <Textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={9}
          className="font-mono text-[13px]"
          aria-label={`Kode ${ENGINE_LABEL[engine]}`}
          placeholder={`Tempel kode ${ENGINE_LABEL[engine]} di sini, atau pilih salah satu kerangka di atas.`}
        />
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={renderPreview} disabled={busy || !code.trim()}>
            {busy ? "Memproses…" : "Render pratinjau"}
          </Button>
          <Button variant="primary" onClick={save} disabled={busy || !code.trim() || !title.trim()}>
            Simpan ke Bab IV
          </Button>
        </div>
        {error && <p className="text-[13px] text-vermillion">{error}</p>}
        {preview && (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img src={preview.dataUrl} alt="Pratinjau diagram" className="max-h-96 rounded-btn border border-hairline bg-white p-3" />
        )}
      </div>
    </Card>
  );
}
