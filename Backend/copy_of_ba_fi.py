import requests
import os
import ee
import geemap
from datetime import datetime
from progress import update_progress
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

dates_only = globals().get("dates_only", False)
selected_date = globals().get("selected_date", None)
try:
    selected_date
except NameError:
    selected_date = None

#Authenticate and initialize Earth Engine
service_account = "stubble-burning-restfulapi@stubbleburning-api.iam.gserviceaccount.com"

credentials = ee.ServiceAccountCredentials(
    service_account,
    "Backend/stubbleburning-api-dbbb45eb2716.json"
)

ee.Initialize(
    credentials,
    project="stubbleburning-api"
)

state = globals().get("state", "Firozpur")
season = globals().get("season", "Rabi")
year = globals().get("year", 2026)
selected_date = globals().get("selected_date", None)
dates_only = globals().get("dates_date", None)
duration = globals().get("duration", "latest_date")

start_date = globals().get("start_date", None)

end_date = globals().get("end_date", None)

#duration for burnt area mapping
start_date = f"{year}-03-16"
end_date   = f"{year}-06-01"

#duration for NDVI season max
start_ndvi = "2025-12-01"
end_ndvi   = f"{year}-02-28"

#duration for MIRBI season
start_mirbi = f"{year}-03-01"
end_mirbi   = end_date

#AOI assets with if statements for Punjab, Haryana and UP_NCR
if state == "Firozpur":
    aoi = ee.FeatureCollection('projects/stubbleburning-2025/assets/Firozpur')
else:
    raise ValueError("Invalid state name, kindly check") ## ensure above assets are right

#define esa worldcover agrimask
worldCover = ee.ImageCollection('ESA/WorldCover/v100').first().clip(aoi)
croplandMask = worldCover.eq(40)

#lulc mask assets
if state == "Firozpur":
    lulcMask = ee.Image('projects/stubbleburning-2025/assets/Firozpur_lulc_gcs84')
else:
    raise ValueError("Invalid state name, kindly check") ## ensure above assets are right

lulc_mask = lulcMask.eq(5).clip(aoi)

#Paddy or Wheat masks defined based on crop season
if season == "Kharif":
    paddyMask = ee.Image('projects/ee-stubbleburning2024/assets/paddymask_pb')
elif season == "Rabi":
    wheatMask = ee.Image('projects/stubbleburning-2025/assets/wheat_mask_Firozpur_final_2026_10m_GCS')
else:
    raise ValueError("Invalid mask. kindly check") ## ensure above assets are right

"""
#water mask assets (manually created)
if state == "Firozpur":
    water_fc = ee.FeatureCollection('projects/stubble-burning-447105/assets/punjab_watermask_manual')
else:
    raise ValueError("Invalid state name") ## ensure above assets are right
"""

# Call the sentinel collection
collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(aoi)
      .filterDate(start_ndvi, end_mirbi))

# ---------------------------------
# Seasonmax NDVI
# ---------------------------------
collection_NDVI = collection.filterDate(start_ndvi, end_ndvi)
def add_ndvi(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)
ndvi_collection = collection_NDVI.map(add_ndvi).select('NDVI')
season_max_ndvi = ndvi_collection.max().clip(aoi)
season_max_ndvi_th = season_max_ndvi.gt(0.3)

# ---------------------------------
# MIRBI Season
# ---------------------------------
collection_MIRBI = collection.filterDate(start_mirbi, end_mirbi)
def add_MIRBI(image):
    mirbi = image.expression(
        '((10 * SWIR2 - 9.8 * SWIR1 + 2))',
        {
            'SWIR1': image.select('B11'),
            'SWIR2': image.select('B12')
        }
    ).rename('MIRBI')
    return image.addBands(mirbi)
mirbi_collection = collection_MIRBI.map(add_MIRBI).select('MIRBI')
mirbi_season = mirbi_collection.reduce(ee.Reducer.min()).rename('MIRBI_season_min').clip(aoi)
MIRBI_Season_th = mirbi_season.gt(-3000).rename('MIRBI_Season')

def clip_image(image):
    return image.clip(aoi)

def cloud_pct(image):
  cloud_pct = ee.Number(image.get('CLOUDY_PIXEL_PERCENTAGE')).float()
  return image.set('cloud_pct', cloud_pct)

collection_dates = (collection
                      .filterDate(start_date, end_date)
                      .map(cloud_pct)
                      .map(clip_image))

