API DESIGN
--------------------------------

ENDPOINT 1

POST /analyze

Purpose:
Generate Burnt Area Analysis

Input:

{
  "state": "Punjab",
  "district": "Ludhiana",
  "season": "Kharif",
  "year": "2025"
}

Output:

{
  "burnt_area": 1250,
  "low_severity": 320,
  "medium_severity": 610,
  "high_severity": 320
}

--------------------------------

ENDPOINT 2

GET /download/pdf

Purpose:
Download PDF Report

--------------------------------

ENDPOINT 3

GET /download/csv

Purpose:
Download CSV Statistics

--------------------------------

ENDPOINT 4

GET /health

Purpose:
Check API Status