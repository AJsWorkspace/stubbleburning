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
start_date = globals().get("start_date")
end_date = globals().get("end_date")
#Authenticate and initialize Earth Engine
service_account = "stubbleburning-dashboard@stubbleburning-dashboard.iam.gserviceaccount.com"

credentials = ee.ServiceAccountCredentials(
    service_account,
    "/home/stubbleburning_asag_nrsc/Stubble_burning_RESTAPI/Backend/stubbleburning-dashboard-cc9dc95beae3.json"
)

ee.Initialize(
    credentials,
    project="stubbleburning-dashboard"
)

#Mention state and year
# Parameters received from NS_runner.py
district = globals().get("district")
state = globals().get("state")
season = globals().get("season")
year = globals().get("year")
crop_mask_option = globals().get("crop_mask")
duration = globals().get("duration")
output_product = globals().get("output_product")


print("\n========== NATIONAL SCALE ==========")
print("Duration      :", duration)
print("Start Date    :", start_date)
print("End Date      :", end_date)
print("Selected Date :", selected_date)
print("Crop Mask received:", crop_mask_option)
print("Output Product :", output_product)
print("====================================\n")

if district in [None, "", "All Districts"]:
    aoi_name = state
else:
    aoi_name = district

if season == "Rabi":

    # Burnt area mapping period
    season_start_date = f"{year}-03-16"
    season_end_date   = f"{year}-06-01"

    # Maximum NDVI season (previous Dec -> current Feb)
    start_ndvi = f"{year-1}-12-01"
    end_ndvi   = f"{year}-02-28"

    # MIRBI season
    start_mirbi = f"{year}-03-01"
    end_mirbi   = season_end_date

elif season == "Kharif":

    # Burnt area mapping period
    season_start_date = f"{year}-08-16"
    season_end_date   = f"{year}-12-01"

    # Maximum NDVI season
    start_ndvi = f"{year}-06-01"
    end_ndvi   = f"{year}-09-30"

    # MIRBI season
    start_mirbi = f"{year}-09-01"
    end_mirbi   = season_end_date

else:
    raise ValueError("season must be either 'Rabi' or 'Kharif'")

#AOI assets 
AOI_ASSETS = {

    "Punjab":
        "projects/stubbleburning-api/assets/State_boundary/PUNJAB",

    "Ludhiana":
        "projects/stubbleburning-api/assets/PUNJAB/LUDHIANA",

    "Haryana":
        "projects/stubbleburning-api/assets/State_boundary/HARYANA",

    "Firozpur":
        "projects/.../Firozpur",

    "Kurukshetra":
        "projects/.../Kurukshetra",
    
    "Delhi":
        "projects/stubbleburning-api/assets/State_boundary/DELHI"

}
if aoi_name not in AOI_ASSETS:
    raise ValueError(f"AOI '{aoi_name}' not found")

aoi = ee.FeatureCollection(AOI_ASSETS[aoi_name])
# =========================================================
# CROP MASK OPTION
# =========================================================
#
# Options:
#   Agriculture Mask
#   Wheat Mask
#   Rice Mask
#   Sugarcane Mask
# =========================================================

#crop_mask_option = "Agriculture Mask"

#define esa worldcover agrimask
worldCover = ee.ImageCollection('ESA/WorldCover/v100').first().clip(aoi)
agriMask1  = worldCover.eq(40)

#lulc mask assets
lulcMask = ee.Image('projects/stubbleburning-2025/assets/india_lulc_gcs84_agri')
agriMask2 = lulcMask.eq(1).clip(aoi)

# =========================================================
# CROP SPECIFIC MASK
# =========================================================
"""
update later
WHEAT_MASKS = {

    "Punjab":
        "...",

    "Haryana":
        "...",

}
cropMask = ee.Image(
    WHEAT_MASKS[state]
).clip(aoi)
"""
cropMask = ee.Image.constant(1).clip(aoi)

if crop_mask_option == "Agriculture Mask":

    # No additional crop mask
    pass

elif crop_mask_option == "Wheat Mask":

    if aoi_name == "Punjab":

        cropMask = ee.Image(
            "projects/stubbleburning-2025/assets/wheat_mask_pb_final_2026_10m_GCS84"
        ).clip(aoi)

    else:

        raise ValueError(
            "Wheat mask not available for selected AOI."
        )

elif crop_mask_option == "Rice Mask":

    if aoi_name == "Punjab":

        cropMask = ee.Image(
            "projects/ee-stubbleburning2024/assets/paddymask_pb"
        ).clip(aoi)

    else:

        raise ValueError(
            "Rice mask not available for selected AOI."
        )

elif crop_mask_option == "Sugarcane Mask":

    if aoi_name == "Punjab":

        cropMask = ee.Image(
            "YOUR_SUGARCANE_MASK_ASSET"
        ).clip(aoi)

    else:

        raise ValueError(
            "Sugarcane mask not available for selected AOI."
        )

else:

    raise ValueError(
        "Invalid Crop Mask option."
    )

def filter_bands(image):

  # Keep only the required spectral bands
    bands = (
        image
        .select(['B4', 'B7', 'B8', 'B11', 'B12', 'SCL', 'QA60'])
    )

    return (
        bands.copyProperties(image, image.propertyNames())
    )
# Call the sentinel collection
collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(aoi)
      .filterDate(start_ndvi, end_mirbi)
      .map(filter_bands))