def extract_date_from_index(image):
    idx = ee.String(image.get('system:index'))
    yyyymmdd = idx.slice(0, 8)
    yyyy = yyyymmdd.slice(0, 4)
    mm = yyyymmdd.slice(4, 6)
    dd = yyyymmdd.slice(6, 8)
    date_iso = yyyy.cat('-').cat(mm).cat('-').cat(dd)

    return image.set('date_from_index', date_iso)

collection_dates = collection_dates.map(extract_date_from_index)

# Get distinct list of acquisition dates
distinct_dates = collection_dates.aggregate_array('date_from_index').distinct().sort()

# Convert list to Python
distinct_dates_list = distinct_dates.getInfo()
"""
print("Total unique acquisition dates:", len(distinct_dates_list))
print("\nAvailable dates:")
for d in distinct_dates_list:
    print(d)
"""

#print("\nDate-wise summary:\n")

date_tile_info = []

for d in distinct_dates_list:

    daily_images = collection_dates.filter(
        ee.Filter.eq('date_from_index', d)
    )

    tile_count = daily_images.size().getInfo()

    avg_cloud = round(
       daily_images.aggregate_mean('cloud_pct').getInfo(),
       2
    )


    print(
        f"{d} ---> {tile_count} tile(s) ---> Avg Cloud %: {avg_cloud}"
    )

    date_tile_info.append({
        "date": d,
        "tile_count": tile_count,
        "avg_cloud": avg_cloud
    })

from datetime import datetime, timedelta

# =========================================================
# STEP 1 — USE EXACT WORKING DATE SORTING LOGIC
# (latest → oldest using interval-based backtracking)
# =========================================================

print("\n" + "=" * 70)
print("STEP 1 — Latest to oldest dates using interval logic")
print("=" * 70)

# User-specified interval (in days)
interval_days = 1

# Convert distinct dates to datetime
date_objs = [
    datetime.strptime(d, "%Y-%m-%d")
    for d in distinct_dates_list
]

# Latest available date
if selected_date:

    latest_date = datetime.strptime(
        selected_date,
        "%Y-%m-%d"
    )

else:

    latest_date = max(date_objs)

# Start from latest date and keep moving backward
selected_dates = [latest_date]

# No fixed num_days needed — collect all available dates
while True:
    next_target = selected_dates[-1] - timedelta(days=interval_days)

    # Find closest available date <= next_target
    prev_dates = [
        d for d in date_objs
        if d <= next_target
    ]

    if prev_dates:
        selected_dates.append(max(prev_dates))
    else:
        break
print("Reached latest_dates block")
print("dates_only =", dates_only)
# Final sort latest → oldest
selected_dates = sorted(selected_dates, reverse=True)

latest_dates = [
    d.strftime("%Y-%m-%d")
    for d in selected_dates
]

# ----------------------------------------
# If user selected a specific date
# ----------------------------------------

if selected_date is not None:

    if selected_date in latest_dates:

        latest_dates = [selected_date]

    else:

        raise Exception(f"{selected_date} not available")

#print(f"\nTotal dates available: {len(latest_dates)}\n")

# =========================================================
# Attach tile count + avg cloud %
# =========================================================
from datetime import datetime, timedelta

# =========================================================
# STEP 1 — DATE SORTING
# =========================================================

interval_days = 1

date_objs = [
    datetime.strptime(d, "%Y-%m-%d")
    for d in distinct_dates_list
]

latest_date = max(date_objs)

selected_dates = [latest_date]

while True:

    next_target = (
        selected_dates[-1]
        - timedelta(days=interval_days)
    )

    prev_dates = [
        d for d in date_objs
        if d <= next_target
    ]

    if prev_dates:
        selected_dates.append(max(prev_dates))
    else:
        break

selected_dates = sorted(
    selected_dates,
    reverse=True
)

latest_dates = [
    d.strftime("%Y-%m-%d")
    for d in selected_dates
]

# =========================================================
# STEP 2 — ATTACH TILE INFO
# =========================================================

date_lookup = {
    item["date"]: item
    for item in date_tile_info
}

sorted_date_info = [
    date_lookup[d]
    for d in latest_dates
]

# =========================================================
# STEP 2A — FILTER CLOUD
# =========================================================

filtered_dates = [
    d for d in sorted_date_info
    if d["avg_cloud"] <= 50
]

