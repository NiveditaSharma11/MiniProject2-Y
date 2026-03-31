import os
from pyexpat import features
from random import random
import random

from flask import Flask, render_template, request, jsonify
import joblib
import numpy as np
import requests
from datetime import datetime
import pandas as pd
import warnings
from sklearn.exceptions import DataConversionWarning
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import jwt
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from dotenv import load_dotenv
load_dotenv()

warnings.filterwarnings(action='ignore', category=UserWarning)
warnings.filterwarnings(action='ignore', category=DataConversionWarning)

DATA_PATH = os.getenv("DATA_PATH", "data/continuous dataset.csv")
data = pd.read_csv(DATA_PATH)

data["datetime"] = pd.to_datetime(data["datetime"])
data = data.sort_values("datetime")

demand_history = data["nat_demand"].tail(24).tolist()

import random
from datetime import datetime

def simulate_realtime_demand():
    global demand_history

    last_value = demand_history[-1]
    hour = datetime.now().hour

    # 📊 Realistic daily pattern

    if 6 <= hour <= 10:
        base_change = 4   # morning increase
    elif 18 <= hour <= 22:
        base_change = 8   # evening peak
    elif 0 <= hour <= 5:
        base_change = -6  # night drop
    else:
        base_change = 1   # stable daytime

    # 🎯 small randomness (natural fluctuation)
    noise = random.uniform(-2, 2)

    new_value = last_value + base_change + noise

    # prevent unrealistic values
    new_value = max(50, new_value)

    new_value = round(new_value, 2)

    demand_history.append(new_value)
    demand_history.pop(0)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey")

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:3000"]
    }
})

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["100 per hour"]
)


FORECAST_MODEL_PATH = "model/load_forecast_model.pkl"
DECISION_MODEL_PATH = "model/grid_optimiser.pkl"

try:
    forecast_model = joblib.load(FORECAST_MODEL_PATH)
    decision_model = joblib.load(DECISION_MODEL_PATH)
except:
    forecast_model = None
    decision_model = None

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    print("WARNING: API key not found in environment variables")

users = {
    "admin": {
        "password": generate_password_hash("admin123"),
        "role": "admin"
    },
    "user": {
        "password": generate_password_hash("user123"),
        "role": "user"
    }
}

@app.route("/login", methods=["POST"])
def login():

    auth = request.json

    if not auth or not auth.get("username") or not auth.get("password"):
        return jsonify({"error": "Missing credentials"}), 400

    username = auth.get("username")
    password = auth.get("password")

    if username not in users or not check_password_hash(users[username]["password"], password):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "user": username,
        "role": users[username]["role"],
        "exp": datetime.utcnow() + timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({"token": token})

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
    
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                return jsonify({"error": "Invalid token format"}), 401

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            request.user = data
        except:
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(*args, **kwargs)

    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):

        if not hasattr(request, "user") or request.user.get("role") != "admin":
            return jsonify({"error": "Admin access required"}), 403

        return f(*args, **kwargs)

    return decorated

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login_page")
def login_page():
    return render_template("login.html")

@app.route("/predict_page")
def predict_page():
    return render_template("predict.html")

def get_features(weather, hour, day, month, weekday, lag_1, lag_2, lag_24):
    return pd.DataFrame([{
        "T2M_toc": weather["main"]["temp"],
        "QV2M_toc": weather["main"]["humidity"],
        "TQL_toc": weather["clouds"]["all"],
        "W2M_toc": weather["wind"]["speed"],
        "hour": hour,
        "day": day,
        "month": month,
        "day_of_week": weekday,
        "holiday": 0,
        "school": 0,
        "lag_1": lag_1,
        "lag_2": lag_2,
        "lag_24": lag_24
    }])