# =====================================================
# Season Maximum NDVI (20 m default projection)
# =====================================================

collection_NDVI = collection.filterDate(start_ndvi, end_ndvi)

# Native Sentinel-2 20 m projection
reference_proj = (
    ee.Image(collection_NDVI.first())
    .select('B11')
    .projection()
)

def add_ndvi(image):

    ndvi = (
        image.normalizedDifference(['B8', 'B4'])
        .rename('NDVI')
        .setDefaultProjection(reference_proj)
    )

    return image.addBands(ndvi)

ndvi_collection = collection_NDVI.map(add_ndvi).select('NDVI')

season_max_ndvi = (
    ndvi_collection
    .max()
    .setDefaultProjection(reference_proj)
    .clip(aoi)
)

season_max_ndvi_th = (
    season_max_ndvi
    .gt(0.3)
    .rename('NDVI_Season')
    .setDefaultProjection(reference_proj)
)

# =====================================================
# Season Minimum MIRBI (20 m default projection)
# =====================================================

collection_MIRBI = collection.filterDate(start_mirbi, end_mirbi)

def add_MIRBI(image):

    mirbi = (
        image.expression(
            '(10 * SWIR2 - 9.8 * SWIR1 + 2)',
            {
                'SWIR1': image.select('B11'),
                'SWIR2': image.select('B12')
            }
        )
        .rename('MIRBI')
        .setDefaultProjection(reference_proj)
    )

    return image.addBands(mirbi)

mirbi_collection = collection_MIRBI.map(add_MIRBI).select('MIRBI')

mirbi_season = (
    mirbi_collection
    .reduce(ee.Reducer.min())
    .rename('MIRBI_season_min')
    .setDefaultProjection(reference_proj)
    .clip(aoi)
)

MIRBI_Season_th = (
    mirbi_season
    .gt(-3000)
    .rename('MIRBI_Season')
    .setDefaultProjection(reference_proj)
)

agriMask2 = agriMask2.setDefaultProjection(reference_proj)
agriMask1 = agriMask1.setDefaultProjection(reference_proj)
cropMask = cropMask.setDefaultProjection(reference_proj)

def clip_image(image):
    return image.clip(aoi)

def cloud_pct(image):
  cloud_pct = ee.Number(image.get('CLOUDY_PIXEL_PERCENTAGE')).float()
  return image.set('cloud_pct', cloud_pct)