# =========================================================
# STEP 2B — TILE GROUPING
# =========================================================

ignored_dates = []

category_A = []
category_B = []
category_C = []

for d in filtered_dates:

    tc = d["tile_count"]

    # Ignore tiny coverage
    if tc <= 2:
        ignored_dates.append(d)
        continue

    # CATEGORY A
    if tc == 3 or tc > 3:
        category_A.append(d)

# =========================================================
# STEP 2A — FILTER avg_cloud <= 50
# =========================================================

print("\n" + "=" * 70)
print("STEP 2A — Filter dates where avg cloud <= 50%")
print("=" * 70)

filtered_dates = [
    d for d in sorted_date_info
    if d["avg_cloud"] <= 50
]

print(f"\nDates after filtering: {len(filtered_dates)}\n")

for d in filtered_dates:
    print(
        f"{d['date']}   --->   "
        f"{d['tile_count']} tile(s)   --->   "
        f"Avg Cloud %: {d['avg_cloud']}"
    )


# =========================================================
# STEP 2B — GROUP INTO TILE COUNT CATEGORIES
# =========================================================
# CATEGORY_A:
#   tile_count == 3
#   OR tile_count > 3
#
#
#print("\n" + "=" * 70)
#print("STEP 2B — Grouping by tile count categories")
#print("=" * 70)

ignored_dates = []

category_A = []
category_B = []
category_C = []

for d in filtered_dates:

    tc = d["tile_count"]

    # -----------------------------------------------------
    # IGNORE small partial coverage
    # -----------------------------------------------------
    if tc <= 2:

        ignored_dates.append(d)

    # -----------------------------------------------------
    # CATEGORY A
    # 3-tile workflow
    # Includes:
    #   exact 3-tile
    #   AND >3 tile dates
    # -----------------------------------------------------
    if tc == 3 or tc > 3:

        category_A.append(d)
        
# ----------------------------------------
# If frontend only wants available dates
# ----------------------------------------

if dates_only:

    result_data = {
        "available_dates": [ d["date"] for d in category_A ]
    }

    raise SystemExit(result_data)

def print_category(title, items):
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)
    print(f"Total dates: {len(items)}\n")

    for d in items:
        print(
            f"{d['date']}   --->   "
            f"{d['tile_count']} tile(s)   --->   "
            f"Avg Cloud %: {d['avg_cloud']}"
        )


# =========================================================
# PRINT CATEGORIES
# =========================================================

print_category(
    "IGNORED DATES → tile count <= 2",
    ignored_dates
)

print_category(
    "CATEGORY_A → 3 tiles OR >3 tiles",
    category_A
)

print("\n" + "=" * 70)
print("STEP 3 — Auto selecting day_0, day_1, day_2")
print("=" * 70)

# ---------------------------------------------------------
# Remove tile_count <= 2 completely
# ---------------------------------------------------------

filtered_dates_no_small = [
    d for d in filtered_dates
    if d["tile_count"] > 2
]

#print("\nAfter removing tile_count <= 2:\n")

for d in filtered_dates_no_small:
    print(
        f"{d['date']}   --->   "
        f"{d['tile_count']} tile(s)   --->   "
        f"Avg Cloud %: {d['avg_cloud']}"
    )

if len(filtered_dates_no_small) == 0:
    raise ValueError("No valid dates left after filtering.")

# ---------------------------------------------------------
# Latest valid date
# ---------------------------------------------------------

if selected_date:

    day_0_info = next(
        (
            d for d in filtered_dates_no_small
            if d["date"] == selected_date
        ),
        None
    )

    if day_0_info is None:

        print(
            f"{selected_date} not available after filtering."
        )

        print(
            "Using latest valid date instead."
        )

        day_0_info = filtered_dates_no_small[0]

else:

    day_0_info = filtered_dates_no_small[0]

latest_date = day_0_info["date"]
day0_avg_cloud = day_0_info["avg_cloud"]

available_dates = [
    d["date"]
    for d in filtered_dates_no_small
]

result_data = {
    "latest_date": latest_date,
    "avg_cloud": day0_avg_cloud,
    "burnt_area": 0,
    "available_dates": available_dates
}
if dates_only:
    raise SystemExit(result_data)

print("\nLatest valid date selected as day_0:\n")

print(
    f"{day_0_info['date']}   --->   "
    f"Avg Cloud %: {day_0_info['avg_cloud']}"
)

