import type { MutableRefObject, RefObject } from "react";

import { PdfThumbnail } from "./PdfThumbnail";
import type { DocumentCard, Location, LocationDocumentsResponse, SearchResponse } from "./types";

type UiStatus = "loading" | "ready" | "error";
type ErrorContext = "startup" | "location_documents" | "search" | "unknown";
type BoundariesStatus = "loading" | "ready" | "error";

type Props = {
  searchInputRef: RefObject<HTMLInputElement>;
  searchQuery: string;
  onSearchQueryChange: (query: string) => void;
  activeMode: string;
  selectedLocation: Location | null;
  searchActive: boolean;
  searchResults: SearchResponse;
  panelTitle: string;
  locationDocumentsMeta: LocationDocumentsResponse | null;
  status: UiStatus;
  errorContext: ErrorContext;
  boundariesStatus: BoundariesStatus;
  documents: DocumentCard[];
  activeVisualizationDocumentId: string | null;
  pinnedDocumentId: string | null;
  offscreenLinkCount: number;
  declutterLinks: boolean;
  hiddenVisibleLinkCount: number;
  cardRefs: MutableRefObject<Record<string, HTMLElement | null>>;
  canLoadMore: boolean;
  isLoadingMore: boolean;
  onClickLocation: (locationId: string) => void;
  onDeclutterChange: (enabled: boolean) => void;
  onHoverDocument: (documentId: string | null) => void;
  onToggleDocument: (documentId: string) => void;
  onOpenPdf: (documentId: string) => void;
  onLoadMore: () => void;
};

function formatRank(rank: string | null | undefined): string {
  const normalized = String(rank ?? "unknown").toLowerCase();
  if (normalized === "admin_region" || normalized === "region" || /^admin_level_\d+$/.test(normalized)) return "Admin";
  if (normalized === "national_park") return "National Park";
  if (normalized === "country") return "Country";
  if (normalized === "continent") return "Continent";
  if (normalized === "ocean") return "Ocean";
  if (normalized === "desert") return "Desert";
  if (normalized === "city") return "City";
  return "Unknown";
}

function errorMessageFor(context: ErrorContext): string {
  if (context === "startup") return "Unable to load locations.";
  if (context === "location_documents") return "Unable to load linked documents for this location.";
  if (context === "search") return "Unable to load search results.";
  return "Unable to load data.";
}

export function DocumentPanel(props: Props) {
  return (
    <aside className="right-panel">
      <div className="search-row">
        <input
          ref={props.searchInputRef}
          type="search"
          value={props.searchQuery}
          placeholder="Search SCP or location"
          onChange={(event) => props.onSearchQueryChange(event.target.value)}
        />
      </div>

      <div className="mode-summary-row">
        <span className="mode-pill">Mode: {props.activeMode}</span>
        {props.selectedLocation ? (
          <span className="selection-pill" title={props.selectedLocation.name}>
            {props.selectedLocation.name} · {props.selectedLocation.document_count} docs
          </span>
        ) : null}
      </div>

      {props.searchActive && props.status === "ready" ? (
        <p className="search-summary">
          Results: {props.searchResults.locations.length} locations, {props.searchResults.documents.length} documents
        </p>
      ) : null}

      <h2>{props.panelTitle}</h2>
      {props.locationDocumentsMeta && !props.searchActive ? (
        <p className="fallback-note">
          Scope: {formatRank(props.locationDocumentsMeta.scope_rank)} · {props.locationDocumentsMeta.total_items} docs from{" "}
          {props.locationDocumentsMeta.scope_location_count} locations
          {props.locationDocumentsMeta.fallback_depth && props.locationDocumentsMeta.fallback_depth > 0
            ? ` · alias depth ${props.locationDocumentsMeta.fallback_depth}`
            : ""}
        </p>
      ) : null}
      {props.status === "loading" && <p>Loading locations...</p>}
      {props.status === "error" && <p>{errorMessageFor(props.errorContext)}</p>}
      {props.status === "ready" && props.boundariesStatus === "loading" ? (
        <p className="fallback-note">Loading baked geometry...</p>
      ) : null}
      {props.status === "ready" && props.boundariesStatus === "error" ? (
        <p className="fallback-note">Boundaries unavailable. Showing location points only.</p>
      ) : null}

      {props.status === "ready" && props.searchActive ? (
        <div className="search-result-locations">
          {props.searchResults.locations.map((location) => (
            <button
              key={location.location_id}
              type="button"
              className="search-location-chip"
              onClick={() => props.onClickLocation(location.location_id)}
            >
              <span className="chip-rank">{formatRank(location.location_rank)}</span>
              <span>{location.name}</span>
            </button>
          ))}
        </div>
      ) : null}

      {props.status === "ready" && !props.searchActive && !props.selectedLocation ? (
        <p>Explore the map to discover SCP documents.</p>
      ) : null}
      {props.status === "ready" && props.documents.length === 0 && (props.searchActive || props.selectedLocation) ? (
        <p>No linked documents.</p>
      ) : null}

      {props.activeVisualizationDocumentId ? (
        <div className="link-controls">
          <label>
            <input
              type="checkbox"
              checked={props.declutterLinks}
              onChange={(event) => props.onDeclutterChange(event.target.checked)}
            />
            Declutter links (top 12)
          </label>
          {props.hiddenVisibleLinkCount > 0 ? <span>Hidden visible links: {props.hiddenVisibleLinkCount}</span> : null}
        </div>
      ) : null}

      <div className="cards">
        {props.documents.map((doc) => (
          <article
            key={doc.document_id}
            className={`doc-card ${props.pinnedDocumentId === doc.document_id ? "doc-card-pinned" : ""}`}
            ref={(element) => { props.cardRefs.current[doc.document_id] = element; }}
            onMouseEnter={() => props.onHoverDocument(doc.document_id)}
            onMouseLeave={() => props.onHoverDocument(null)}
            onClick={() => props.onToggleDocument(doc.document_id)}
          >
            <header>
              <a href={doc.scp_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                {doc.scp_number}
              </a>
            </header>
            <p className="card-location">{doc.location_display ?? "Unknown location"}</p>
            <div className="card-meta-row">
              <span className="card-meta-pill">PDF: {doc.pdf_url ? "Available" : "Missing"}</span>
              {props.activeVisualizationDocumentId === doc.document_id ? (
                <span className="card-meta-pill emphasis">Active visualization</span>
              ) : null}
            </div>
            <PdfThumbnail
              thumbnailUrl={doc.thumbnail_url ?? null}
              hasPdf={Boolean(doc.pdf_url)}
              alt={`Preview for ${doc.scp_number}`}
              onClick={() => props.onOpenPdf(doc.document_id)}
            />
            {props.activeVisualizationDocumentId === doc.document_id ? (
              <p className="offscreen-count badge">Offscreen linked locations: {props.offscreenLinkCount}</p>
            ) : null}
          </article>
        ))}
      </div>
      {props.canLoadMore ? (
        <div className="load-more-row">
          <button type="button" onClick={props.onLoadMore} disabled={props.isLoadingMore}>
            {props.isLoadingMore ? "Loading..." : "Load more"}
          </button>
        </div>
      ) : null}
    </aside>
  );
}
