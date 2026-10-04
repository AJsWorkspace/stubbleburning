GEOSPATIAL WEB APPLICATION FOR BURNT AREA MAPPING

SYSTEM ARCHITECTURE

User
 ↓

Frontend Dashboard
(HTML + CSS + JavaScript + Leaflet)

 ↓

REST API Layer
(FastAPI)

 ↓

Google Earth Engine

 ↓

Sentinel-2 Imagery

 ↓

Burnt Area Detection Workflow

 • Cloud Masking
 • NBR Calculation
 • dNBR Calculation
 • Burnt Area Extraction
 • Severity Classification

 ↓

Statistics Generation

 ↓

JSON Response

 ↓

Frontend Dashboard

 • Burnt Area Map
 • Statistics
 • Charts
 • Downloads