latest_tile_count = day_0_info["tile_count"]

# =========================================================
# CASE 1 → day_0 >= 3 tiles
# =========================================================

if latest_tile_count >= 3:


    print("\n" + "-" * 70)
    print("CASE 1 → day_0 has 3 tiles")
    print("Allowed fallback categories:")
    print("  - tile_count == 3")
    print("  - tile_count > 3")
    print("-" * 70)

    selected_category = category_A

    print("\nCandidate dates:\n")

    for d in selected_category:
        print(
            f"{d['date']}   --->   "
            f"{d['tile_count']} tile(s)   --->   "
            f"Avg Cloud %: {d['avg_cloud']}"
        )
    
    selected_triplet = selected_category[:3]

    print("\nSelected dates:\n")

    for i, d in enumerate(selected_triplet):

        if i == 0:
            label = "day_0"
        elif i == 1:
            label = "day_1"
        else:
            label = "day_2"

        print(
            f"{label}: {d['date']}   --->   "
            f"{d['tile_count']} tile(s)   --->   "
            f"Avg Cloud %: {d['avg_cloud']}"
        )

    day_0 = selected_triplet[0]["date"]
    day_1 = selected_triplet[1]["date"]
    day_2 = selected_triplet[2]["date"]

# =========================================================
# FINAL NORMAL OUTPUT
# (only for CASE 1)
# =========================================================

if latest_tile_count >= 3:

    print("\n" + "=" * 70)
    print("FINAL VARIABLES")
    print("=" * 70)

    print("day_0 =", day_0)
    print("day_1 =", day_1)
    print("day_2 =", day_2)

# =========================================================
# STEP 1 — COLLECT DATES REQUIRED FOR PROCESSING
# =========================================================

print("\n" + "=" * 70)
print("COLLECTING REQUIRED DATES")
print("=" * 70)

# ---------------------------------------------------------
# Collect dates depending on processing mode
# ---------------------------------------------------------

selected_dates_visualize = []

# CASE 1 - NORMAL MODE
if latest_tile_count >= 3:

    selected_dates_visualize = [
        day_0,
        day_1,
        day_2
    ]

print("\nSelected dates:\n")
for d in selected_dates_visualize:
    print(d)

# =========================================================
# STEP 3 — PREPROCESS ONLY REQUIRED IMAGES
# =========================================================
# ---------------------------------------------------------
# Cloud masking + resampling
# ---------------------------------------------------------

def preprocess_s2(image):

    scl = image.select('SCL')
    qa = image.select('QA60')

    # QA60 bits
    cloud = qa.bitwiseAnd(1 << 10).neq(0)
    cirrus = qa.bitwiseAnd(1 << 11).neq(0)

    qa_cloud = cloud.Or(cirrus)

    # SCL cloud classes
    scl_invalid = (
        scl.eq(3)   # cloud shadow
        .Or(scl.eq(8))   # medium cloud
        .Or(scl.eq(9))   # high cloud
        .Or(scl.eq(10))  # cirrus
    )

    combined_cloud = (
        scl_invalid
        .Or(qa_cloud)
        .rename('cloud_mask')
    )

    # -----------------------------------------------------
    # Cloud buffer
    # -----------------------------------------------------

    cloud_buffer = combined_cloud.focal_max(
        radius=500,
        units='meters'
    )

    clear_mask = cloud_buffer.Not()

    masked = image.updateMask(clear_mask)

    # -----------------------------------------------------
    # Resample 20m → 10m
    # -----------------------------------------------------

    bands_10m = [
        'B2', 'B3', 'B4', 'B8'
    ]

    bands_20m = [
        'B5', 'B6', 'B7',
        'B8A', 'B11', 'B12'
    ]

    reference_proj = (
        masked
        .select('B8')
        .projection()
    )

    resampled_bands = (
        masked
        .select(bands_20m)
        .resample('bilinear')
        #.reproject(crs=reference_proj)
    )

    merged = (
        masked
        .select(bands_10m)
        .addBands(resampled_bands)
    )

    scaled = merged.divide(10000)

    return (
        scaled
        .addBands(combined_cloud)
        .copyProperties(image, image.propertyNames())
    )


# ---------------------------------------------------------
# Apply preprocessing ONLY to selected images
# ---------------------------------------------------------

# Filter only required dates
collection_burnt = (
    collection_dates
    .filter(
        ee.Filter.inList(
            'date_from_index',
            selected_dates_visualize
        )
    )
    .map(preprocess_s2)
)

