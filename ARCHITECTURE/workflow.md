BURNT AREA MAPPING WORKFLOW

1. User opens the dashboard

2. User selects:
   • State
   • District
   • Season
   • Year

3. Frontend sends request to REST API

4. FastAPI receives request

5. FastAPI sends request to Google Earth Engine

6. Google Earth Engine:
   • Loads Sentinel-2 imagery
   • Performs cloud masking
   • Calculates NBR
   • Calculates dNBR
   • Detects burnt area
   • Classifies burn severity

7. Statistics are generated

8. Results are returned as JSON

9. Frontend displays:
   • Burnt Area Map
   • Statistics
   • Charts
   • Download Options
   