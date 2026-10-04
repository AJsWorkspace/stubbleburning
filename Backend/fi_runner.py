import runpy

def generate_burnt_area_report(
    state,
    season,
    year,
    duration=None,
    dates_only=False,
    selected_date=None,
    start_date=None,
    end_date=None,
    crop_mask="agriculture"
):
    variables = {

    "state": state,
    "season": season,
    "year": year,

    "duration": duration,

    "dates_only": dates_only,

    "selected_date": selected_date,

    "start_date": start_date,

    "end_date": end_date,

    "crop_mask": crop_mask

}

    try:

        result = runpy.run_path(
            "Backend/copy_of_ba_fi.py",
            init_globals=variables
        )

        return result["result_data"]

    except SystemExit as e:

        return e.code