# =========================================================
# BUILD DATE LOOKUP DICTIONARY
# =========================================================

date_collections = {}

for d in selected_dates_visualize:

    daily_collection = collection_burnt.filter(
        ee.Filter.eq('date_from_index', d)
    )

    date_collections[d] = daily_collection
# =========================================================
# STEP 4 — PRINT DATE SUMMARY
# =========================================================

print("\n" + "=" * 70)
print("SELECTED DATES SUMMARY")
print("=" * 70)

day0_avg_cloud = None
for i, d in enumerate(selected_dates_visualize):

    daily_collection = date_collections[d]

    tile_count = daily_collection.size().getInfo()

    avg_cloud = (
        daily_collection
        .aggregate_mean('cloud_pct')
        .getInfo()
    )

    avg_cloud = round(avg_cloud, 2)
    if i == 0:
        day0_avg_cloud = avg_cloud

    print(
        f"{d}   --->   "
        f"{tile_count} tile(s)   --->   "
        f"Avg Cloud %: {avg_cloud}"
    )

# =========================================================
# BUILD MOSAICS
# =========================================================

print("\nBuilding mosaics...\n")


# Function to mosaic all tiles for a given date
def mosaic_for_date(date_str):
    date_filter = ee.Filter.eq('date_from_index', date_str)
    daily_images = date_collections[date_str]
    mosaic = daily_images.mosaic().clip(aoi)
    return mosaic.set('date_from_index', date_str)

mosaics = {}

for d in selected_dates_visualize:

    #print(f"Creating mosaic for {d}")

    mosaics[d] = mosaic_for_date(d)

# =========================================================
# FUNCTION TO ADD INDICES
# =========================================================

def addIndices(image):

    ndvi = image.normalizedDifference(
        ['B8', 'B4']
    ).rename('NDVI')

    mirbi = image.expression(
        '(10 * SWIR2 - 9.8 * SWIR1 + 0.0002) * 10000',
        {
            'SWIR1': image.select('B11'),
            'SWIR2': image.select('B12')
        }
    ).rename('MIRBI')

    nbr = image.normalizedDifference(
        ['B8', 'B12']
    ).rename('NBR')

    return image.addBands([
        ndvi,
        mirbi,
        nbr
    ])


# =========================================================
# ADD INDICES TO EXISTING MOSAICS
# =========================================================

indexed_mosaics = {}

for d in selected_dates_visualize:

    #print(f"Adding indices to {d}")

    indexed_mosaics[d] = addIndices(
        mosaics[d]
    )

# =========================================================
# STORE SELECTED VISUALIZATION DATES
# =========================================================

days = {}
days_next = {}

# Store dates
for i, d in enumerate(selected_dates_visualize):

    days[f"day_{i}_l"] = d

# =========================================================
# PRINT RESULTS
# =========================================================

print("\nStored date variables:\n")

for i in range(len(selected_dates_visualize)):

    print(f"day_{i}_l: {days[f'day_{i}_l']}")

# =========================================================
# BUILD PROCESSING BATCHES
# =========================================================

processing_batches = []

# ---------------------------------------------------------
# NORMAL MODE
# ---------------------------------------------------------

if latest_tile_count >= 3:

    processing_batches.append({

        "batch_name": "single_run",

        "d0_auto": selected_triplet[0]["date"],
        "d1_auto": selected_triplet[1]["date"],
        "d2_auto": selected_triplet[2]["date"]

    })


# =========================================================
# DEBUG
# =========================================================

print("\n" + "=" * 70)
print("PROCESSING BATCHES")
print("=" * 70)

for batch in processing_batches:

    print("\nBatch:", batch["batch_name"])

    print("d0_auto =", batch["d0_auto"])
    print("d1_auto =", batch["d1_auto"])
    print("d2_auto =", batch["d2_auto"])


# =========================================================
# FUNCTION TO GET NEXT DATE
# =========================================================

from datetime import datetime, timedelta

def next_day(date_string):

    return (
        datetime.strptime(date_string, "%Y-%m-%d")
        + timedelta(days=1)
    ).strftime("%Y-%m-%d")

# =========================================================
# STORE FINAL OUTPUTS
# =========================================================

batch_outputs = {}
batch_outputs_3class = {}
burn_image_list = []


# =========================================================
# PROCESS EACH BATCH
# =========================================================

