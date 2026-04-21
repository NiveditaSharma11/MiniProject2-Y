from calendar import month, weekday
import os
import re
import html
from pyexpat import features
from random import random
import random

from flask import Flask, render_template, request, jsonify, session
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

# ── FIREBASE ADMIN INIT ───────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth_module

_firebase_initialized = False
_firebase_service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH", "firebase-service-account.json")

if os.path.exists(_firebase_service_account_path):
    try:
        cred = credentials.Certificate(_firebase_service_account_path)
        firebase_admin.initialize_app(cred)
        _firebase_initialized = True
        print("✅ Firebase Admin SDK initialized")
    except Exception as _e:
        print(f"⚠️  Firebase Admin init failed: {_e}")
else:
    print("⚠️  Firebase service account file not found — Google login disabled")

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
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey_smartenergy_2026_jwt")

# ── CORS CONFIGURATION ──────────────────────────────────────────────────────
# Only allow requests from trusted origins
CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5000", "http://127.0.0.1:5000", "http://localhost:3000"],
        "methods": ["GET", "POST"],
        "allow_headers": ["Authorization", "Content-Type"]
    }
})

# ── RATE LIMITING ────────────────────────────────────────────────────────────
# Prevents brute-force and DoS attacks
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["2000 per hour", "200 per minute"]
)

# ── SECURITY HEADERS ─────────────────────────────────────────────────────────
# Added to every response to prevent XSS, clickjacking, MIME sniffing, etc.
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options']    = 'nosniff'
    response.headers['X-Frame-Options']           = 'DENY'
    response.headers['X-XSS-Protection']          = '1; mode=block'
    response.headers['Referrer-Policy']           = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy']   = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com https://www.gstatic.com https://apis.google.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://fonts.gstatic.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https://*.googleusercontent.com; "
        "connect-src 'self' https://*.googleapis.com https://*.firebaseio.com https://identitytoolkit.googleapis.com https://securetoken.googleapis.com; "
        "frame-src https://accounts.google.com https://mini-project-e6c44.firebaseapp.com;"
    )
    return response

# ── INPUT VALIDATION ─────────────────────────────────────────────────────────
# Centralised sanitisation — prevents XSS and injection attacks
def sanitize_string(value, max_length=100):
    """Strip HTML tags, escape special chars, enforce max length."""
    if not isinstance(value, str):
        return ""
    value = html.escape(value.strip())          # XSS prevention
    value = re.sub(r'[<>"\';]', '', value)      # remove dangerous chars
    return value[:max_length]

def validate_city(city):
    """City must be letters and spaces only — no SQL/script injection possible."""
    if not city:
        return False
    # SQL Injection Prevention: only allow alphabetic city names
    return bool(re.match(r'^[A-Za-z\s\-]{2,50}$', city))

def validate_demand(value):
    """Demand must be a positive finite number."""
    try:
        v = float(value)
        return 0 < v < 1_000_000  # realistic MW range
    except (TypeError, ValueError):
        return False

# ── PASSWORD HASHING ─────────────────────────────────────────────────────────
# Werkzeug bcrypt-based hashing — passwords never stored in plain text
def hash_password(plain_text):
    """Hash a password using Werkzeug's secure hashing."""
    return generate_password_hash(plain_text)

def verify_password(plain_text, hashed):
    """Verify a password against its hash."""
    return check_password_hash(hashed, plain_text)


FORECAST_MODEL_PATH = "model/load_forecast_model.pkl"
DECISION_MODEL_PATH = "model/grid_optimizer.pkl"

try:
    forecast_model = joblib.load(FORECAST_MODEL_PATH)
    decision_model = joblib.load(DECISION_MODEL_PATH)
except:
    forecast_model = None
    decision_model = None

API_KEY = os.getenv("OPENWEATHER_API_KEY")
if not API_KEY:
    print("WARNING: API key not found in environment variables")

# ── USER STORE ───────────────────────────────────────────────────────────────
# Passwords are hashed — never stored in plain text (Password Hashing)
users = {
    "admin": {
        "password": hash_password("admin123"),
        "role": "admin"
    },
    "user": {
        "password": hash_password("user123"),
        "role": "user"
    }
}

