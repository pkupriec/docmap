# Service Boundaries Summary

Write ownership:
- crawler -> document ingestion tables
- extractor -> extraction tables
- geocoder -> geo resolution tables
- analytics -> BI tables
- control -> pipeline metadata tables
- presentation -> no writes

Read [SERVICES.md](SERVICES.md) for full ownership and boundary rules.