for batch in processing_batches:

    print("\n" + "=" * 70)
    print("RUNNING:", batch["batch_name"])
    print("=" * 70)

    # -----------------------------------------------------
    # DEFINE DATES
    # -----------------------------------------------------

    d0_auto = batch["d0_auto"]
    d1_auto = batch["d1_auto"]
    d2_auto = batch["d2_auto"]

    day_0_n = next_day(d0_auto)
    day_1_n = next_day(d1_auto)
    day_2_n = next_day(d2_auto)

    #print("day_0:", d0_auto, " ---> ", day_0_n)
    #print("day_1:", d1_auto, " ---> ", day_1_n)
    #print("day_2:", d2_auto, " ---> ", day_2_n)


    # =====================================================
    # LOAD DATE MOSAICS
    # =====================================================

    img_d0 = indexed_mosaics[d0_auto]
    img_d1 = indexed_mosaics[d1_auto]
    img_d2 = indexed_mosaics[d2_auto]


    # =====================================================
    # EXTRACT REQUIRED BANDS
    # =====================================================

    # MIRBI
    Date_n2_MIRBI = img_d2.select(
        'MIRBI'
    ).rename('Date_n2_MIRBI')

    Date_n1_MIRBI = img_d1.select(
        'MIRBI'
    ).rename('Date_n1_MIRBI')

    Date_0_MIRBI = img_d0.select(
        'MIRBI'
    ).rename('Date_0_MIRBI')


    # NDVI
    Date_0_NDVI = img_d0.select(
        'NDVI'
    ).rename('Date_0_NDVI')


    # NBR
    Date_0_NBR = img_d0.select(
        'NBR'
    ).rename('Date_0_NBR')


    # B7 / B8
    Day_0_b7 = img_d0.select(
        'B7'
    ).rename('Day_0_b7')

    Day_0_b8 = img_d0.select(
       'B8'
    ).rename('Day_0_b8')


    # =====================================================
    # DIFFERENCE STACKS
    # =====================================================

    Diff_Date_0_Date_n1_MIRBI = (
        Date_0_MIRBI
        .subtract(Date_n1_MIRBI)
        .rename('Date_0_minus_Date_n1')
    )

    Diff_Date_0_Date_n2_MIRBI = (
        Date_0_MIRBI
        .subtract(Date_n2_MIRBI)
        .rename('Date_0_minus_Date_n2')
    )


    # =====================================================
    # BUILD FINAL STACK
    # =====================================================

    ls = ee.Image.cat([

        Date_n2_MIRBI,
        Date_n1_MIRBI,
        Date_0_MIRBI,

        Day_0_b7,
        Day_0_b8,

        Diff_Date_0_Date_n2_MIRBI,
        Diff_Date_0_Date_n1_MIRBI,

        Date_0_NBR,
        Date_0_NDVI

    ]).rename([

        'Date_n2_MIRBI',
        'Date_n1_MIRBI',
        'Date_0_MIRBI',

        'Day_0_b7',
        'Day_0_b8',

        'Date_0_minus_Date_n2_MIRBI',
        'Date_0_minus_Date_n1_MIRBI',

        'Date_0_NBR',
        'Date_0_NDVI'

    ]).clip(aoi)


    # =====================================================
    # CLASSIFICATION
    # =====================================================

    d0_mirbi = ls.select('Date_0_MIRBI')
    d1_mirbi = ls.select('Date_n1_MIRBI')
    d2_mirbi = ls.select('Date_n2_MIRBI')
    d0_d1_diff = ls.select('Date_0_minus_Date_n1_MIRBI')
    d0_d2_diff = ls.select('Date_0_minus_Date_n2_MIRBI')
    d0_nbr = ls.select('Date_0_NBR')
    d0_ndvi = ls.select('Date_0_NDVI')
    d0_b7 = ls.select('Day_0_b7')
    d0_b8 = ls.select('Day_0_b8')

    classified = ee.Image(0)
    #&& Date_0_NDVI>0 && Date_0_NDVI<=0.25
    classified = classified.where(
       (d0_mirbi.gte(-4500))
       .And(d1_mirbi.lte(-7500))
       .And(d0_d1_diff.gte(4000))
       .And(d0_nbr.lte(0.05))
       .And(d0_ndvi.lte(0.25))
       .And(d0_ndvi.gt(0))
       .And(d0_b7.lt(0.25))
       .And(d0_b8.lt(0.25)),
       1
    )

    classified = classified.where(
       (d0_mirbi.gte(-1500))
       .And(d2_mirbi.lt(-5500))
       .And(d0_d2_diff.gte(5000))
       .And(d0_nbr.lte(0.05))
       .And(d0_ndvi.lte(0.25))
       .And(d0_ndvi.gt(0))
       .And(d0_b7.lt(0.25))
       .And(d0_b8.lt(0.25)),
       2
    )

    classified = classified.where(
       (d0_mirbi.gte(-4500))
       .And(d2_mirbi.lte(-8000))
       .And(d0_d2_diff.gte(4000))
       .And(d0_nbr.lte(0.05))
       .And(d0_ndvi.lte(0.25))
       .And(d0_ndvi.gt(0))
       .And(d0_b7.lt(0.25))
       .And(d0_b8.lt(0.25)),
       3
    )

    classified = classified.where(
       (d0_mirbi.gte(-2500))
       .And(d1_mirbi.gte(-2500))
       .And(d0_nbr.lte(0.05))
       .And(d0_ndvi.lte(0.25))
       .And(d0_ndvi.gt(0))
       .And(d0_b7.lt(0.25))
       .And(d0_b8.lt(0.25)),
       4
    )

    classified = classified.where(d0_ndvi.gte(0.35), 5)

    classified = classified.where(d0_mirbi.lt(-7500), 6) #others  includes harvest, fallow, ploughed and more

    classified = classified.where(
       (d0_mirbi.gte(-1500))
       .And(d1_mirbi.lt(-5500))
       .And(d0_d1_diff.gte(5000))
       .And(d0_nbr.lte(0.05))
       .And(d0_ndvi.lte(0.25))
       .And(d0_ndvi.gt(0))
       .And(d0_b7.lt(0.25))
       .And(d0_b8.lt(0.25)),
       7
    )

    classified = classified.rename('Class')


    # =====================================================
    # FINAL MASKING
    # =====================================================

    c1 = classified.eq(1)
    c2 = classified.eq(2)
    c3 = classified.eq(3)
    c4 = classified.eq(4)
    c5 = classified.eq(5)
    c6 = classified.eq(6)
    c7 = classified.eq(7)

    valid_mirbi = MIRBI_Season_th.Not()

    c1_valid = c1.And(valid_mirbi)
    c2_valid = c2.And(valid_mirbi)
    c3_valid = c3.And(valid_mirbi)
    c4_valid = c4.And(valid_mirbi)

    c5_valid = c5
    c6_valid = c6
    c7_valid = c7

    final_mask = (
        c1_valid
        .Or(c2_valid)
        .Or(c3_valid)
        .Or(c4_valid)
        .Or(c5_valid)
        .Or(c6_valid)
        .Or(c7_valid)
    )

    final_mask = (
        final_mask
        .And(lulc_mask)
        .And(croplandMask)
        .And(season_max_ndvi_th)
        .And(wheatMask)
    )

    final_classified = classified.updateMask(final_mask)

    final_classified_uint8 = final_classified.toUint8()

    patch_size = final_classified_uint8.connectedPixelCount(
      maxSize=100,          # should be > threshold
      eightConnected=True   # 8-neighbour connectivity
    )

    final_sieved = (
        final_classified_uint8
        .updateMask(patch_size.gte(10))
        .toUint8()
    )

    # final_sieved is your cleaned output
    #("Sieve completed: removed patches smaller than 10 pixels")


    # =====================================================
    # STORE OUTPUT
    # =====================================================

    batch_outputs[batch["batch_name"]] = final_sieved

    #print("\nCompleted:", batch["batch_name"])


    # ---------------------------------
    # Reclassify to 3 classes
    # ---------------------------------

    # Class 1 = Burnt (original classes 1,2,3,4,7)
