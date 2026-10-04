import pandas as pd

# =========================================================
# BUILD PROCESSING GROUPS
# =========================================================

def build_processing_groups(
    metadata_df,
    aoi_name,
    season,
    year
):

    print("\n========================================")
    print("FILTERING METADATA")
    print("========================================")

    # -----------------------------------------------------
    # Filter metadata for selected AOI / Season / Year
    # -----------------------------------------------------

    metadata = metadata_df[

        (metadata_df["AOI"] == aoi_name) &
        (metadata_df["Season"] == season) &
        (metadata_df["Year"] == year)

    ].copy()

    print("AOI    :", aoi_name)
    print("Season :", season)
    print("Year   :", year)
    print("Rows   :", len(metadata))

    """print("\nMetadata columns:")
    print(metadata.columns.tolist())

    print("\nUnique dates in metadata:")
    print(metadata["Date"].nunique())

    print("\nFirst few rows:")
    print(
     metadata[
          [
              "Date",
               "Tile_ID",
               "AOI_Coverage_Pct",
              "Avg_Cloud_Pct"
            ]
        ].head(10)
    )"""

    if metadata.empty:
        print("\nNo metadata found for selected AOI / Season / Year.")
        return [], "tile_count"

    metadata["Date"] = pd.to_datetime(
        metadata["Date"],
        dayfirst=False
    )

    metadata = metadata.sort_values(
        "Date",
        ascending=False
    )

    #print(metadata["Date"].dtype)
    #print(metadata["Date"].head())

    # =====================================================
    # AOI-SPECIFIC PROCESSING CONFIGURATION
    # =====================================================

    AOI_CONFIG = {

        "Haryana": {

            "base_tile_count": 8,

            "ignore_tile_count": 2

        },

        "Punjab": {

            "base_tile_count": 6,

            "ignore_tile_count": 2

        },

        "Ludhiana": {

            "base_tile_count": 4,

            "ignore_tile_count": 2

        }

    }

    # =====================================================
    # GET AOI-SPECIFIC CONFIGURATION
    # =====================================================

    if aoi_name not in AOI_CONFIG:

        raise ValueError(

            f"Unsupported AOI: {aoi_name}. "

            f"Available AOIs: "
            f"{list(AOI_CONFIG.keys())}"

        )

    aoi_config = AOI_CONFIG[aoi_name]

    BASE_TILE_COUNT = (
        aoi_config["base_tile_count"]
    )

    IGNORE_TILE_COUNT = (
        aoi_config["ignore_tile_count"]
    )

    print("\n" + "=" * 70)
    print("AOI-SPECIFIC PROCESSING CONFIGURATION")
    print("=" * 70)

    print(
        "AOI                :",
        aoi_name
    )

    print(
        "Base tile count    :",
        BASE_TILE_COUNT
    )

    print(
        "Ignore tile count  :",
        IGNORE_TILE_COUNT
    )

    print("=" * 70)



    tile_count_df = (
        metadata
        .groupby("Date")["Tile_ID"]
        .nunique()
        .reset_index(name="Tile_Count")
    )

    # Newest first

    tile_count_df = tile_count_df.sort_values(
        "Date",
        ascending=False
    )

    #print("\nTile count check")

    tile_counts = {}

    for _, row in tile_count_df.iterrows():

        d = row["Date"]
        n = row["Tile_Count"]

        tile_counts[d] = n

        #print(d.strftime("%d-%m-%Y"), ":", n)

    # =====================================================
    # BUILD DATE-LEVEL INFORMATION
    # =====================================================

    date_info = []

    for _, row in tile_count_df.iterrows():

        date = row["Date"]

        tile_count = int(
            row["Tile_Count"]
        )

        date_metadata = metadata[
            metadata["Date"] == date
        ]

        avg_cloud = date_metadata[
            "Avg_Cloud_Pct"
        ].mean()

        date_info.append({

            "date": date,

            "tile_count": tile_count,

            "avg_cloud": avg_cloud

        })

    # Ensure newest first

    date_info = sorted(

        date_info,

        key=lambda x: x["date"],

        reverse=True

    )

    # =====================================================
    # CLASSIFY DATES
    # =====================================================

    ignored_dates = []

    category_A = []

    category_B = []

    category_C = []

    for d in date_info:

        tc = d["tile_count"]

        # -------------------------------------------------
        # IGNORE SMALL PARTIAL COVERAGE
        # -------------------------------------------------

        if tc <= IGNORE_TILE_COUNT:

            ignored_dates.append(d)

            continue

        # -------------------------------------------------
        # CATEGORY A
        #
        # Base AOI footprint
        # OR 7 tiles
        # OR >21 tiles
        # -------------------------------------------------

        if (
            tc == BASE_TILE_COUNT
            or tc == 7
            or tc > 21
        ):

            category_A.append(d)

        # -------------------------------------------------
        # CATEGORY B
        #
        # Larger intermediate footprint
        # OR >21 tiles
        # -------------------------------------------------

        if (
            (tc > BASE_TILE_COUNT and tc <= 21)
            or tc > 21
        ):

            category_B.append(d)

        # -------------------------------------------------
        # CATEGORY C
        #
        # Large AOI workflow
        # -------------------------------------------------

        if tc > 21:

            category_C.append(d)

    # ======================================================
    # DEBUG SUMMARY
    # ======================================================

    print("\n" + "=" * 70)
    print("DATE CATEGORISATION")
    print("=" * 70)

    print(
        "Base tile count   :",
        BASE_TILE_COUNT
    )

    print(
        "Ignore tile count :",
        IGNORE_TILE_COUNT
    )

    print(
        "Total unique dates:",
        len(date_info)
    )

    print(
        "Ignored dates     :",
        len(ignored_dates)
    )

    print(
        "Category A dates  :",
        len(category_A)
    )

    print(
        "Category B dates  :",
        len(category_B)
    )

    print(
        "Category C dates  :",
        len(category_C)
    )


    # ======================================================
    # BUILD PROCESSING GROUPS
    # ======================================================

    processing_groups = []


    # ======================================================
    # CATEGORY A
    # ======================================================

    dates_A = [
        d["date"]
        for d in category_A
    ]

    metadata_A = metadata[
        metadata["Date"].isin(dates_A)
    ].copy()

    processing_groups.append({

        "group_name":
            "Category_A",

        "method":
            "tile_count",

        "metadata":
            metadata_A,

        "category":
            "A",

        "reference_lookup":
            None

    })


    # ======================================================
    # CATEGORY B
    # ======================================================

    dates_B = [
        d["date"]
        for d in category_B
    ]

    metadata_B = metadata[
        metadata["Date"].isin(dates_B)
    ].copy()

    processing_groups.append({

        "group_name":
            "Category_B",

        "method":
            "tile_count",

        "metadata":
            metadata_B,

        "category":
            "B",

        "reference_lookup":
            None

    })


    # ======================================================
    # CATEGORY C
    # ======================================================

    dates_C = [
        d["date"]
        for d in category_C
    ]

    metadata_C = metadata[
        metadata["Date"].isin(dates_C)
    ].copy()

    processing_groups.append({

        "group_name":
            "Category_C",

        "method":
            "tile_count",

        "metadata":
            metadata_C,

        "category":
            "C",

        "reference_lookup":
            None

    })


    # ======================================================
    # GROUP SUMMARY
    # ======================================================

    print("\n" + "=" * 70)
    print("PROCESSING GROUPS")
    print("=" * 70)

    for group in processing_groups:

        print(
            group["group_name"],
            "->",
            len(group["metadata"]),
            "rows"
        )


    # ======================================================
    # RETURN
    # ======================================================

    return processing_groups