# Phase 12 — Execution Checklist

Before considering phase 12 complete, verify:

- search is API-backed, not client-only
- search results replace right-panel location content while search is active
- map recenters or fits results on search
- document cards use canonical SCP number, contextual location, and PDF thumbnail
- PDF thumbnails are rendered on the client with pdfjs-dist
- PDF opens in a centered modal
- pinned document visualization survives map drag
- empty-map click clears pinned document and pinned location state
- visible document links recompute as viewport changes
- offscreen linked-location count updates during pinned-document mode
- country/region polygons come from static assets
- static geometry asset build is integrated into analytics (not presentation runtime and not geocoder runtime)
- city remains point geometry
- polygon click behavior matches point click behavior
- backend/API/tests are aligned with phase 12 contracts
- no presentation writes are introduced
- geometry coverage diagnostics exist for unmatched country/region targets