burn_class = (
        final_sieved.eq(1)
        .Or(final_sieved.eq(2))
        .Or(final_sieved.eq(3))
        .Or(final_sieved.eq(4))
        .Or(final_sieved.eq(7))
    )
burn_binary = burn_class.rename('Burn').toUint8()

burn_image_list.append(
    burn_binary.set("date", d0_auto)
    )

burn_collection = ee.ImageCollection.fromImages(
    burn_image_list
   )

print("Total burn images:",
      burn_collection.size().getInfo())

burn_frequency = (
    burn_collection.reduce(ee.Reducer.sum())
    .rename("Burn_Frequency")
    )

cumulative_burn = (
    burn_frequency.gt(0)
    .rename("Cumulative_BA")
    .toUint8()
    )

print("Reached 3-class conversion")


    # Class 2 = Crop (original class 5)
crop_class = final_sieved.eq(5)

    # Class 3 = Others (original class 6)
other_class = final_sieved.eq(6)

    # Start from 0
classified_3class = ee.Image(0)
print("Created empty image")

classified_3class = classified_3class.where(burn_class,1)
print("Added burn")

classified_3class = classified_3class.where(crop_class,2)
print("Added crop")

classified_3class = classified_3class.where(other_class,3)
print("Added other")

classified_3class = classified_3class.rename("Class_3")
print("Renamed")
classified_3class_uint8 = classified_3class.toUint8().clip(aoi)
png_url = classified_3class_uint8.visualize(
    min=0,
    max=3,
    palette=[
        "808080",   # Background
        "8B0000",   # Burnt
        "00FF00",   # Crop
        "FFFF00"    # Harvest
    ]
).getThumbURL({
    "region": aoi.geometry(),
    "dimensions": 1500,
    "format": "png"
})

