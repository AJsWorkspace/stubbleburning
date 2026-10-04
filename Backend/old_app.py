from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS, cross_origin
from fi_runner import generate_burnt_area_report as run_fi
from ku_runner import generate_burnt_area_report as run_ku
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
    season = request.args.get("season")
    year = int(request.args.get("year"))

    print(district, season, year)

    if district == "Firozpur":

        print("Calling FI runner")

        data = run_fi(
            state="Firozpur",
            season=season,
            year=year,
            dates_only=True
        )

    elif district == "Kurukshetra":

        print("Calling KU runner")

        data = run_ku(
            state="Kurukshetra",
            season=season,
            year=year,
            dates_only=True
        )

    elif district == "National":

        print("Calling National runner")

        data = run_ns(
            season=season,
            year=year,
            dates_only=True
        )

    else:

        return jsonify({
            "error": "Invalid AOI"
        }), 400

    print("Runner finished")

    return jsonify({
        "available_dates": data["available_dates"]
    })


@app.route("/api/firozpur")
@cross_origin()
def firozpur():

    year = request.args.get("year")
    season = request.args.get("season")
    duration = request.args.get("duration")

    selected_date = request.args.get("selected_date")

    start_date = request.args.get("start_date")

    end_date = request.args.get("end_date")

    crop_mask = request.args.get("crop_mask", "agriculture")

    if not selected_date:
      selected_date = None

      # Run only when API is called
    fi_data = run_fi(
        state="Firozpur",
        season=season,
        year=year,
        duration=duration,
        selected_date=selected_date,
        start_date=start_date,
        end_date=end_date,
        crop_mask=crop_mask
)

    return jsonify({
        "district": "Firozpur",
        "state": "Punjab",
        "year": year,
        "season": season,
        "latest_date": fi_data["latest_date"],
        "available_dates": fi_data["available_dates"],
        "avg_cloud": fi_data["avg_cloud"],
        "burnt_area": fi_data["burnt_area"],
        "tile_url": fi_data["tile_url"],
        "cumulative_tile_url": fi_data["cumulative_tile_url"],
        "png_url": fi_data["png_url"],
        "cumulative_png_url": fi_data["cumulative_png_url"],
        "boundary_url": fi_data["boundary_url"]
    })



@app.route("/api/kurukshetra")
@cross_origin()
def kurukshetra():

    year = int(request.args.get("year"))
    season = request.args.get("season")
    duration = request.args.get("duration")

    selected_date = request.args.get("selected_date")

    start_date = request.args.get("start_date")

    end_date = request.args.get("end_date")

    crop_mask = request.args.get("crop_mask", "agriculture")

    # Run only when API is called
    ku_data = run_ku(
      state="Kurukshetra",
      season=season,
      year=year,
      duration=duration,
      selected_date=selected_date,
      start_date=start_date,
      end_date=end_date,
      crop_mask=crop_mask
)

    return jsonify({
        "district": "Kurukshetra",
        "state": "Haryana",
        "year": year,
        "season": season,
        "latest_date": ku_data["latest_date"],
        "available_dates": ku_data["available_dates"],
        "avg_cloud": ku_data["avg_cloud"],
        "burnt_area": ku_data["burnt_area"],
        "tile_url": ku_data["tile_url"],
        "cumulative_tile_url": ku_data["cumulative_tile_url"],
        "png_url": ku_data["png_url"],
        "cumulative_png_url": ku_data["cumulative_png_url"],
        "boundary_url": ku_data["boundary_url"]
    })


@app.route("/api/national")
@cross_origin()
def national():

    district = request.args.get("district")
    state = request.args.get("state")
    year = request.args.get("year")
    season = request.args.get("season")
    duration = request.args.get("duration")

    selected_date = request.args.get("selected_date")

    start_date = request.args.get("start_date")

    end_date = request.args.get("end_date")

    crop_mask = request.args.get("crop_mask", "agriculture")

    if not selected_date:
      selected_date = None

      # Run only when API is called
    ns_data = run_ns(
        district=district,
        state=state,
        season=season,
        year=year,
        duration=duration,
        selected_date=selected_date,
        start_date=start_date,
        end_date=end_date,
        crop_mask=crop_mask
)

    return jsonify({
        "district": district,
        "state": state,
        "year": year,
        "season": season,
        "latest_date": ns_data["latest_date"], ## remove 
        "available_dates": ns_data["available_dates"], ## this parameter will change 
        "avg_cloud": ns_data["avg_cloud"],
        "burnt_area": ns_data["burnt_area"],
        "tile_url": ns_data["tile_url"],
        "cumulative_tile_url": ns_data["cumulative_tile_url"],
        "png_url": ns_data["png_url"],
        "cumulative_png_url": ns_data["cumulative_png_url"],
        "boundary_url": ns_data["boundary_url"]
    })

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