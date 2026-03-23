import os

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


MODEL_PATH = os.getenv("MODEL_PATH", "model/load_forecast_model.pkl")

try:
    model = joblib.load(MODEL_PATH)
except:
    model = None

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
    return [[
        weather["main"]["temp"],
        weather["main"]["humidity"],
        weather["clouds"]["all"],
        weather["wind"]["speed"],
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

    if not model:
        print("WARNING: Model not loaded, using fallback")

    try:
        if model:
            prediction = model.predict(features)[0]
        else:
            prediction = (lag_1 + lag_2 + lag_24) / 3
    except Exception:
        return render_template("predict.html", error="Prediction failed. Try again.")
    
    prediction = round(prediction, 2)
    confidence_range = round(prediction * 0.05, 2)
    lower_bound = round(prediction - confidence_range, 2)
    upper_bound = round(prediction + confidence_range, 2)

    demand_history.append(prediction)
    demand_history.pop(0)

    avg = np.mean(demand_history[-24:])

    if prediction > avg * 1.2:
        status = "High Load"
        peak = "High Risk"
    elif prediction > avg * 0.9:
        status = "Moderate Load"
        peak = "Medium Risk"
    else:
        status = "Normal Load"
        peak = "Low Risk"


    if peak == "High Risk":
        recommendation = "Increase power generation and activate backup grids immediately."
    elif peak == "Medium Risk":
        recommendation = "Monitor load and prepare additional supply if needed."
    else:
        recommendation = "Grid is stable. Maintain current distribution."


    trend = "Stable"

    if prediction > lag_1:
        trend = "Increasing"
    elif prediction < lag_1:
        trend = "Decreasing"

    temp = weather["main"]["temp"]

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
        residential=residential,
        industrial=industrial,
        commercial=commercial,
        recommendation=recommendation,
        trend=trend
    )


@app.route("/api/chart-data")
@token_required
@limiter.limit("30 per minute")
def chart_data():

    global demand_history

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

        if model:
            pred = model.predict(features)[0]
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
@admin_required
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