# ── AUTHENTICATION ────────────────────────────────────────────────────────────
# JWT-based login — issues a signed token valid for 1 hour
@app.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    auth = request.json

    if not auth or not auth.get("username") or not auth.get("password"):
        return jsonify({"error": "Missing credentials"}), 400

    # Input validation — sanitize before use
    username = sanitize_string(auth.get("username", ""), max_length=50)
    password = auth.get("password", "")

    if not username or not password:
        return jsonify({"error": "Invalid input"}), 400

    # Authentication check
    if username not in users or not verify_password(password, users[username]["password"]):
        return jsonify({"error": "Invalid credentials"}), 401

    token = jwt.encode({
        "user": username,
        "role": users[username]["role"],
        "exp": datetime.utcnow() + timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({"token": token, "message": "Login successful"})

# ── GOOGLE / FIREBASE AUTH ────────────────────────────────────────────────────
# Accepts a Firebase ID token, verifies it server-side, then issues our own JWT
@app.route("/api/firebase-auth", methods=["POST"])
@limiter.limit("10 per minute")
def firebase_auth():
    if not _firebase_initialized:
        return jsonify({"error": "Google login is not configured on this server."}), 503

    data = request.json
    if not data or not data.get("idToken"):
        return jsonify({"error": "Missing Firebase ID token"}), 400

    id_token = data["idToken"]

    try:
        # Verify the token with Firebase Admin SDK
        # clock_skew_seconds=60 tolerates minor system clock drift
        decoded = firebase_auth_module.verify_id_token(id_token, clock_skew_seconds=60)
    except firebase_auth_module.ExpiredIdTokenError:
        return jsonify({"error": "Google session expired. Please sign in again."}), 401
    except firebase_auth_module.InvalidIdTokenError as e:
        print(f"[Firebase] InvalidIdTokenError: {e}")
        return jsonify({"error": "Invalid Google token. Please sign in again."}), 401
    except Exception as e:
        print(f"[Firebase] Token verification failed: {type(e).__name__}: {e}")
        return jsonify({"error": "Token verification failed."}), 401

    # Extract user info from the verified token
    uid   = decoded.get("uid", "")
    email = decoded.get("email", "")
    name  = decoded.get("name", email.split("@")[0] if email else "Google User")

    # Issue our own JWT so the rest of the app works unchanged
    token = jwt.encode({
        "user": email or uid,
        "name": name,
        "role": "user",          # Google users get standard role
        "provider": "google",
        "exp": datetime.utcnow() + timedelta(hours=1)
    }, app.config['SECRET_KEY'], algorithm="HS256")

    return jsonify({
        "token": token,
        "message": "Google login successful",
        "name": name,
        "email": email
    })

# ── TOKEN AUTHENTICATION DECORATOR ───────────────────────────────────────────
# Protects all API endpoints — requires valid JWT Bearer token
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
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired. Please login again."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        return f(*args, **kwargs)
    return decorated

# ── AUTHORIZATION DECORATOR ───────────────────────────────────────────────────
# Role-based access control — only admins can access admin-only endpoints
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, "user") or request.user.get("role") != "admin":
            return jsonify({"error": "Admin access required. Insufficient permissions."}), 403
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def landing():
    return render_template("landing.html")

@app.route("/login_page")
def login_page():
    return render_template(
        "login.html",
        firebase_api_key=os.getenv("FIREBASE_API_KEY", ""),
        firebase_auth_domain=os.getenv("FIREBASE_AUTH_DOMAIN", ""),
        firebase_project_id=os.getenv("FIREBASE_PROJECT_ID", ""),
        firebase_storage_bucket=os.getenv("FIREBASE_STORAGE_BUCKET", ""),
        firebase_messaging_sender_id=os.getenv("FIREBASE_MESSAGING_SENDER_ID", ""),
        firebase_app_id=os.getenv("FIREBASE_APP_ID", ""),
        firebase_measurement_id=os.getenv("FIREBASE_MEASUREMENT_ID", ""),
    )

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

def classify_load(prediction, avg):
    """Classify load level and return label, risk, and description."""
    if prediction > avg * 1.2:
        return {
            "label": "High Load",
            "risk": "High Risk",
            "class": "critical",
            "description": "Demand significantly exceeds average. Grid stress is high. Immediate action may be required.",
            "color": "#ff5252"
        }
    elif prediction > avg * 0.9:
        return {
            "label": "Moderate Load",
            "risk": "Medium Risk",
            "class": "moderate",
            "description": "Demand is near average levels. Grid is operating within normal bounds.",
            "color": "#ff9800"
        }
    else:
        return {
            "label": "Normal Load",
            "risk": "Low Risk",
            "class": "normal",
            "description": "Demand is below average. Grid is stable with surplus capacity available.",
            "color": "#00e676"
        }


@app.route("/api/load-classification", methods=["GET"])
@token_required
def load_classification():
    """Return current load classification based on demand history."""
    global demand_history

    if len(demand_history) < 24:
        return jsonify({"error": "Not enough data"}), 400

    latest = demand_history[-1]
    avg = round(float(np.mean(demand_history[-24:])), 2)
    classification = classify_load(latest, avg)

    return jsonify({
        "current_demand": round(latest, 2),
        "average_demand": avg,
        "load_label": classification["label"],
        "risk_level": classification["risk"],
        "class": classification["class"],
        "description": classification["description"],
        "color": classification["color"],
        "demand_ratio": round(latest / avg, 3) if avg else 0
    })


@app.route("/predict", methods=["POST"])
@limiter.limit("10 per minute")
def predict():

    global demand_history

    # ── INPUT VALIDATION ──────────────────────────────────────────────────────
    city = sanitize_string(request.form.get("city", ""), max_length=50)
    region = sanitize_string(request.form.get("region", "Mixed"), max_length=20)

    # Validate region against allowed values (prevents injection)
    allowed_regions = {"Residential", "Industrial", "Commercial", "Mixed"}
    if region not in allowed_regions:
        region = "Mixed"

    # SQL Injection Prevention: city validated with strict regex
    if not validate_city(city):
        return render_template("predict.html", error="Enter a valid city name (letters only, 2-50 characters)")

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
   # 💰 Energy cost per unit (₹ per MW)

    renewable_cost_per_mw = 2      # solar/wind cheaper
    non_renewable_cost_per_mw = 6  # fossil expensive

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


   # 🎯 ML-driven core decisions

    actions["load_shedding"] = bool(action == 2)
    actions["backup_power"] = bool(action >= 1)
    actions["demand_response"] = bool(action >= 1)

    # 🧠 Optimization Score (IMPORTANT)
    grid_stress = min(1, prediction / avg) if avg != 0 else 0
    renewable_weight = renewable_ratio

    optimization_score = (renewable_weight * 0.6) - (grid_stress * 0.4)

    actions["optimization_score"] = round(optimization_score, 2)

    # 📊 Grid State based on optimization
    if optimization_score > 0.3:
        actions["optimization_status"] = "Optimal Grid ✅"
    elif optimization_score > 0:
        actions["optimization_status"] = "Balanced Grid ⚠"
    else:
        actions["optimization_status"] = "Critical Grid 🚨"

    # 🎯 Optimization goal
    actions["goal"] = "Minimize cost, reduce peak load, maximize renewable usage"

    # 🔍 AI reasoning (EXPLAINABLE AI)

    if optimization_score > 0.3:
        actions["ai_decision"] = "Optimal Grid ✅"
        actions["ai_advice"] = "High renewable + low grid stress"
        actions["ai_reason"] = "System efficiently using renewable energy"

    elif optimization_score > 0:
        actions["ai_decision"] = "Balanced Grid ⚠"
        actions["ai_advice"] = "Moderate demand, balanced sources"
        actions["ai_reason"] = "Grid operating under manageable conditions"

    else:
        actions["ai_decision"] = "Critical Grid 🚨"
        actions["ai_advice"] = "Reduce load + activate backup"
        actions["ai_reason"] = "High demand and low renewable causing stress"

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



    # cap
    if renewable > prediction:
        renewable = prediction


    non_renewable = round(prediction - renewable, 2)

    # 💰 REAL COST CALCULATION

    renewable_cost = renewable * renewable_cost_per_mw
    non_renewable_cost = non_renewable * non_renewable_cost_per_mw

    total_cost = renewable_cost + non_renewable_cost

    # 💡 Compare with worst case (all fossil)
    max_possible_cost = prediction * non_renewable_cost_per_mw

    cost_saving = round(max_possible_cost - total_cost, 2)

    actions["total_cost"] = round(total_cost, 2)
    actions["cost_saving"] = cost_saving

    if cost_saving > 0:
        actions["cost_impact"] = f"Saved ₹{cost_saving} using renewable energy"
    else:
        actions["cost_impact"] = "No cost saving. High fossil fuel usage"

    # 🎯 Cost efficiency score
    cost_efficiency = cost_saving / max_possible_cost if max_possible_cost != 0 else 0

    actions["cost_efficiency"] = round(cost_efficiency, 2)

    if cost_efficiency > 0.4:
        actions["cost_status"] = "Highly Cost Efficient 💰"
    elif cost_efficiency > 0.2:
        actions["cost_status"] = "Moderate Cost Efficiency ⚖"
    else:
        actions["cost_status"] = "Low Cost Efficiency ⚠"

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

    if region == "Residential":
        residential = round(prediction * 0.60 * factor, 2)
        industrial = round(prediction * 0.20 * factor, 2)
        commercial = round(prediction * 0.20 * factor, 2)
    elif region == "Industrial":
        residential = round(prediction * 0.20 * factor, 2)
        industrial = round(prediction * 0.60 * factor, 2)
        commercial = round(prediction * 0.20 * factor, 2)
    elif region == "Commercial":
        residential = round(prediction * 0.25 * factor, 2)
        industrial = round(prediction * 0.25 * factor, 2)
        commercial = round(prediction * 0.50 * factor, 2)
    elif temp > 30:
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

    load_class = classify_load(prediction, avg)

    # Save city to session so other pages can use it
    from flask import session
    session['last_city'] = city

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
        load_class=load_class,
        region=region,
    )

