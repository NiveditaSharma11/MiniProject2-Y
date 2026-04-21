# ⚡ Smart Energy AI — Grid Demand Forecasting System

An AI-powered web application that predicts electricity demand using machine learning, real-time weather data, and sensor inputs — helping grid operators anticipate load, classify demand, and take proactive decisions.

---

## ✅ Implemented Features

| Feature | Status | Details |
|---|---|---|
| AI Demand Prediction | ✅ Fully Implemented | Scikit-learn ML model with lag features + weather inputs |
| Load Classification | ✅ Fully Implemented | Classifies demand as High / Moderate / Normal with risk level |
| AI-based Recommendations | ✅ Fully Implemented | Decision, advice, strategy, emergency mode per prediction |
| Weather-Aware Prediction | ✅ Fully Implemented | OpenWeather API feeds temperature, humidity, wind, clouds into model |
| Short-Term Forecast (6h) | ✅ Fully Implemented | Next 6-hour forecast with confidence bands (±5%) |
| Long-Term Forecast (24h) | ✅ Fully Implemented | Full 24-hour demand projection |
| Real-Time Sensor Feed | ✅ Fully Implemented | Live sensor card updates every 15s via `/api/sensor-input` |
| Peak Demand Detection | ✅ Fully Implemented | Alert bar + color-coded classification card |
| Demand Response Insights | ✅ Fully Implemented | Grid Action Plan: load shedding, backup, demand shifting |
| Renewable Energy Tracking | ✅ Fully Implemented | Solar + wind generation, renewable share %, deficit |
| User Authentication (JWT) | ✅ Fully Implemented | JWT login with success/failure feedback, Enter key support |
| Interactive Charts | ✅ Fully Implemented | Chart.js: line, bar, doughnut, radar, scatter |
| Sector-wise Distribution | ✅ Fully Implemented | Residential / Industrial / Commercial split by region type |
| Cost & Efficiency Analysis | ✅ Fully Implemented | Cost saved via renewables, efficiency rating |
| Rate Limiting | ✅ Fully Implemented | Flask-Limiter: 2000/hour, 200/minute, per-endpoint limits |
| Analytics Dashboard | ✅ Fully Implemented | Weekly trend, peak hours, temp vs demand correlation |

---

## 🧠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Flask (Python) |
| ML Models | Scikit-learn (load_forecast_model.pkl, grid_optimizer.pkl) |
| Frontend | HTML, CSS (Inter font), JavaScript |
| Charts | Chart.js |
| Weather API | OpenWeatherMap API |
| Auth | JWT (PyJWT) + Werkzeug password hashing |
| Data | Historical Electricity Demand CSV dataset |
| Security | Flask-Limiter, Flask-CORS, python-dotenv |

---

## 📁 Project Structure

```
project/
├── app.py                          # Main Flask application
├── requirements.txt
├── .env                            # API keys and config
│
├── model/
│   ├── load_forecast_model.pkl     # ML demand forecasting model
│   └── grid_optimizer.pkl          # Grid decision model
│
├── data/
│   └── continuous dataset.csv      # Historical demand dataset
│
├── templates/
│   ├── landing.html                # Public landing page
│   ├── login.html                  # JWT authentication
│   ├── predict.html                # Forecast input form
│   ├── dashboard.html              # Main analytics dashboard
│   ├── renewable.html              # Renewable energy page
│   ├── weather.html                # Weather intelligence page
│   └── analytics.html             # Historical analytics page
│
└── static/
    ├── charts.js
    └── style.css
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/NiveditaSharma11/MiniProject2-Y.git
cd MiniProject2-Y
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create `.env` in the root directory:

```
OPENWEATHER_API_KEY=your_api_key_here
DATA_PATH=data/continuous dataset.csv
SECRET_KEY=your_secret_key_here
```

### 5. Run the Application

```bash
python app.py
```

### 6. Open in Browser

```
http://127.0.0.1:5000/
```

**Demo credentials:** username: `admin` | password: `admin123`

---

## 🔑 How to Get OpenWeather API Key

1. Go to https://openweathermap.org/
2. Sign up / login → API Keys → copy your key → paste in `.env`

---

## 📊 How It Works

```
User enters city + region type
        ↓
OpenWeather API fetches real-time weather (temp, humidity, wind, clouds)
        ↓
ML model combines weather + historical lag features → predicts demand (MW)
        ↓
Load Classification: High / Moderate / Normal + risk level
        ↓
AI Recommendation: decision, advice, strategy, emergency flag
        ↓
Grid Action Plan: load shedding / backup / demand response
        ↓
Cost Analysis: renewable savings, efficiency rating
        ↓
Dashboard: charts, sensor feed, 6h/24h forecast toggle
```

---

## 📈 API Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `POST /login` | No | JWT authentication |
| `POST /predict` | No | Run ML demand prediction |
| `GET /api/load-classification` | JWT | Current load class + risk level |
| `GET /api/chart-data` | JWT | 24-hour demand forecast |
| `GET /api/short-term-forecast` | JWT | Next 6-hour forecast with confidence bands |
| `GET /api/sensor-status` | JWT | Live sensor reading + trend |
| `POST /api/sensor-input` | No | Push real-time sensor data |
| `GET /api/weather-data` | JWT | Weather + demand correlation |
| `GET /api/analytics-data` | JWT | Weekly trend, peak hours, correlation |
| `GET /api/renewable-data` | JWT | Solar, wind, renewable share |
| `GET /api/dashboard-data` | JWT | Sector-wise load distribution |

---

## 🔐 Security

- JWT tokens (1-hour expiry) for all protected API endpoints
- Password hashing via Werkzeug
- Rate limiting: 2000 req/hour global, 30 req/min per API endpoint, 10 req/min for predictions
- Environment variables for all secrets (never hardcoded)
- Input validation on city name and sensor data

---

## 🧪 Testing

Run the test suite:

```bash
python -m pytest test_app.py -v
```

Tests cover:
- App startup
- Login success / invalid credentials / missing credentials
- Load classification API (auth + response structure)
- Sensor input validation

---

## 🏆 Use Cases

- Power grid operators monitoring real-time demand
- Energy analysts forecasting peak load periods
- Utility companies planning renewable integration
- Smart city infrastructure management

---

## 👩‍💻 Team

| Name | Role |
|---|---|
| Nivedita Sharma | Developer |
| Aditya Garg | Developer |
| Aditya Sikarwar | Developer |

---

## 📜 License

This project is for educational purposes.