@app.route("/predict", methods=["POST"])
@limiter.limit("10 per minute")
def predict():

    global demand_history

    city = request.form.get("city")

    if not city or not city.replace(" ", "").isalpha():
        return render_template("predict.html", error="Enter a valid city name (letters only)")

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        weather = response.json()

        if "main" not in weather or "wind" not in weather or "clouds" not in weather:
            return render_template("predict.html", error="Invalid city or incomplete weather data")

    except requests.exceptions.Timeout:
        return render_template("predict.html", error="Request timed out. Try again.")

    except requests.exceptions.HTTPError:
        return render_template("predict.html", error="API error occurred.")

    except requests.exceptions.RequestException:
        return render_template("predict.html", error="Network error. Check connection.")
    
    now = datetime.now()

    hour = now.hour
    day = now.day
    month = now.month
    weekday = now.weekday()

    if len(demand_history) < 24:
        return render_template("predict.html", error="Not enough historical data")

    lag_1 = demand_history[-1]
    lag_2 = demand_history[-2]
    lag_24 = demand_history[0]

    features = get_features(weather, hour, day, month, weekday, lag_1, lag_2, lag_24)

    if not forecast_model:
        print("WARNING: Model not loaded, using fallback")


    try:
        # 🔮 Demand Prediction (REAL ML)

        if forecast_model:
            prediction = forecast_model.predict(features)[0]
        else:
            prediction = (lag_1 + lag_2 + lag_24) / 3

        prediction = round(prediction, 2)
    except Exception:
        return render_template("predict.html", error="Prediction failed. Try again.")
    
    prediction = round(prediction, 2)
    confidence_range = round(prediction * 0.05, 2)
    lower_bound = round(prediction - confidence_range, 2)
    upper_bound = round(prediction + confidence_range, 2)

    demand_history.append(prediction)
    demand_history.pop(0)

    avg = np.mean(demand_history[-24:])
    temp = weather["main"]["temp"]

    clouds = weather["clouds"]["all"]
    wind_speed = weather["wind"]["speed"]

    # ☀ SOLAR (based on sunlight + clouds)
    if 6 <= hour <= 18:
        sunlight_factor = (hour - 6) / 12
        cloud_factor = (100 - clouds) / 100
        solar = round(sunlight_factor * cloud_factor * 50, 2)
    else:
        solar = 0

    # 🌬 WIND (cubic relation)
    wind_energy = round((wind_speed ** 3) * 0.5, 2)

    # ⚡ TOTAL
    renewable = round(solar + wind_energy, 2)

    renewable_ratio = renewable / prediction if prediction else 0
    # 🤖 ML-based Grid Decision

    # 🎯 Rule-based context (ONLY explanation, not control)
    # 🎯 Initialize actions safely
    actions = {
        "load_shedding": False,
        "backup_power": False,
        "demand_response": False
    }