@app.route("/api/sensor-status")
@token_required
@limiter.limit("30 per minute")
def sensor_status():
    """Return latest real-time sensor reading and recent history."""
    global demand_history
    latest = demand_history[-1]
    prev   = demand_history[-2]
    change = round(latest - prev, 2)
    trend  = "Rising" if change > 0 else ("Falling" if change < 0 else "Stable")
    last_6 = demand_history[-6:]
    avg_6  = round(float(np.mean(last_6)), 2)
    return jsonify({
        "latest_demand": round(latest, 2),
        "change":        change,
        "trend":         trend,
        "avg_last_6h":   avg_6,
        "history":       [round(v, 2) for v in last_6],
        "timestamp":     datetime.now().strftime("%H:%M:%S")
    })


@app.route("/api/short-term-forecast")
@token_required
@limiter.limit("30 per minute")
def short_term_forecast():
    """Return next 6-hour short-term forecast."""
    global demand_history

    city = request.args.get("city", "Delhi")
    url  = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"

    try:
        response     = requests.get(url, timeout=5)
        weather      = response.json()
        base_temp    = weather["main"]["temp"]
        if "main" not in weather:
            raise ValueError("bad weather")
    except:
        return jsonify({"labels": [], "demand": [], "lower": [], "upper": []})

    now      = datetime.now()
    day      = now.day
    month    = now.month
    weekday  = now.weekday()
    cur_hour = now.hour

    temp_history = demand_history.copy()
    if len(temp_history) < 24:
        return jsonify({"labels": [], "demand": [], "lower": [], "upper": []})

    labels  = []
    preds   = []
    lowers  = []
    uppers  = []

    for i in range(1, 7):
        h = (cur_hour + i) % 24
        lag_1 = temp_history[-1]
        lag_2 = temp_history[-2]
        lag_24 = temp_history[0]

        sim_weather = weather.copy()
        sim_weather["main"] = dict(weather["main"])
        sim_weather["main"]["temp"] = base_temp + (h - 12) * 0.5

        features = get_features(sim_weather, h, day, month, weekday, lag_1, lag_2, lag_24)

        if forecast_model:
            pred = forecast_model.predict(features)[0]
        else:
            pred = (lag_1 + lag_2 + lag_24) / 3

        pred   = round(pred, 2)
        conf   = round(pred * 0.05, 2)
        labels.append(f"{h:02d}:00")
        preds.append(pred)
        lowers.append(round(pred - conf, 2))
        uppers.append(round(pred + conf, 2))

        temp_history.append(pred)
        temp_history.pop(0)

    return jsonify({
        "labels": labels,
        "demand": preds,
        "lower":  lowers,
        "upper":  uppers
    })


