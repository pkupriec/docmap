# Processing Pipeline

1 Crawl SCP Wiki pages

2 Create document snapshots
- raw_html
- clean_text
- pdf_snapshot

3 LLM Extraction

Extract geographic mentions.

Output JSON:

{
  "locations":[
    {
      "mention_text":"near Kyoto",
      "normalized_location":"Kyoto, Japan",
      "precision":"city",
      "confidence":0.84,
      "evidence_quote":"Recovered near Kyoto in 1993."
    }
  ]
}

4 Location normalization

5 Geocoding via Nominatim

6 Store results in PostGIS

7 Generate analytics tables

8 Export to BigQuery