collection_dates = (collection
                      .filterDate(season_start_date, season_end_date)
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

print("Total unique acquisition dates:", len(distinct_dates_list))
print("\nAvailable dates:")
for d in distinct_dates_list:
    print(d)

## load metadata and filter dates and tiles
from metadata import authenticate_drive, load_metadata

drive_service = authenticate_drive()
metadata_df = load_metadata()
img = ee.Image(collection_dates.first())

#print(img.propertyNames().getInfo())
# =========================================================
# Extract metadata for all tiles of one acquisition date
# =========================================================

def extract_tile_metadata(date_str):

    daily = collection_dates.filter(
        ee.Filter.eq("date_from_index", date_str)
    )

    tile_metadata_fc = daily.map(
        lambda img: ee.Feature(
            None,
            {
                "Date": img.get("date_from_index"),
                "Tile_ID": img.get("MGRS_TILE"),
                "Image_ID": img.get("system:index"),
                "Avg_Cloud_Pct": img.get("cloud_pct")
            }
        )
    )

    return tile_metadata_fc
fc = extract_tile_metadata(distinct_dates_list[0])
"""
print(fc.size().getInfo())

print(fc.first().getInfo())"""
#print(f"\nChecking {len(distinct_dates_list)} acquisition dates...\n")

# =========================================================
# Existing processed dates for current AOI / Season / Year
# =========================================================

existing_dates = set(

    metadata_df[
        (metadata_df["AOI"] == aoi_name) &
        (metadata_df["Season"] == season) &
        (metadata_df["Year"] == year)
    ]["Date"]

)

new_rows = []

# =========================================================
# LOOP THROUGH ACQUISITION DATES
# =========================================================

for date in distinct_dates_list:

    print(f"\nDate : {date}")

    # -------------------------------------------------
    # Skip entire date if already processed
    # -------------------------------------------------

    if date in existing_dates:

        #print("  ✓ Cached - skipping date")

        continue

    #print("  + Processing")

    # -------------------------------------------------
    # Get tile metadata
    # -------------------------------------------------

    tile_fc = extract_tile_metadata(date)

    tiles = tile_fc.getInfo()["features"]

    # -------------------------------------------------
    # Process every tile
    # -------------------------------------------------

    for tile in tiles:

        props = tile["properties"]

        tile_id = props["Tile_ID"]
        image_id = props["Image_ID"]
        cloud_pct = props["Avg_Cloud_Pct"]

        #print(f"    + {tile_id}")

        # -------------------------------------------------
        # Get image
        # -------------------------------------------------

        image = collection.filter(
            ee.Filter.eq("system:index", image_id)
        ).first()

        # -------------------------------------------------
        # AOI Coverage (%)
        # -------------------------------------------------

        aoi_geom = aoi.geometry()
        aoi_area = aoi_geom.area()

        footprint = image.geometry()

        coverage = (
            footprint
            .intersection(aoi_geom, ee.ErrorMargin(1))
            .area()
            .divide(aoi_area)
            .multiply(100)
            .getInfo()
        )

        coverage = round(coverage, 2)

        system_footprint = image.get("system:footprint").getInfo()

        new_rows.append([

            aoi_name,
            season,
            year,
            date,
            tile_id,
            image_id,
            round(cloud_pct, 2),
            coverage,
            system_footprint

        ])

import pandas as pd
# =========================================================
# Append all new rows together
# =========================================================

if new_rows:

    metadata_df = pd.concat(

        [
            metadata_df,
            pd.DataFrame(
                new_rows,
                columns=metadata_df.columns
            )
        ],

        ignore_index=True

    )

print(f"\nNew rows added : {len(new_rows)}")

metadata_df.sort_values(

    ["AOI",
     "Season",
     "Year",
     "Date",
     "Tile_ID"],

    inplace=True

)

from googleapiclient.http import MediaIoBaseUpload
import io

# =========================================================
# SAVE UPDATED METADATA TO GOOGLE DRIVE
# =========================================================

csv_buffer = io.BytesIO()

metadata_df.to_csv(
    csv_buffer,
    index=False
)

csv_buffer.seek(0)

results = drive_service.files().list(
    q="name='metadata.csv' and trashed=false",
    fields="files(id,name)"
).execute()

files = results.get("files", [])

if files:

    file_id = files[0]["id"]

    media = MediaIoBaseUpload(
        csv_buffer,
        mimetype="text/csv",
        resumable=True
    )

    drive_service.files().update(
        fileId=file_id,
        media_body=media
    ).execute()

    print("✓ metadata.csv updated on Google Drive.")

else:

    print("metadata.csv not found on Drive.")

print("\n===================================")
print(f"New rows added : {new_rows}")
print(f"Total records  : {len(metadata_df)}")
print("Metadata CSV updated successfully.")
print("===================================")

from filterdates import build_processing_groups

# =========================================================
# BUILD PROCESSING GROUPS
# =========================================================

processing_groups = build_processing_groups(
    metadata_df=metadata_df,
    aoi_name=aoi_name,
    season=season,
    year=year
)

#print(f"\nTotal Processing Groups : {len(processing_groups)}")

# ==========================================================
# BUILD SEASON PROCESSING WINDOWS
# ==========================================================

processing_batches = []

for group in processing_groups:

    #print("\n" + "="*70)
    #print("PROCESSING GROUP :", group["group_name"])
    #print("="*70)

    group_metadata  = group["metadata"].copy()

    # ------------------------------------------------------
    # Remove cloudy tiles
    # ------------------------------------------------------

    metadata_cloud = group_metadata [
        group_metadata ["Avg_Cloud_Pct"] < 50
    ].copy()

    candidate_dates = sorted(
        metadata_cloud["Date"].unique(),
        reverse=True
    )

    """print("\nGenerating season windows...")

    print("Rows before cloud filter :", len(group_metadata))
    print("Rows after cloud filter  :", len(metadata_cloud))
    print("Candidate dates          :", len(candidate_dates))

    print("Candidate D0 dates:")

    for d in candidate_dates:
        print(d.strftime("%d-%m-%Y"))"""

    # ==========================================================
    # LOOP THROUGH EVERY POSSIBLE D0
    # ==========================================================

    for single_date in candidate_dates:

        #print("\n" + "-" * 70)
        #print("Evaluating D0 :", single_date.strftime("%d-%m-%Y"))

        # ------------------------------------------------------
        # Keep only dates up to current D0
        # ------------------------------------------------------

        metadata_current = metadata_cloud[
            metadata_cloud["Date"] <= single_date
        ].copy()

        if metadata_current.empty:
            continue

        latest_tiles = metadata_current[
            metadata_current["Date"] == single_date
        ].copy()

        if latest_tiles.empty:
            continue

        """print(
            "Tiles available for D0:",
            len(latest_tiles)
        )

        print(
            sorted(latest_tiles["Tile_ID"].tolist())
        )"""

        # ======================================================
        # SEQUENTIAL TILE SEARCH
        # ======================================================

        selected_tiles = []

        for _, latest_row in latest_tiles.iterrows():

            tile = latest_row["Tile_ID"]

            #print("\n" + "-" * 60)
            #print("Processing Tile:", tile)

            tile_rows = metadata_current[
                metadata_current["Tile_ID"] == tile
            ].sort_values(
                "Date",
                ascending=False
            )

            chosen = [latest_row]

            """print(
                latest_row["Date"].strftime("%d-%m-%Y"),
                "| Latest"
            )"""

            for _, row in tile_rows.iterrows():

                if row["Date"] >= single_date:
                    continue

                chosen.append(row)

                if len(chosen) == 3:
                    break

            # ----------------------------------------------
            # Skip incomplete tile sequence
            # ----------------------------------------------

            if len(chosen) == 3:

                selected_tiles.extend(chosen)

            else:

                print("Skipped (less than 3 dates)")

        # ======================================================
        # BUILD DATAFRAME
        # ======================================================

        if len(selected_tiles) == 0:
            continue

        selected_tiles_df = (
            pd.DataFrame(selected_tiles)
            .sort_values(
                ["Date", "Tile_ID"],
                ascending=[False, True]
            )
        )

        # ------------------------------------------------------
        # Ensure every tile has D0 D1 D2
        # ------------------------------------------------------

        tile_counts = (
            selected_tiles_df
            .groupby("Tile_ID")
            .size()
        )

        if (tile_counts < 3).any():

            #print("\nSkipping batch (Incomplete tile sequences)")
            continue

        # ======================================================
        # STORE PROCESSING BATCH
        # ======================================================

        processing_batches.append({

            "group_name":
                group["group_name"],

            "category":
                group.get("category"),

            "batch_name":
                single_date.strftime("%Y-%m-%d"),

            "selected_tiles":
                selected_tiles_df.copy(),

            "single_date": single_date,

            "metadata": metadata_current.copy()

        })

        """# ======================================================
        # DEBUG
        # ======================================================

        print("\n" + "=" * 70)
        print("BATCH :", single_date.strftime("%d-%m-%Y"))
        print("=" * 70)

        print(
            selected_tiles_df[
                [
                    "Date",
                    "Tile_ID",
                    "Avg_Cloud_Pct",
                    "AOI_Coverage_Pct"
                ]
            ]
        )"""

# ==========================================================
# SUMMARY
# ==========================================================
"""
print("\n" + "=" * 70)
print("TOTAL PROCESSING BATCHES")
print("=" * 70)

print(len(processing_batches))

for batch in processing_batches:

    print(
        batch["group_name"],
        "->",
        batch["batch_name"]
    )
"""
# ==========================================================
# AVAILABLE PROCESSING DATES
# ==========================================================

available_dates = sorted(
    {batch["batch_name"] for batch in processing_batches},
    reverse=True
)

print("\nAvailable Processing Dates:")

for d in available_dates:
    print(d)


# ==========================================================
# RETURN ONLY AVAILABLE DATES
# ==========================================================
if dates_only:

    result_data = {
        "available_dates": available_dates
    }

    raise SystemExit(result_data)

# ==========================================================
# FILTER PROCESSING BATCHES BASED ON USER SELECTION
# ==========================================================

if duration == "single_date":

    print("\nRunning Latest Observation")

    processing_batches = [

        batch

        for batch in processing_batches

        if batch["batch_name"] == selected_date

    ]

    print("Selected Date :", selected_date)
    print("Batches found :", len(processing_batches))


elif duration == "multi_date":

    print("\nRunning Cumulative Analysis")

    processing_batches = [

        batch

        for batch in processing_batches

        if start_date <= batch["batch_name"] <= end_date

    ]

    print("Start Date :", start_date)
    print("End Date   :", end_date)
    print("Batches found :", len(processing_batches))

# ==========================================================
# BUILD D0 / D1 / D2 FOR ALL PROCESSING BATCHES
# ==========================================================

for batch in processing_batches:

    selected_tiles_df = batch["selected_tiles"]

    # Initialise
    batch["D0"] = []
    batch["D1"] = []
    batch["D2"] = []

    # ------------------------------------------------------
    # Build D0/D1/D2 lists for every tile
    # ------------------------------------------------------

    for tile in sorted(selected_tiles_df["Tile_ID"].unique()):

        tile_rows = (
            selected_tiles_df[
                selected_tiles_df["Tile_ID"] == tile
            ]
            .sort_values(
                "Date",
                ascending=False
            )
            .reset_index(drop=True)
        )

        if len(tile_rows) != 3:
            continue

        batch["D0"].append({

            "date":
                tile_rows.loc[0, "Date"].strftime("%Y-%m-%d"),

            "tile":
                tile_rows.loc[0, "Tile_ID"],

            "image_id":
                tile_rows.loc[0, "Image_ID"]

        })

        batch["D1"].append({

            "date":
                tile_rows.loc[1, "Date"].strftime("%Y-%m-%d"),

            "tile":
                tile_rows.loc[1, "Tile_ID"],

            "image_id":
                tile_rows.loc[1, "Image_ID"]

        })

        batch["D2"].append({

            "date":
                tile_rows.loc[2, "Date"].strftime("%Y-%m-%d"),

            "tile":
                tile_rows.loc[2, "Tile_ID"],

            "image_id":
                tile_rows.loc[2, "Image_ID"]

        })

"""print("\nProcessing batches\n")

for batch in processing_batches:

    print("\n" + "=" * 70)
    print("Group :", batch["group_name"])
    print("Batch :", batch["batch_name"])
    print("=" * 70)

    for label in ["D0", "D1", "D2"]:

        print(f"\n{label}")

        for item in batch[label]:

            print(
                item["date"],
                item["tile"],
                item["image_id"]
            )"""

def preprocess_s2(image):

    # Required bands for cloud masking
    scl = image.select('SCL')
    qa = image.select('QA60')

    # QA60 bits
    cloud = qa.bitwiseAnd(1 << 10).neq(0)
    cirrus = qa.bitwiseAnd(1 << 11).neq(0)

    qa_cloud = cloud.Or(cirrus)

    # SCL cloud classes
    scl_invalid = (
        scl.eq(3)      # cloud shadow
        .Or(scl.eq(8))   # medium cloud
        .Or(scl.eq(9))   # high cloud
        .Or(scl.eq(10))  # cirrus
    )

    combined_cloud = (
        scl_invalid
        .Or(qa_cloud)
        .rename('cloud_mask')
    )

    # Cloud buffer
    cloud_buffer = combined_cloud.focal_max(
        radius=500,
        units='meters'
    )

    clear_mask = cloud_buffer.Not()

    # Keep only the required spectral bands
    bands = (
        image
        .select(['B4', 'B7', 'B8', 'B11', 'B12'])
        .updateMask(clear_mask)
        .divide(10000)
    )

    return (
        bands
        .addBands(combined_cloud)
        .copyProperties(image, image.propertyNames())
    )

collection_burnt = (collection_dates.map(preprocess_s2))

img = ee.Image(collection_burnt.first())

bands = img.bandNames().getInfo()

"""print("Band resolutions after masking:\n")

for band in bands:
    proj = img.select(band).projection()
    print(
        f"{band:10s}",
        "Scale:", proj.nominalScale().getInfo(), "m",
        "CRS:", proj.crs().getInfo()
    )"""

# =========================================================
# LOAD ALL IMAGES REQUIRED FOR ALL PROCESSING BATCHES
# =========================================================

required_pairs = set()

for batch in processing_batches:

    selected_tiles_df = batch["selected_tiles"]

    for _, row in selected_tiles_df.iterrows():

        required_pairs.add((
            row["Date"].strftime("%Y-%m-%d"),
            row["Tile_ID"]
        ))

"""print("\nUnique Date/Tile pairs required:",
      len(required_pairs))"""

# ---------------------------------------------------------
# Build EE filter
# ---------------------------------------------------------

filters = []

for date, tile in sorted(required_pairs):

    filters.append(

        ee.Filter.And(

            ee.Filter.eq("date_from_index", date),

            ee.Filter.eq("MGRS_TILE", tile)

        )

    )

pair_filter = ee.Filter.Or(*filters)

# ---------------------------------------------------------
# Load only required Sentinel-2 images
# ---------------------------------------------------------

collection_burnt = (
    collection_dates
    .filter(pair_filter)
    .map(preprocess_s2)
)

print("\nLoading required Sentinel-2 images...")

count = collection_burnt.size().getInfo()

print("Images loaded:", count)

"""# ---------------------------------------------------------
# Debug
# ---------------------------------------------------------

print("\nLoaded Date / Tile combinations:")

loaded = (
    collection_burnt
    .aggregate_array("date_from_index")
    .zip(
        collection_burnt.aggregate_array("MGRS_TILE")
    )
    .getInfo()
)

for d, t in loaded:
    print(d, t)"""

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
# BUILD MOSAIC FROM SELECTED TILES
# =========================================================

print("\nBuilding mosaics...\n")

def build_mosaic(image_records):

    filters = []

    for record in image_records:

        filters.append(

            ee.Filter.And(

                ee.Filter.eq(
                    "date_from_index",
                    record["date"]
                ),

                ee.Filter.eq(
                    "MGRS_TILE",
                    record["tile"]
                )

            )

        )

    mosaic = (

        collection_burnt

        .filter(
            ee.Filter.Or(*filters)
        )

        .mosaic()

        .setDefaultProjection(reference_proj)

        .clip(aoi)

    )

    return addIndices(mosaic)


"""# =========================================================
# DEBUG - VERIFY MOSAIC PROJECTIONS
# =========================================================

print("=" * 70)
print("CHECKING MOSAIC PROJECTIONS")
print("=" * 70)

img = build_mosaic(
    processing_batches[0]["D0"]
)

print("\n=== Mosaic + Indices Band Projections ===\n")

for band in img.bandNames().getInfo():

    proj = img.select(band).projection()

    print(
        f"{band:10s} | "
        f"CRS: {proj.crs().getInfo()} | "
        f"Scale: {proj.nominalScale().getInfo()} m"
    )"""



burn_image_list = []

# =========================================================
# PROCESS ALL BATCHES
# =========================================================

for batch in processing_batches:

    print("\n" + "=" * 70)
    print("PROCESSING GROUP :", batch["group_name"])
    print("RUNNING BATCH    :", batch["batch_name"])
    print("=" * 70)

    # -----------------------------------------------------
    # BUILD D0 / D1 / D2 MOSAICS
    # -----------------------------------------------------

    img_d0 = build_mosaic(batch["D0"])
    img_d1 = build_mosaic(batch["D1"])
    img_d2 = build_mosaic(batch["D2"])

    d0_auto = batch["batch_name"]

    """print("\n" + "=" * 70)
    print("RUNNING:", d0_auto)
    print("=" * 70)

    print("\nD0 Mosaic")
    for r in batch["D0"]:
       print(r["date"], r["tile"], r["image_id"])

    print("\nD1 Mosaic")
    for r in batch["D1"]:
        print(r["date"], r["tile"], r["image_id"])

    print("\nD2 Mosaic")
    for r in batch["D2"]:
       print(r["date"], r["tile"], r["image_id"])"""

    # -----------------------------------------------------
    # REQUIRED BANDS
    # -----------------------------------------------------

    Date_n2_MIRBI = (
        img_d2.select('MIRBI')
        .rename('Date_n2_MIRBI')
    )

    Date_n1_MIRBI = (
        img_d1.select('MIRBI')
        .rename('Date_n1_MIRBI')
    )

    Date_0_MIRBI = (
        img_d0.select('MIRBI')
        .rename('Date_0_MIRBI')
    )

    Date_0_NDVI = (
        img_d0.select('NDVI')
        .rename('Date_0_NDVI')
    )

    Date_0_NBR = (
        img_d0.select('NBR')
        .rename('Date_0_NBR')
    )

    Day_0_b7 = (
        img_d0.select('B7')
        .rename('Day_0_b7')
    )

    Day_0_b8 = (
        img_d0.select('B8')
        .rename('Day_0_b8')
    )

    # -----------------------------------------------------
    # DIFFERENCES
    # -----------------------------------------------------

    Diff_Date_0_Date_n1_MIRBI = (
        Date_0_MIRBI
        .subtract(Date_n1_MIRBI)
        .rename('Date_0_minus_Date_n1_MIRBI')
    )

    Diff_Date_0_Date_n2_MIRBI = (
        Date_0_MIRBI
        .subtract(Date_n2_MIRBI)
        .rename('Date_0_minus_Date_n2_MIRBI')
    )

    # -----------------------------------------------------
    # STACK
    # -----------------------------------------------------

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

    ]).clip(aoi)

    # -----------------------------------------------------
    # VARIABLES
    # -----------------------------------------------------

    d0_mirbi = ls.select('Date_0_MIRBI')
    d1_mirbi = ls.select('Date_n1_MIRBI')
    d2_mirbi = ls.select('Date_n2_MIRBI')

    d0_d1_diff = ls.select(
        'Date_0_minus_Date_n1_MIRBI'
    )

    d0_d2_diff = ls.select(
        'Date_0_minus_Date_n2_MIRBI'
    )

    d0_nbr = ls.select('Date_0_NBR')
    d0_ndvi = ls.select('Date_0_NDVI')

    d0_b7 = ls.select('Day_0_b7')
    d0_b8 = ls.select('Day_0_b8')

    classified = (
        ee.Image.constant(0)
        .toUint8()
        .setDefaultProjection(reference_proj)
    )

    if season == 'Rabi':

        # =====================================================
        # RABI CLASSIFICATION
        # =====================================================

        burn_class = (

            (
                d0_mirbi.gte(-4500)
                .And(d1_mirbi.lte(-7500))
                .And(d0_d1_diff.gte(4000))
                .And(d0_nbr.lte(0.05))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
                .And(d0_b7.lt(0.25))
                .And(d0_b8.lt(0.25))
            )

            .Or(
               d0_mirbi.gte(-1500)
                .And(d2_mirbi.lt(-5500))
                .And(d0_d2_diff.gte(5000))
                .And(d0_nbr.lte(0.05))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
                .And(d0_b7.lt(0.25))
                .And(d0_b8.lt(0.25))
            )

            .Or(
               d0_mirbi.gte(-4500)
                .And(d2_mirbi.lte(-8000))
                .And(d0_d2_diff.gte(4000))
                .And(d0_nbr.lte(0.05))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
                .And(d0_b7.lt(0.25))
                .And(d0_b8.lt(0.25))
            )

            .Or(
                d0_mirbi.gte(-2500)
                .And(d1_mirbi.gte(-2500))
                .And(d0_nbr.lte(0.05))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
                .And(d0_b7.lt(0.25))
                .And(d0_b8.lt(0.25))
            )

            .Or(
               d0_mirbi.gte(-1500)
                .And(d1_mirbi.lt(-5500))
                .And(d0_d1_diff.gte(5000))
                .And(d0_nbr.lte(0.05))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
                .And(d0_b7.lt(0.25))
                .And(d0_b8.lt(0.25))
            )

        ).And(MIRBI_Season_th.Not())

        classified = classified.where(burn_class, 1)
        classified = classified.where(d0_ndvi.gte(0.35), 2)
        classified = classified.where(d0_mirbi.lt(-7500), 3)

    elif season == 'Kharif':

        # =====================================================
        # KHARIF CLASSIFICATION
        # =====================================================

        burn_class = (

            (
                d0_mirbi.gte(-4500)
                .And(d1_mirbi.lte(-8000))
                .And(d0_d1_diff.gte(4000))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
            )

            .Or(
                d0_mirbi.gte(-4500)
                .And(d1_mirbi.lte(-7500))
                .And(d1_mirbi.gt(-8000))
                .And(d0_d1_diff.gte(4000))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
            )

            .Or(
                d0_mirbi.gte(-4500)
                .And(d2_mirbi.lte(-8000))
                .And(d0_d2_diff.gte(4000))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
            )

            .Or(
                d0_mirbi.gte(-2500)
                .And(d1_mirbi.gte(-2500))
                .And(d0_nbr.lt(0))
                .And(d0_ndvi.lte(0.25))
                .And(d0_ndvi.gt(0))
            )

        ).And(MIRBI_Season_th.Not())

        classified = classified.where(burn_class, 1)

        classified = classified.where(
            d0_ndvi.gte(0.35),
            2
        )

        harvest_class = (
            (
                d0_mirbi.lte(-8000)
                .And(d0_ndvi.lt(0.25))
            )
            .Or(
               d0_mirbi.lte(-5500)
               .And(d0_mirbi.gt(-8500))
            )
        )

        classified = classified.where(harvest_class, 3)

    else:
        raise ValueError(f"Unknown season: {season}")

    classified = classified.rename("Class").setDefaultProjection(reference_proj)

    # =====================================================
    # FINAL MASK
    # =====================================================

    final_mask = (
        agriMask1
        .And(agriMask2)
        .And(season_max_ndvi_th)
        .And(cropMask)
    )

    final_classified = classified.updateMask(final_mask).toUint8().setDefaultProjection(reference_proj)

    patch_size = final_classified.connectedPixelCount(
      maxSize=100,          # should be > threshold
      eightConnected=True   # 8-neighbour connectivity
    )

    """stats1 = classified.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi.geometry(),
        scale=20,
        maxPixels=1e13
    ).getInfo()
    print(stats1)
    stats2 = final_classified.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi.geometry(),
        scale=20,
        maxPixels=1e13
    ).getInfo()
    print(stats2)"""
    final_sieved = (
        final_classified
        .updateMask(patch_size.gte(10))
        .toUint8().setDefaultProjection(reference_proj)
    )
    """stats3 = final_classified.reduceRegion(
        reducer=ee.Reducer.minMax(),
        geometry=aoi.geometry(),
        scale=20,
        maxPixels=1e13
    ).getInfo()
    print(stats3)"""
    # final_sieved is your cleaned output
    #("Sieve completed: removed patches smaller than 10 pixels")
    #print("final sieved :", final_sieved.projection().getInfo())

    burn_binary = (final_sieved.eq(1).rename("Burn").toUint8().setDefaultProjection(reference_proj)
                    .set({
                        "date": d0_auto,
                        "system:index": d0_auto,
                        "AOI": aoi_name,
                        "Season": season,
                        "Year": year
                    }))

    #print("burn binary :", burn_binary.projection().getInfo())

    """# ----------------------------------------------------------
    # DEBUG
    # ----------------------------------------------------------

    print("\n" + "=" * 60)
    print("Adding Burn Image")
    print("=" * 60)

    print("Date   :", d0_auto)
    print("AOI    :", aoi_name)
    print("Season :", season)
    print("Year   :", year)

    print("\nImage Properties:")

    props = burn_binary.toDictionary().getInfo()

    for k, v in props.items():
        print(f"{k:15s}: {v}")"""

    burn_image_list.append({"date": d0_auto,"image": burn_binary})
    
    print("\nTotal burn images stored:", len(burn_image_list))

    burn_collection = ee.ImageCollection.fromImages(
        [item["image"] for item in burn_image_list]
    )

    """print(
        "Burn images:",
        burn_collection.size().getInfo()
    )"""
    