# 🎯 Rule-based context (ONLY for explanation)
    if prediction > avg * 1.2 or temp > 35:
        actions["priority"] = "critical"
        actions["message"] = "Extreme demand due to heat. Immediate action required."

    elif prediction > avg:
        actions["priority"] = "moderate"
        actions["message"] = "Demand rising. Shift usage to off-peak hours."

    else:
        actions["priority"] = "normal"
        actions["message"] = "Demand under control."

    decision_input = pd.DataFrame([{
        "demand": prediction,
        "temp": weather["main"]["temp"],
        "renewable_ratio": renewable_ratio
    }])

    if decision_model:
        action = decision_model.predict(decision_input)[0]
    else:
        action = 1

    if action == 2:
        actions["load_shedding"] = True
        actions["backup_power"] = True
        actions["demand_response"] = True

    elif action == 1:
        actions["backup_power"] = True
        actions["demand_response"] = True


    if action == 2:
        actions["ml_decision"] = "High Demand → Activate backup & demand response"
    elif action == 1:
        actions["ml_decision"] = "Moderate Demand → Balance grid"
    else:
        actions["ml_decision"] = "Low Demand → Normal operation"

    # 🎯 Decision Intelligence based on renewable

    if renewable_ratio > 0.5:
        actions["strategy"] = "Use Renewable Priority"
        actions["grid_action"] = "Reduce fossil fuel usage"
        actions["message"] += " Renewable supply is high. Shift grid to green energy."

    elif renewable_ratio > 0.3:
        actions["strategy"] = "Balanced Energy Mix"
        actions["grid_action"] = "Use hybrid supply"
        actions["message"] += " Moderate renewable available. Balance sources."

    else:
        actions["strategy"] = "Conventional Backup Mode"
        actions["grid_action"] = "Increase non-renewable generation"
        actions["message"] += " Renewable low. Activate backup sources."


    # 💰 Cost intelligence

    cost_saving = round(renewable * 2, 2)

    if renewable_ratio > 0.4:
        actions["cost_impact"] = f"Saving approx ₹{cost_saving} due to renewable usage"
    else:
        actions["cost_impact"] = "Higher operational cost due to fossil fuel usage"

    # cap
    if renewable > prediction:
        renewable = prediction

    non_renewable = round(prediction - renewable, 2)

    renewable_status = ""

    ratio = renewable / prediction if prediction else 0

    if ratio > 0.6:
        renewable_status = "Excellent renewable penetration 🌱"
    elif ratio > 0.35:
        renewable_status = "Moderate renewable usage ⚡"
    else:
        renewable_status = "Low renewable usage 🔥"

    if prediction > avg * 1.2:
        status = "High Load"
        peak = "High Risk"
    elif prediction > avg * 0.9:
        status = "Moderate Load"
        peak = "Medium Risk"
    else:
        status = "Normal Load"
        peak = "Low Risk"

    # ⚡ Critical intelligent decision

    if peak == "High Risk" and renewable_ratio < 0.3:
        actions["emergency"] = "YES"
        actions["message"] += " CRITICAL: High demand + low renewable → Load shedding required."

    elif peak == "High Risk" and renewable_ratio > 0.5:
        actions["emergency"] = "CONTROLLED"
        actions["message"] += " High demand but renewable helping stabilize grid."

    # 🧠 AI GRID DECISION ENGINE

    grid_score = (renewable_ratio * 0.6) - ((prediction / avg) * 0.4)

    if grid_score > 0.3:
        actions["ai_decision"] = "Optimal Grid State ✅"
        actions["ai_advice"] = "Grid is stable. Maximize renewable usage."

    elif grid_score > 0:
        actions["ai_decision"] = "Moderate Load ⚠"
        actions["ai_advice"] = "Balance renewable and conventional sources."

    else:
        actions["ai_decision"] = "Critical Load 🚨"
        actions["ai_advice"] = "Reduce load + activate backup immediately."

    trend = "Stable"

    if prediction > lag_1:
        trend = "Increasing"
    elif prediction < lag_1:
        trend = "Decreasing"

    

    grid_strategy = []

    if actions["load_shedding"]:
        grid_strategy.append("Cut power to non-critical zones")

    if actions["demand_response"]:
        grid_strategy.append("Notify users to reduce usage")

    if actions["backup_power"]:
        grid_strategy.append("Activate diesel/backup generators")

    if temp > 30:
        grid_strategy.append("High AC usage expected")

    if trend == "Increasing":
        grid_strategy.append("Prepare for demand spike")

    if not grid_strategy:
        grid_strategy.append("No immediate action required. System stable.")

    shifted_load = 0
    optimized_demand = prediction

    if actions["demand_response"]:
        shifted_load = round(prediction * 0.1, 2)
        optimized_demand = round(prediction - shifted_load, 2)


    factor = 1

    if temp > 30:
        residential = round(prediction * 0.45 * factor, 2)
        industrial = round(prediction * 0.30 * factor, 2)
        commercial = round(prediction * 0.25 * factor, 2)

    elif hour >= 18:
        residential = round(prediction * 0.50 * factor, 2)
        industrial = round(prediction * 0.25 * factor, 2)
        commercial = round(prediction * 0.25 * factor, 2)

    else:
        residential = round(prediction * 0.35 * factor, 2)
        industrial = round(prediction * 0.40 * factor, 2)
        commercial = round(prediction * 0.25 * factor, 2)

    total = residential + industrial + commercial

    residential = round(residential / total * prediction, 2)
    industrial = round(industrial / total * prediction, 2)
    commercial = round(commercial / total * prediction, 2)

    if "emergency" not in actions:
        actions["emergency"] = "NO"

    return render_template(
        "dashboard.html",
        city=city,
        prediction=prediction,
        lower_bound=lower_bound,
        upper_bound=upper_bound,
        confidence_range=confidence_range,
        status=status,
        peak=peak,
        temperature=weather["main"]["temp"],
        humidity=weather["main"]["humidity"],
        wind=weather["wind"]["speed"],
        actions=actions,
        residential=residential,
        industrial=industrial,
        commercial=commercial,
        recommendation = actions["message"],
        trend=trend,
        grid_strategy=grid_strategy,
        optimized_demand=optimized_demand,
        shifted_load=shifted_load,
        solar=solar,
        wind_energy=wind_energy,
        renewable=renewable,
        non_renewable=non_renewable,
        renewable_status=renewable_status,
    )


@app.route("/api/chart-data")
@token_required
@limiter.limit("30 per minute")
def chart_data():

    global demand_history
    simulate_realtime_demand()

    hours = list(range(1, 25))
    predictions = []

    city = request.args.get("city", "Delhi")

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=5)
        weather = response.json()
        base_temp = weather["main"]["temp"]
        if "main" not in weather:
            return jsonify({
                "labels": hours,
                "demand": [0]*24
            })

    except: 
        return jsonify({
            "labels": hours,
            "demand": [0]*24
        })

    now = datetime.now()
    day = now.day
    month = now.month
    weekday = now.weekday()

    temp_history = demand_history.copy()

    if len(temp_history) < 24:
        return jsonify({
            "labels": hours,
            "demand": [0]*24
        })

    for h in hours:

        lag_1 = temp_history[-1]
        lag_2 = temp_history[-2]
        lag_24 = temp_history[0]

        simulated_weather = weather.copy()

        simulated_weather["main"]["temp"] = base_temp + (h - 12) * 0.5

        features = get_features(simulated_weather, h, day, month, weekday, lag_1, lag_2, lag_24)

        if forecast_model:
            pred = forecast_model.predict(features)[0]
        else:
            pred = (lag_1 + lag_2 + lag_24) / 3

        pred = round(pred, 2)

        predictions.append(pred)

        temp_history.append(pred)
        temp_history.pop(0)

    return jsonify({
        "labels": hours,
        "demand": predictions
    })

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/analytics")
def analytics():

    city = request.args.get("city", "Delhi")

    return render_template(
        "analytics.html",
        city=city
    )

