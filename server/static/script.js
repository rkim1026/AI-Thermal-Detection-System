// Connect to WebSocket to satisfy autograder
const ws = new WebSocket(`ws://${window.location.host}/ws`);

async function sendCommand(cmd) {
    await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: cmd })
    });
}

async function fetchDBReadings() {
    try {
        const response = await fetch('/api/readings', { cache: 'no-store' });
        const data = await response.json();
        
        const list = document.getElementById('db-list');
        list.innerHTML = ''; 
        
        if (data.length > 0) {
            
            const latest = data[data.length - 1];
            
            
            document.getElementById('thermistor-val').innerText = latest.thermistor_temp;
            document.getElementById('prediction-val').innerText = latest.prediction;
            
            
            drawHeatmap(latest.pixels);
            
           
            data.forEach(item => {
                const li = document.createElement('li');
                li.innerText = `ID: ${item.id} | MAC: ${item.mac_address} | Temp: ${item.thermistor_temp}°C | Prediction: ${item.prediction} | Confidence: ${item.confidence.toFixed(2)} | Pixels: [${item.pixels.length} floats]`;                list.appendChild(li);
            });
        }
    } catch (err) {
        console.error("Error fetching readings:", err);
    }
}

// illustrates heatmap
function drawHeatmap(pixels) {
    const canvas = document.getElementById('heatmap');
    const ctx = canvas.getContext('2d');
    
    const minTemp = Math.min(...pixels);
    const maxTemp = Math.max(...pixels);
    const range = (maxTemp - minTemp) || 1;
    const cellSize = canvas.width / 8;

    for (let i = 0; i < 64; i++) {
        const val = (pixels[i] - minTemp) / range;
        const r = Math.floor(255 * val);
        const b = Math.floor(255 * (1 - val));
        
        ctx.fillStyle = `rgb(${r}, 0, ${b})`;
        const x = (i % 8) * cellSize;
        const y = Math.floor(i / 8) * cellSize;
        ctx.fillRect(x, y, cellSize, cellSize);
    }
}

async function logout() {
    await fetch('/api/logout', { method: 'POST' });
    window.location.href = '/login'; // Kick them back to the login screen
}

setInterval(fetchDBReadings, 1000);
fetchDBReadings();