"""# ==========================================================
# DEBUG: FINAL SIEVED VALUE RANGE
# ==========================================================

stats = final_sieved.reduceRegion(
    reducer=ee.Reducer.minMax(),
    geometry=aoi.geometry(),
    scale=20,
    maxPixels=1e13
).getInfo()

print("\n========== FINAL SIEVED ==========")
print(stats)
print("==================================")"""

cumulative_burn = (
    burn_collection
        .max()
        .rename("Cumulative_BA")
        .toUint8().setDefaultProjection(reference_proj)
)


"""
# ==========================================================
# DEBUG: cumulative burn value range
# ==========================================================

stats = cumulative_burn.reduceRegion(
    reducer=ee.Reducer.minMax(),
    geometry=aoi.geometry(),
    scale=20,
    maxPixels=1e13
).getInfo()

print("\n========== FINAL SIEVED ==========")
print(stats)
print("==================================")
"""


# ==========================================================
# EXPORT IMAGE TO USE
# ==========================================================
if duration == "single_date":

    export_images = [

        {

            "date": selected_date,

            "image": final_sieved.eq(1)

        }

    ]

    export_name = f"{aoi_name}_{selected_date}"

else:

    export_images = burn_image_list
    
    export_name = f"{aoi_name}_{start_date}_{end_date}"