@app.route("/api/analytics-data")
@token_required
# @admin_required
@limiter.limit("30 per minute")
def analytics_data():

    global demand_history

    latest = demand_history[-1]

    renewable = round(latest * 0.3, 2)
    non_renewable = round(latest - renewable, 2)

    weekly = demand_history[-7:] if len(demand_history) >= 7 else [0]*7
    peak = demand_history[-6:] if len(demand_history) >= 6 else [0]*6

    temps = [20, 25, 28, 30, 32, 35]

    if len(demand_history) >= 6:
        correlation = [
            {"x": temps[i], "y": demand_history[-6:][i]}
            for i in range(6)
        ]
    else:
        correlation = []

    return jsonify({
        "weekly": weekly,
        "renewable": renewable,
        "non_renewable": non_renewable,
        "peak": peak,
        "correlation": correlation
    })

@app.route("/renewable")
def renewable_page():
    return render_template("renewable.html")


@app.route("/api/renewable-data")
@token_required
def renewable_data():

    global demand_history

    hours = list(range(1, 25))
    demand = demand_history[-24:]

    solar = []
    wind = []
    renewable = []

    for i, d in enumerate(demand):

        hour = i

        # simulate realistic variation
        clouds = 30 + (i % 5) * 10
        wind_speed = 2 + (i % 4)

        # ☀ SOLAR (linked to demand + weather)
        if 6 <= hour <= 18:
            sunlight_factor = (hour - 6) / 12
            cloud_factor = (100 - clouds) / 100

            s = d * 0.25 * sunlight_factor * cloud_factor
        else:
            s = d * 0.05

        # 🌬 WIND (linked to demand + wind speed)
        wind_factor = min(1, wind_speed / 10)
        w = d * 0.2 * wind_factor

        # 🎯 Add realism (random variation)
        s = round(s * random.uniform(0.9, 1.1), 2)
        w = round(w * random.uniform(0.9, 1.1), 2)

        r = round(s + w, 2)
        solar.append(s)
        wind.append(w)
        renewable.append(r)

    total_demand = sum(demand)
    total_renewable = sum(renewable)

    percentage = round((total_renewable / total_demand) * 100, 2) if total_demand else 0
    deficit = round(total_demand - total_renewable, 2)

    return jsonify({
        "hours": hours,
        "demand": demand,
        "renewable": renewable,
        "solar": solar,
        "wind": wind,
        "percentage": percentage,
        "deficit": deficit
    })

@app.route("/weather")
def weather():

    city = request.args.get("city", "Delhi")

    return render_template(
        "weather.html",
        city=city
    )

@app.route("/api/weather-data")
@token_required
@limiter.limit("30 per minute")
def weather_data():

    city = request.args.get("city", "Delhi")

    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

    try:
        response = requests.get(url, timeout=5)
        weather_data = response.json()

        if "main" not in weather_data:
            return jsonify({"error": "Invalid city"})

    except:
        return jsonify({"error": "API failed"})

    temperature = weather_data["main"]["temp"]
    humidity = weather_data["main"]["humidity"]
    wind = weather_data["wind"]["speed"]
    clouds = weather_data["clouds"]["all"]

    temps = [
        round(temperature - 3, 2),
        round(temperature + 2, 2),
        round(temperature + 4, 2),
        round(temperature + 1, 2)
    ]

    humidity_trend = [
        humidity - 10,
        humidity + 5,
        humidity + 10,
        humidity
    ]

    demand = demand_history[-4:] if len(demand_history) >= 4 else [0,0,0,0]

    return jsonify({
        "temps": temps,
        "humidity": humidity_trend,
        "demand": demand,
        "temperature": temperature,
        "wind": wind,
        "clouds": clouds
    })

@app.route("/api/dashboard-data")
@token_required
@limiter.limit("30 per minute")
def dashboard_data():

    global demand_history

    if len(demand_history) < 24:
        return jsonify({
            "residential": 0,
            "industrial": 0,
            "commercial": 0
        })

    latest = demand_history[-1]

    residential = round(latest * 0.4, 2)
    industrial = round(latest * 0.35, 2)
    commercial = round(latest * 0.25, 2)

    return jsonify({
        "residential": residential,
        "industrial": industrial,
        "commercial": commercial
    })

@app.errorhandler(429)
def rate_limit_error(e):
    return jsonify({"error": "Too many requests. Try again later."}), 429

if __name__ == "__main__":
    app.run(debug=True)