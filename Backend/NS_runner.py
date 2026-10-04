import runpy

def generate_burnt_area_report(
    district,
    state,
    season,
    year,
    crop_mask,
    output_product=None,
    duration=None,
    dates_only=False,
    selected_date=None,
    start_date=None,
    end_date=None
    
):
    print("\n========== NS RUNNER ==========")
    print("Duration      :", duration)
    print("Start Date    :", start_date)
    print("End Date      :", end_date)
    print("Selected Date :", selected_date)
    print("Crop Mask     :", crop_mask)
    print("================================\n")

    try:

        result = runpy.run_path(
    "Backend/national_scale.py",
    init_globals={
        "district": district,
        "state": state,
        "season": season,
        "year": year,
        "duration": duration,
        "selected_date": selected_date,
        "start_date": start_date,
        "end_date": end_date,
        "crop_mask": crop_mask,
        "dates_only": dates_only,
        "output_product": output_product
    }
)

        return result["result_data"]

    #except Exception as e:

        #print(e)

        #raise

    except SystemExit as e:

        return e.code