print("\nImages to Export :", len(export_images))

# ----------------------------------------------------------
# Optional CSV export
# ----------------------------------------------------------

if output_product in ["csv", "both"]:

    print("\n" + "=" * 60)
    print("CSV EXPORT")
    print("=" * 60)
    # ------------------------------------------------------
    # STATE EXPORT
    # ------------------------------------------------------
    if district == "All Districts":

        print("Export Mode : State")

        district_folders = {

            "Punjab":
                "projects/stubbleburning-api/assets/PUNJAB",

            "Haryana":
                "projects/stubbleburning-api/assets/HARYANA",

        }

        district_folder = district_folders[aoi_name]

        assets = ee.data.listAssets({
            "parent": district_folder
        })["assets"]


        print(f"Found {len(assets)} district assets.")

        for export in export_images:

            export_date = export["date"]

            burn_image = export["image"]

            print("\nProcessing :", export_date)

            features = []

            for asset in assets:

                asset_id = asset["name"]

                district_name = asset_id.split("/")[-1]

                district_fc = ee.FeatureCollection(asset_id)

                burnt_area = (

                    ee.Image.pixelArea()

                    .updateMask(burn_image)

                    .reduceRegion(

                        reducer=ee.Reducer.sum(),

                        geometry=district_fc.geometry(),

                        scale=20,

                        maxPixels=1e13,

                        bestEffort=True

                    )

                    .get("area")

                )

                feature = ee.Feature(

                    None,

                    {

                        "AOI": aoi_name,

                        "Date": export_date,

                        "District": district_name,

                        "Burnt_Area_ha":

                            ee.Number(

                                ee.Algorithms.If(

                                    burnt_area,

                                    burnt_area,

                                    0

                                )

                            ).divide(10000)

                    }

                )

                features.append(feature)

            export_fc = ee.FeatureCollection(features)

            task = ee.batch.Export.table.toDrive(

                collection=export_fc,

                description=f"{aoi_name}_{export_date}_Area",

                folder="Burnt_Area_Stats",

                fileNamePrefix=f"{aoi_name}_{export_date}_Area",

                fileFormat="CSV"

            )

            task.start()

            print("CSV Export Started :", export_date)

    elif district != "All Districts":

        print("Export Mode : District")

        for export in export_images:

            export_date = export["date"]

            burn_image = export["image"]

            burnt_area = (

                ee.Image.pixelArea()

                .updateMask(burn_image)

                .reduceRegion(

                    reducer=ee.Reducer.sum(),

                    geometry=aoi.geometry(),

                    scale=20,

                    maxPixels=1e13,

                    bestEffort=True

                )

                .get("area")

            )

            feature = ee.Feature(

                None,

                {

                    "AOI": aoi_name,

                    "District": district,

                    "Date": export_date,

                    "Burnt_Area_ha":

                        ee.Number(

                            ee.Algorithms.If(

                                burnt_area,

                                burnt_area,

                                0

                            )

                        ).divide(10000)

                }

            )

            export_fc = ee.FeatureCollection([feature])

            task = ee.batch.Export.table.toDrive(

                collection=export_fc,

                description=f"{district}_{export_date}_Area",

                folder="Burnt_Area_Stats",

                fileNamePrefix=f"{district}_{export_date}_Area",

                fileFormat="CSV"

            )

            task.start()

            print("CSV Export Started :", export_date)

