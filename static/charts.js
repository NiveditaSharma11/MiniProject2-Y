const ctx = document.getElementById("demandChart");

fetch("/api/chart-data")
.then(res => res.json())
.then(data => {

new Chart(ctx, {

type: "line",

data: {
labels: data.labels,

datasets: [{
label: "Hourly Electricity Demand",
data: data.values,
borderWidth: 3
}]

},

options: {
responsive: true
}

});

});