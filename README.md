# ⚡ Smart Energy AI — Grid Demand Forecasting System

An AI-powered web application that predicts electricity demand using machine learning and real-time weather data, helping grid operators anticipate load and take proactive decisions.

---

## 🚀 Features

* 🔮 **AI Demand Prediction** using trained ML model
* 🌦 **Real-time Weather Integration** (OpenWeather API)
* 📊 **24-Hour Forecast Visualization** (Chart.js)
* ⚡ **Load Classification** (High / Moderate / Normal)
* 📈 **Trend Detection** (Increasing / Decreasing)
* 🏭 **Sector-wise Load Distribution** (Residential / Industrial / Commercial)
* 🤖 **AI-based Recommendations**
* 📉 **Analytics Dashboard**
* 🌍 **City-based Forecasting**
* 🚫 **Rate Limiting for API protection**

---

## 🧠 Tech Stack

| Layer    | Technology                            |
| -------- | ------------------------------------- |
| Backend  | Flask (Python)                        |
| ML Model | Scikit-learn                          |
| Frontend | HTML, CSS, JavaScript                 |
| Charts   | Chart.js                              |
| API      | OpenWeatherMap API                    |
| Data     | Historical Electricity Demand Dataset |

---

## 📁 Project Structure

```
project/
│
├── app.py
├── requirements.txt
├── .env
│
├── model/
│   └── load_forecast_model.pkl
│
├── data/
│   └── continuous dataset.csv
│
├── templates/
│   ├── landing.html
│   ├── predict.html
│   ├── dashboard.html
│   ├── weather.html
│   └── analytics.html
│
└── static/
```

---

## ⚙️ Setup Instructions

### 1. Clone the Repository

```
git clone https://github.com/NiveditaSharma11/MiniProject2-Y.git
cd MiniProject2-Y
```

---

### 2. Create Virtual Environment

#### Windows:

```
python -m venv venv
venv\Scripts\activate
```

#### Mac/Linux:

```
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Install Dependencies

```
pip install -r requirements.txt
```

---

### 4. Create Environment Variables

Create a file named `.env` in the root directory:

```
OPENWEATHER_API_KEY=your_api_key_here
MODEL_PATH=model/load_forecast_model.pkl
DATA_PATH=data/continuous dataset.csv
```

---

### 5. Enable .env Loading

Make sure this is added at the **top of `app.py`**:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

### 6. Run the Application

```
python app.py
```

---

### 7. Open in Browser

```
http://127.0.0.1:5000/
```

---

## 🔐 Environment Variables Guide

| Variable            | Description                 |
| ------------------- | --------------------------- |
| OPENWEATHER_API_KEY | API key from OpenWeatherMap |
| MODEL_PATH          | Path to trained ML model    |
| DATA_PATH           | Path to dataset             |

---

### 🔑 How to Get OpenWeather API Key

1. Go to https://openweathermap.org/
2. Sign up / login
3. Go to "API Keys"
4. Copy your key and paste in `.env`

---

## 📊 How It Works

1. User enters city name
2. Weather API fetches real-time weather
3. System extracts:

   * Temperature
   * Humidity
   * Wind speed
   * Cloud cover
4. Combines with historical demand (lag features)
5. ML model predicts electricity demand
6. System:

   * Classifies load
   * Generates recommendations
   * Updates charts dynamically

---

## 📈 API Endpoints

| Endpoint              | Description                 |
| --------------------- | --------------------------- |
| `/predict`            | Generates demand prediction |
| `/api/chart-data`     | 24-hour forecast            |
| `/api/weather-data`   | Weather + demand data       |
| `/api/analytics-data` | Analytics insights          |
| `/api/dashboard-data` | Load distribution           |

---

## 🛡️ Security Features

* ✅ Environment variables for secrets
* ✅ Rate limiting on APIs
* ⚠️ Authentication (Planned)
* ⚠️ Authorization (Planned)
* ⚠️ Input validation (Partial)

---

## ⚡ Rate Limiting

Implemented using Flask-Limiter:

* `/predict` → 10 requests/min
* APIs → 30 requests/min
* Global → 100 requests/hour

Prevents API abuse and ensures stability.

---

## 📉 Known Limitations

* Uses simulated future weather (for demo)
* No user authentication yet
* Dataset limited to historical patterns

---

## 🚀 Future Improvements

* 🔐 User Authentication & Login System
* 🌐 Multi-language support
* 📱 Mobile responsiveness
* ☁️ Cloud deployment (AWS/GCP)
* 📊 Advanced ML models (LSTM / Time Series)
* 🔔 Real-time alerts (SMS/Email)

---

## 🧪 Testing

Basic testing includes:

* API response validation
* Error handling for invalid city
* Model fallback logic

---

## 🏆 Use Case

* Power grid operators
* Energy analysts
* Smart city planning
* Hackathon demonstrations

---

## 📸 Screenshots (Add here)

* Dashboard
* Weather Page
* Analytics Page

---

## 👩‍💻 Team

Nivedita Sharma
Aditya Garg
Aditya Sikarwar

---

## 📜 License

This project is for educational and hackathon purposes.

---

## 💡 Final Note

This project demonstrates how AI + real-time data can be used to build intelligent, predictive systems for real-world infrastructure like energy grids.

---
