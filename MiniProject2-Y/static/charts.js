const ctx = document.getElementById("demandChart").getContext("2d");

fetch("/api/chart-data")
.then(res => res.json())
.then(data => {

if(window.demandChart){
    window.demandChart.destroy(); // prevents duplication bug
}

window.demandChart = new Chart(ctx, {

type: "line",

data: {
labels: data.labels,

datasets: [{
label: "Hourly Electricity Demand",
data: data.values,
borderWidth: 3,
borderColor: "#00e5ff",
backgroundColor: "rgba(0,229,255,0.2)",
fill: true,
tension: 0.4
}]
},

options: {
responsive: true,
maintainAspectRatio: false,   // 🔥 IMPORTANT FIX

plugins: {
legend: {
labels: {
color: "white"
}
}
},

scales: {
x: {
ticks: { color: "white" }
},
y: {
ticks: { color: "white" }
}
}
}

});

});