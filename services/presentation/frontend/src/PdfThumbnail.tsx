import { useEffect, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = workerUrl;

type Props = {
  pdfUrl: string | null;
  alt: string;
  onClick: () => void;
};

export function PdfThumbnail({ pdfUrl, alt, onClick }: Props) {
  const [imageSrc, setImageSrc] = useState<string | null>(null);

  useEffect(() => {
    let revokedUrl: string | null = null;
    let cancelled = false;

    if (!pdfUrl) {
      setImageSrc(null);
      return;
    }

    async function renderThumbnail() {
      try {
        const task = getDocument(pdfUrl);
        const pdf = await task.promise;
        const page = await pdf.getPage(1);
        const viewport = page.getViewport({ scale: 0.3 });
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        if (!context) {
          return;
        }

        canvas.width = Math.round(viewport.width);
        canvas.height = Math.round(viewport.height);
        await page.render({ canvasContext: context, viewport }).promise;
        revokedUrl = canvas.toDataURL("image/jpeg", 0.8);

        if (!cancelled) {
          setImageSrc(revokedUrl);
        }
      } catch {
        if (!cancelled) {
          setImageSrc(null);
        }
      }
    }

    renderThumbnail();
    return () => {
      cancelled = true;
    };
  }, [pdfUrl]);

  return (
    <button type="button" className="pdf-thumb" onClick={onClick} disabled={!pdfUrl}>
      {imageSrc ? <img src={imageSrc} alt={alt} /> : <span>No PDF preview</span>}
    </button>
  );
}
