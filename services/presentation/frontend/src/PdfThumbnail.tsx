type Props = {
  thumbnailUrl: string | null;
  hasPdf: boolean;
  alt: string;
  onClick: () => void;
};

export function PdfThumbnail({ thumbnailUrl, hasPdf, alt, onClick }: Props) {
  return (
    <button
      type="button"
      className="pdf-thumb"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      disabled={!hasPdf}
    >
      {thumbnailUrl ? <img src={thumbnailUrl} alt={alt} loading="lazy" decoding="async" /> : <span>No PDF preview</span>}
    </button>
  );
}
