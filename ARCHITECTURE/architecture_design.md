GEOSPATIAL WEB APPLICATION FOR BURNT AREA MAPPING

COMPLETE SYSTEM ARCHITECTURE

┌─────────────────────────────┐
│            USER             │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│      FRONTEND DASHBOARD     │
│ HTML + CSS + JS + Leaflet   │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│         REST API            │
│          FastAPI            │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│   GOOGLE EARTH ENGINE       │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│     SENTINEL-2 IMAGERY      │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│  BURNT AREA PROCESSING      │
│  • Cloud Masking            │
│  • NBR                      │
│  • dNBR                     │
│  • Burn Severity            │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│    STATISTICS GENERATION    │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│      JSON RESPONSE          │
└──────────────┬──────────────┘
               │
               ▼

┌─────────────────────────────┐
│      FRONTEND OUTPUT        │
│ • Burnt Area Map            │
│ • Statistics                │
│ • Charts                    │
│ • Downloads                 │
└─────────────────────────────┘