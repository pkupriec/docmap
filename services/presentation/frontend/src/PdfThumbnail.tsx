import { useEffect, useRef, useState } from "react";
import { GlobalWorkerOptions, getDocument } from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = workerUrl;

const THUMBNAIL_SCALE = 0.3;
const THUMBNAIL_QUALITY = 0.8;
const THUMBNAIL_ROOT_MARGIN = "640px 0px";
const MAX_CONCURRENT_RENDERS = 2;
const MAX_THUMBNAIL_CACHE_SIZE = 256;

type ThumbnailCacheEntry =
  | { status: "ready"; src: string }
  | { status: "pending"; promise: Promise<string | null> }
  | { status: "error" };

const thumbnailCache = new Map<string, ThumbnailCacheEntry>();
const thumbnailUsageOrder: string[] = [];
const renderQueue: Array<() => void> = [];
let inFlightRenderCount = 0;

function touchThumbnail(url: string): void {
  const index = thumbnailUsageOrder.indexOf(url);
  if (index >= 0) {
    thumbnailUsageOrder.splice(index, 1);
  }
  thumbnailUsageOrder.push(url);
}

function evictThumbnailCacheIfNeeded(): void {
  while (thumbnailUsageOrder.length > MAX_THUMBNAIL_CACHE_SIZE) {
    const oldest = thumbnailUsageOrder.shift();
    if (!oldest) {
      return;
    }
    const cached = thumbnailCache.get(oldest);
    thumbnailCache.delete(oldest);
    if (cached?.status === "ready") {
      URL.revokeObjectURL(cached.src);
    }
  }
}

function enqueueThumbnailRender(task: () => Promise<string | null>): Promise<string | null> {
  return new Promise((resolve) => {
    const run = () => {
      inFlightRenderCount += 1;
      task()
        .then((result) => {
          resolve(result);
        })
        .catch(() => {
          resolve(null);
        })
        .finally(() => {
          inFlightRenderCount -= 1;
          const next = renderQueue.shift();
          if (next) {
            next();
          }
        });
    };

    if (inFlightRenderCount < MAX_CONCURRENT_RENDERS) {
      run();
      return;
    }
    renderQueue.push(run);
  });
}

async function renderThumbnailImage(pdfUrl: string): Promise<string | null> {
  const task = getDocument({
    url: pdfUrl,
    stopAtErrors: true,
  });
  try {
    const pdf = await task.promise;
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: THUMBNAIL_SCALE });
    const canvas = document.createElement("canvas");
    const context = canvas.getContext("2d");
    if (!context) {
      await pdf.destroy();
      return null;
    }

    canvas.width = Math.max(1, Math.round(viewport.width));
    canvas.height = Math.max(1, Math.round(viewport.height));
    await page.render({ canvasContext: context, viewport }).promise;

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", THUMBNAIL_QUALITY);
    });
    page.cleanup();
    await pdf.cleanup();
    await pdf.destroy();

    if (!blob) {
      return null;
    }
    return URL.createObjectURL(blob);
  } catch {
    try {
      task.destroy();
    } catch {
      // no-op
    }
    return null;
  }
}

function loadThumbnail(pdfUrl: string): Promise<string | null> {
  const cached = thumbnailCache.get(pdfUrl);
  if (cached) {
    if (cached.status === "ready") {
      touchThumbnail(pdfUrl);
      return Promise.resolve(cached.src);
    }
    if (cached.status === "error") {
      return Promise.resolve(null);
    }
    return cached.promise;
  }

  const promise = enqueueThumbnailRender(() => renderThumbnailImage(pdfUrl)).then((src) => {
    if (src) {
      thumbnailCache.set(pdfUrl, { status: "ready", src });
      touchThumbnail(pdfUrl);
      evictThumbnailCacheIfNeeded();
      return src;
    }
    thumbnailCache.set(pdfUrl, { status: "error" });
    return null;
  });
  thumbnailCache.set(pdfUrl, { status: "pending", promise });
  return promise;
}

type Props = {
  pdfUrl: string | null;
  alt: string;
  onClick: () => void;
};

export function PdfThumbnail({ pdfUrl, alt, onClick }: Props) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [isNearViewport, setIsNearViewport] = useState(false);

  useEffect(() => {
    if (!pdfUrl) {
      setIsNearViewport(false);
      setImageSrc(null);
      return;
    }

    const element = buttonRef.current;
    if (!element) {
      return;
    }

    if (!("IntersectionObserver" in window)) {
      setIsNearViewport(true);
      return;
    }

    setIsNearViewport(false);
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setIsNearViewport(true);
          observer.disconnect();
        }
      },
      { root: null, rootMargin: THUMBNAIL_ROOT_MARGIN },
    );
    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [pdfUrl]);

  useEffect(() => {
    let cancelled = false;
    if (!pdfUrl || !isNearViewport) {
      setImageSrc(null);
      return;
    }

    loadThumbnail(pdfUrl).then((src) => {
      if (!cancelled) {
        setImageSrc(src);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isNearViewport, pdfUrl]);

  return (
    <button
      ref={buttonRef}
      type="button"
      className="pdf-thumb"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      disabled={!pdfUrl}
    >
      {imageSrc ? <img src={imageSrc} alt={alt} loading="lazy" /> : <span>No PDF preview</span>}
    </button>
  );
}
