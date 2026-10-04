import time

print(f"Analyze called at {time.time()}")

from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS, cross_origin
from NS_runner import generate_burnt_area_report as run_ns
import time
from progress import progress_queue
from flask import send_from_directory

app = Flask(__name__)

CORS(app, resources={r"/*": {"origins": "*"}})

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/progress")
def progress():

    def generate():
        yield "data: READY\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream"
    )

    def generate():

        while True:

            if not progress_queue.empty():

                msg = progress_queue.get()

                yield f"data: {msg}\n\n"

                if msg == "DONE":
                    break

            time.sleep(0.2)

    return Response(
        generate(),
        mimetype="text/event-stream"
    )

@app.route("/api/get_dates")
@cross_origin()
def get_dates():

    print("Inside get_dates")

    district = request.args.get("district")
    state = request.args.get("state")
    season = request.args.get("season")
    year = int(request.args.get("year"))
    crop_mask = request.args.get("crop_mask")

    print(f"Fetching dates for {district}, {state}, {season}, {year}, {crop_mask}")

    data = run_ns(
    district=district,
    state=state,
    season=season,
    year=year,
    crop_mask=crop_mask,
    dates_only=True
    )

    return jsonify({
        "available_dates": data["available_dates"]
    })


@app.route("/api/analyze")
@cross_origin()
def analyze():

    district = request.args.get("district")
    state = request.args.get("state")
    year = int(request.args.get("year"))
    season = request.args.get("season")
    crop_mask = request.args.get("crop_mask")
    duration = request.args.get("duration")

    selected_date = request.args.get("selected_date")

    start_date = request.args.get("start_date")

    end_date = request.args.get("end_date")
    output_product = request.args.get("output_product")

    if not selected_date:
      selected_date = None

    # Run only when API is called
    try:

        ns_data = run_ns(
            district=district,
            state=state,
            season=season,
            year=year,
            crop_mask=crop_mask,
            duration=duration,
            selected_date=selected_date,
            start_date=start_date,
            end_date=end_date,
            output_product=output_product
        )

    except Exception as e:

        print("\n========== GEE PROCESSING FAILED ==========")
        print(type(e).__name__)
        print(str(e))
        print("===========================================\n")

        return jsonify({

            "status": "error",

            "message": str(e),

            "offer_export": (
                "User memory limit exceeded" in str(e)
                or "Computation timed out" in str(e)
                or "Too many pixels" in str(e)
                or "Computation exceeded" in str(e)
            )

        }), 500
    
    if ns_data.get("status") == "error":

        return jsonify(ns_data), 500
        
    print("\n========== NS DATA ==========")

    for k, v in ns_data.items():
        print(f"{k:20s}: {v}")

    print("=============================\n")
    print("\n========== REQUEST RECEIVED ==========")
    print("State      :", state)
    print("District   :", district)
    print("Year       :", year)
    print("Season     :", season)
    print("Duration   :", duration)
    print("Start Date :", start_date)
    print("End Date   :", end_date)
    print("Selected   :", selected_date)
    print("Crop mask  :", crop_mask)
    print("======================================\n")

    response_data = {
        "district": district,
        "state": state,
        "year": year,
        "season": season,
        "single_date": ns_data["single_date"],
        "available_dates": ns_data["available_dates"],
        "avg_cloud": ns_data["avg_cloud"],
        "burnt_area": ns_data["burnt_area"],
        "tile_url": ns_data["tile_url"],
        "png_url": ns_data["png_url"],
        "boundary_url": ns_data["boundary_url"]
    }

    response_data["message"] = None

    if ns_data["csv_export"] and ns_data["tiff_export"]:

        response_data["message"] = (
            "CSV and GeoTIFF export tasks have been started successfully."
        )

    elif ns_data["csv_export"]:

        response_data["message"] = (
            "CSV export task has been started successfully."
        )

    elif ns_data["tiff_export"]:

        response_data["message"] = (
            "GeoTIFF export task has been started successfully."
        )

    print("\n========== JSON RESPONSE ==========")

    for k, v in response_data.items():
        print(f"{k:20s}: {v}")

    print("===================================\n")

    return jsonify(response_data)

# ADD HERE
@app.route("/test")
def test():
    return jsonify({"message": "CORS Test"})

@app.route("/outputs/<path:filename>")
def outputs(filename):
    return send_from_directory(
        "Backend/outputs",
        filename
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)