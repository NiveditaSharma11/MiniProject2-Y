from flask import Flask, render_template, request, jsonify
import joblib
import random
import numpy as np
import requests
from datetime import datetime
import pandas as pd
import warnings
from sklearn.exceptions import DataConversionWarning

warnings.filterwarnings(action='ignore', category=UserWarning)
warnings.filterwarnings(action='ignore', category=DataConversionWarning)

# ---------------- LOAD HISTORICAL DATA ----------------

data = pd.read_csv("data/continuous dataset.csv")

data["datetime"] = pd.to_datetime(data["datetime"])

# keep dataset sorted
data = data.sort_values("datetime")

# last 24 hours demand history
demand_history = data["nat_demand"].tail(24).tolist()

print("Loaded historical demand history:", demand_history)

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

    global demand_history

    city = request.form.get("city")

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

    weather = requests.get(url).json()
    print("City:", city)

    # FIX: check if API returned valid weather
    if "main" not in weather:
        return render_template("predict.html", error="City not found. Please enter valid city.")

    T2M_toc = weather["main"]["temp"]          # temperature
    QV2M_toc = weather["main"]["humidity"]     # humidity
    W2M_toc = weather["wind"]["speed"]         # wind
    TQL_toc = weather["clouds"]["all"]         # cloud cover

    print("Temp:", T2M_toc)
    print("Humidity:", QV2M_toc)

    # ---------------- MODEL FEATURES ----------------

    now = datetime.now()

    hour = now.hour
    day = now.day
    month = now.month
    weekday = now.weekday()

    lag_1 = demand_history[-1]
    lag_2 = demand_history[-2]
    lag_24 = demand_history[0]

    print("Lag 1:", lag_1)
    print("Lag 2:", lag_2)
    print("Lag 24:", lag_24)

    features = [[
        T2M_toc,
        QV2M_toc,
        TQL_toc,
        W2M_toc,
        hour,
        day,
        month,
        weekday,
        0,
        0,
        lag_1,
        lag_2,
        lag_24
]]

    # ---------------- PREDICTION ----------------

    if model:
        prediction = model.predict(features)[0]
    else:
        prediction = random.uniform(300,500)

    prediction = round(prediction,2)

    demand_history.append(prediction)
    demand_history.pop(0)

    print("Predicted Demand:", prediction)

    # ---------------- GRID STATUS ----------------


    if prediction > 700:
        status = "High Load"
        peak = "High Risk"

    elif prediction > 500:
        status = "Moderate Load"
        peak = "Medium Risk"

    else:
        status = "Normal Load"
        peak = "Low Risk"

    residential = round(prediction * 0.40,2)
    industrial = round(prediction * 0.35,2)
    commercial = round(prediction * 0.25,2)

    return render_template(
        "dashboard.html",
        city=city,
        prediction=round(prediction,2),
        status=status,
        peak=peak,
        temperature=T2M_toc,
        humidity=QV2M_toc,
        wind=W2M_toc,
        residential=residential,
        industrial=industrial,
        commercial=commercial
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

    residential = 0
    industrial = 0
    commercial = 0

    return render_template(
        "dashboard.html",
        residential=residential,
        industrial=industrial,
        commercial=commercial
    )

# ---------------- WEATHER PAGE ----------------

@app.route("/weather")
def weather():

    city = request.args.get("city","Delhi")

    api_key = "69fcbe36a4fc8cda45c92f1971f0e0b0"

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

    response = requests.get(url)

    weather_data = response.json()

    # FIX: prevent crash
    if "main" not in weather_data:
        return render_template("weather.html", error="City not found")

    temperature = weather_data["main"]["temp"]
    humidity = weather_data["main"]["humidity"]
    wind = weather_data["wind"]["speed"]
    clouds = weather_data["clouds"]["all"]
    city_name = weather_data["name"]

    temps = [
        round(temperature - 3,2),
        round(temperature + 2,2),
        round(temperature + 4,2),
        round(temperature + 1,2)
    ]

    humidity_trend = [
        humidity - 10,
        humidity + 5,
        humidity + 10,
        humidity
    ]

    demand = [
        320,
        410,
        460,
        380
    ]

    return render_template(
        "weather.html",
        city=city_name,
        temperature=temperature,
        humidity=humidity,
        wind=wind,
        clouds=clouds,
        temps=temps,
        humidity_trend=humidity_trend,
        demand=demand
    )

@app.route("/api/prediction-forecast")
def prediction_forecast():

    global demand_history

    hours = list(range(1,25))
    predictions = []

    city = "Delhi"

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    weather = requests.get(url).json()

    if "main" not in weather:
        return jsonify({"hours": hours, "predictions": []})

    T2M_toc = weather["main"]["temp"]
    QV2M_toc = weather["main"]["humidity"]
    W2M_toc = weather["wind"]["speed"]
    TQL_toc = weather["clouds"]["all"]

    now = datetime.now()

    day = now.day
    month = now.month
    weekday = now.weekday()

    temp_history = demand_history.copy()

    for h in hours:

        lag_1 = temp_history[-1]
        lag_2 = temp_history[-2]
        lag_24 = temp_history[0]

        features = [[
            T2M_toc,
            QV2M_toc,
            TQL_toc,
            W2M_toc,
            h,
            day,
            month,
            weekday,
            0,
            0,
            lag_1,
            lag_2,
            lag_24
        ]]

        if model:
            pred = model.predict(features)[0]
        else:
            pred = random.uniform(300,500)

        pred = round(pred,2)

        predictions.append(pred)

        temp_history.append(pred)
        temp_history.pop(0)

    return jsonify({
        "hours": hours,
        "predictions": predictions
    })

# ---------------- FIXED ANALYTICS ROUTE ----------------

@app.route("/analytics")
def analytics():

    city = request.args.get("city","Delhi")

    predicted_demand = random.randint(500,650)

    renewable = round(predicted_demand * random.uniform(0.25,0.4))
    non_renewable = predicted_demand - renewable

    return render_template(
        "analytics.html",
        city=city,
        renewable=renewable,
        non_renewable=non_renewable
    )


# ---------------- RUN SERVER ----------------

if __name__ == "__main__":
    app.run(debug=True)