# ==========================================================
# OPTIONAL TIFF EXPORT
# ==========================================================

if output_product in ["tiff", "both"]:

    print("\n" + "=" * 60)
    print("TIFF EXPORT")
    print("=" * 60)

    for export in export_images:

        export_date = export["date"]

        burn_image = export["image"]

        export_name = f"{aoi_name}_{export_date}"

        task = ee.batch.Export.image.toDrive(

            image=burn_image,

            description=export_name,

            folder="Burnt_Area_Maps",

            fileNamePrefix=export_name,

            region=aoi.geometry(),

            scale=20,

            maxPixels=1e13,

            fileFormat="GeoTIFF"

        )

        task.start()

        print("GeoTIFF Export Started :", export_name)

latest_output = final_sieved

#latest_output = ee.Image.constant(1).clip(aoi)
test_vis_params = {
    "palette": ["FF0000"]
}
# ==========================================================
# SELECT OUTPUT IMAGE
# ==========================================================

if duration == "single_date":

    output_image = latest_output
    single_date = selected_date

elif duration == "multi_date":

    output_image = cumulative_burn
    single_date = end_date

else:

    raise ValueError("Invalid duration.")

latest_vis = {
    "min": 0,
    "max": 3,
    "palette": [   
        "#808080",# Background
        "#ff0000",   # Burn
        "#00ff00",    # Crop
        "#ffff00"   # Harvest
    ]
}