result_data["png_url"] = png_url

cumulative_png_url = cumulative_burn.selfMask().visualize(
    palette=["FF0000"]      # red only
).getThumbURL({
    "region": aoi.geometry(),
    "dimensions": 1500,
    "format": "png"
})

result_data["cumulative_png_url"] = cumulative_png_url

    # Create output folder if it doesn't exist
os.makedirs("Backend/outputs", exist_ok=True)


boundary = ee.Image().byte().paint(
    featureCollection=aoi,
    color=1,
    width=1
    )
boundary_map = boundary.getMapId({
    'palette': ['000000']
    })

result_data["boundary_url"] = boundary_map["tile_fetcher"].url_format

vis_params = {
    'min': 0,
    'max': 3,
    'palette': [
        '808080',  # grey
        '8B0000',  # Burnt
        '00FF00',  # Crop
        'FFFF00'   # Harvest
    ]
    }

palette = [
    '808080',  # 0 → black
    '8B0000',  # 1 → Dark red (severe burn)
    '00FF00',  # 2 → Green (crop)
    'FFFF00',  # 3 → Yellow (Harvest)
    ]

classified_3class_uint8 = classified_3class.toUint8().clip(aoi)
map_id = classified_3class_uint8.getMapId(vis_params)

print("Day 0 Cloud:", day0_avg_cloud)

result_data["latest_date"] = latest_date
result_data["avg_cloud"] = day0_avg_cloud
result_data["burnt_area"] = 0
result_data["tile_url"] = map_id["tile_fetcher"].url_format


# inside batch loop after classified_3class_uint8
batch_outputs_3class[batch["batch_name"]] = classified_3class_uint8

print(
    "Stored 3-class output for:",
    batch["batch_name"]
    )

print("\nAvailable 7-class outputs:")
print(batch_outputs.keys())

print("\nAvailable 3-class outputs:")
print(batch_outputs_3class.keys())

# ===========================================
# BUILD CUMULATIVE BURN MAP
# ===========================================

burn_collection = ee.ImageCollection.fromImages(
    burn_image_list
)

print("Total burn images:",
      burn_collection.size().getInfo())

burn_frequency = (
    burn_collection.reduce(ee.Reducer.sum())
    .rename("Burn_Frequency")
)

cumulative_burn = (
    burn_frequency.gt(0)
    .rename("Cumulative_BA")
    .toUint8()
)

cumulative_map = cumulative_burn.getMapId({
    "min": 0,
    "max": 1,
    "palette": ["red"]
})

print("Latest URL")
print(map_id["tile_fetcher"].url_format)

print("Cumulative URL")
print(cumulative_map["tile_fetcher"].url_format)
result_data["cumulative_tile_url"] = cumulative_map["tile_fetcher"].url_format

Map = geemap.Map()
Map.centerObject(aoi, 15)

# Latest Date Classification
Map.addLayer(
    classified_3class_uint8,
    vis_params,
    "Latest Date Classification"
)

# Cumulative Burn Area
Map.addLayer(
    cumulative_burn,
    {
        "min": 0,
        "max": 1,
        "palette": ["red"]
    },
    "Cumulative Burn Area"
)

Map.addLayerControl()
Map