@app.route("/api/sensor-input", methods=["POST"])
@limiter.limit("60 per minute")
def sensor_input():
    """Real-time sensor data ingestion with input validation."""
    global demand_history

    data = request.json

    # ── INPUT VALIDATION ──────────────────────────────────────────────────────
    if not data or "demand" not in data:
        return jsonify({"error": "Invalid sensor data. 'demand' field required."}), 400

    # Validate demand value — must be a positive finite number
    if not validate_demand(data["demand"]):
        return jsonify({"error": "Demand must be a positive number (0 to 1,000,000 MW)"}), 400

    new_demand = round(float(data["demand"]), 2)

    demand_history.append(new_demand)
    demand_history.pop(0)

    return jsonify({
        "message": "Real-time sensor data received",
        "latest_demand": new_demand
    })


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
    from flask import session
    city = session.get("last_city", "")

    # Safe defaults so the template never crashes when visited directly
    empty_actions = {
        "ai_decision": "—", "ai_advice": "—", "ai_reason": "—",
        "strategy": "—", "grid_action": "—", "emergency": "—",
        "total_cost": 0, "cost_saving": 0, "cost_status": "—",
        "optimization_score": 0, "optimization_status": "—",
        "load_shedding": False, "backup_power": False, "demand_response": False,
        "message": "Run a forecast to see live data.", "priority": "normal",
    }

    return render_template(
        "dashboard.html",
        city=city,
        prediction="—",
        lower_bound="—",
        upper_bound="—",
        confidence_range="—",
        status="—",
        peak="—",
        temperature="—",
        humidity="—",
        wind="—",
        actions=empty_actions,
        residential=0,
        industrial=0,
        commercial=0,
        recommendation="Run a forecast first.",
        trend="—",
        grid_strategy=["Run a forecast to populate grid actions."],
        optimized_demand="—",
        shifted_load=0,
        solar=0,
        wind_energy=0,
        renewable=0,
        non_renewable=0,
        renewable_status="—",
        load_class=None,
        region="—",
    )

@app.route("/analytics")
def analytics():
    from flask import session
    city = request.args.get("city") or session.get("last_city", "Delhi")
    return render_template("analytics.html", city=city)

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
    from flask import session
    city = request.args.get("city") or session.get("last_city", "Delhi")

    temperature, humidity, wind = None, None, None
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=metric"
        resp = requests.get(url, timeout=5)
        wd = resp.json()
        if "main" in wd:
            temperature = wd["main"]["temp"]
            humidity    = wd["main"]["humidity"]
            wind        = wd["wind"]["speed"]
    except:
        pass

    return render_template(
        "weather.html",
        city=city,
        temperature=temperature,
        humidity=humidity,
        wind=wind
    )


@app.route("/api/weather-data")
@token_required
@limiter.limit("30 per minute")
def weather_data():
    from flask import session
    city = request.args.get("city") or session.get("last_city", "Delhi")

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

@app.errorhandler(401)
def unauthorized(e):
    return jsonify({"error": "Authentication required"}), 401

@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Access forbidden. Insufficient permissions."}), 403

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    # Never run with debug=True in production
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode, host="localhost", port=5000)