cumulative_vis = {
    "min": 0,
    "max": 1,
    "palette": [
        "808080",
        "ff0000"
    ]
}

if duration == "single_date":

    vis = latest_vis

else:

    vis = cumulative_vis

map_id = output_image.getMapId(vis)

tile_url = map_id["tile_fetcher"].url_format

boundary = ee.Image().byte().paint(
    featureCollection=aoi,
    color=1,
    width=1
    )
boundary_map = boundary.getMapId({
    'palette': ['000000']
    })

boundary_url = boundary_map["tile_fetcher"].url_format

# ==========================================================
# SELECT OUTPUT IMAGE
# ==========================================================

if duration == "single_date":

    output_image = latest_output

    """vis_params = {
        "palette": ["FF0000"]
    }"""
    vis_params = {
        "min": 0,
        "max": 3,
        "palette": [
            "808080",   # Background"
            "8B0000",   # 1 = Burnt
            "00FF00",   # 2 = Crop
            "FFFF00"    # 3 = Harvest
        ]
    }

elif duration == "multi_date":

    output_image = cumulative_burn

    vis_params = cumulative_vis
    

else:

    raise ValueError("Invalid duration")

png_url = output_image.visualize(**vis_params).getThumbURL({
    "region": aoi.geometry(),
    "dimensions": 1500,
    "format": "png"
})

print("\n========== PNG DEBUG ==========")
print("Duration :", duration)
print("PNG URL  :", png_url)
print("===============================\n")


try:

    result_data = {

        "single_date": single_date,
        "available_dates": available_dates,
        "avg_cloud": None,
        "burnt_area": None,

        "tile_url": tile_url,

        "png_url": png_url,
        "boundary_url": boundary_url,
        "csv_export":
            output_product in ["csv", "both"],
        "tiff_export":
            output_product in ["tiff", "both"]
    }

    print("\n========== RESULT DATA ==========")

    for k, v in result_data.items():
        print(f"{k:20s}: {v}")

    print("=================================\n")

except Exception as e:

    msg = str(e)

    print("\n========== GEE ERROR ==========")
    print(msg)
    print("===============================\n")

    result_data = {

        "status": "error",

        "message": msg,

        "offer_export": (
            "User memory limit exceeded" in msg or
            "Computation timed out" in msg or
            "Too many pixels" in msg or
            "Computation exceeded" in msg
        )

    }
