from flask import Flask, render_template, request, jsonify
import joblib
import random
import requests

app = Flask(__name__)

# ---------------- LOAD MODEL ----------------

try:
    model = joblib.load("model/load_forecast_model.pkl")
except:
    model = None


# ---------------- WEATHER API KEY ----------------

API_KEY = "69fcbe36a4fc8cda45c92f1971f0e0b0"


# ---------------- LANDING PAGE ----------------

@app.route("/")
def landing():
    return render_template("landing.html")


# ---------------- INPUT PAGE ----------------

@app.route("/predict_page")
def predict_page():
    return render_template("predict.html")


# ---------------- PREDICTION ----------------

@app.route("/predict", methods=["POST"])
def predict():

    city = request.form.get("city")

    # Weather API request
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

    try:
        weather = requests.get(url).json()
        print(weather)

        temperature = weather["main"]["temp"]
        humidity = weather["main"]["humidity"]
        wind = weather["wind"]["speed"]
        clouds = weather["clouds"]["all"]

    except:
        return render_template(
        "dashboard.html",
        city=city,
        prediction=prediction,
        status=status,
        peak=peak,
        temperature=temperature
    )
        

    # ---------------- MODEL FEATURES ----------------

    features = [[
        temperature,
        humidity,
        clouds,
        wind,
        random.randint(0,23),     # hour
        random.randint(1,30),     # day
        random.randint(1,12),     # month
        random.randint(0,6),      # weekday
        0,                        # holiday
        0,                        # school
        random.uniform(200,500),
        random.uniform(200,500),
        random.uniform(200,500)
    ]]

    # ---------------- PREDICTION ----------------

    if model:
        prediction = model.predict(features)[0]
    else:
        prediction = random.uniform(300,500)

    # ---------------- GRID STATUS ----------------

    if prediction > 450:
        status = "High Load"
        peak = "High Risk"

    elif prediction > 350:
        status = "Moderate Load"
        peak = "Medium Risk"

    else:
        status = "Normal Load"
        peak = "Low Risk"


    return render_template(
        "dashboard.html",
        city=city,
        prediction=round(prediction,2),
        status=status,
        peak=peak,
        temperature=temperature,
        humidity=humidity,
        wind=wind
    )


# ---------------- CHART DATA API ----------------

@app.route("/api/chart-data")
def chart_data():

    hours = list(range(1,25))

    demand = [random.randint(300,500) for i in hours]

    return jsonify({
        "labels": hours,
        "demand": demand
    })

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/weather")
def weather():
    return render_template("weather.html")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(debug=True)