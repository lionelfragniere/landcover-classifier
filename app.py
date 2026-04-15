import os
import json
import ee
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

CLASSIFIER = None # Global variable to store the pre-trained classifier

# Initialize Earth Engine
try:
    # Ensure Earth Engine is authenticated. For server-side, this usually means
    # setting up service account credentials or pre-authenticating in the environment.
    # The project ID is crucial for authentication.
    ee.Initialize(project='unops-gpo-psc-prtnshp-dev')
    GEE_INITIALIZED = True
except Exception as e:
    print(f"Earth Engine initialization failed: {e}")
    print("Please ensure your Earth Engine credentials are set up (e.g., via `earthengine authenticate`) and the project ID is correct.")
    GEE_INITIALIZED = False

def _train_classifier():
    """Trains a Random Forest classifier using ESA WorldCover 2021 as ground truth."""
    global CLASSIFIER
    print("Starting classifier training...")

    # Define a broad, representative training geometry (e.g., a region in Europe)
    # This ensures the classifier learns from diverse land cover types.
    training_geometry = ee.Geometry.Rectangle([-5.0, 40.0, 10.0, 50.0]) # Example: France/Germany region

    # Load ESA WorldCover 2021 as ground truth
    worldcover = ee.Image('ESA/WorldCover/v100/2021').select('Map')

    # Filter Sentinel-2 image collection for the training region and year
    s2_training = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(training_geometry) \
        .filterDate('2021-01-01', '2021-12-31') \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
        .median()

    # Calculate spectral indices for training
    ndvi_training = s2_training.normalizedDifference(['B8', 'B4']).rename('NDVI') # NIR, Red
    ndwi_training = s2_training.normalizedDifference(['B3', 'B8']).rename('NDWI') # Green, NIR
    ndbi_training = s2_training.normalizedDifference(['B11', 'B8']).rename('NDBI') # SWIR1, NIR

    # Combine bands and indices for classification
    bands = ['B2','B3','B4','B8','B11','B12','NDVI','NDWI','NDBI']
    composite_training = s2_training.select(['B2','B3','B4','B8','B11','B12']).addBands([ndvi_training, ndwi_training, ndbi_training])

    # Combine Sentinel-2 composite with WorldCover labels
    training_image = composite_training.addBands(worldcover)

    # Define class mapping from WorldCover to simplified 5 classes
    # 0: Water, 1: Forest, 2: Agriculture, 3: Urban, 4: Barren
    # WorldCover classes:
    # 10: Tree cover -> Forest (1)
    # 20: Shrubland -> Forest (1)
    # 30: Grassland -> Forest (1)
    # 40: Cropland -> Agriculture (2)
    # 50: Vegetated aquatic or regularly flooded -> Water (0)
    # 60: Moss and lichen -> Barren (4)
    # 70: Bare / sparse vegetation -> Barren (4)
    # 80: Built-up -> Urban (3)
    # 90: Snow and ice -> Barren (4)
    # 95: Permanent water bodies -> Water (0)
    # 100: Herbaceous wetland -> Water (0) (Adding this to water for simplicity)

    # Create a remapping expression
    # Use a list of [old_value, new_value, ...]
    remapping_list = [
        10, 1,   # Tree cover -> Forest
        20, 1,   # Shrubland -> Forest
        30, 1,   # Grassland -> Forest
        40, 2,   # Cropland -> Agriculture
        50, 0,   # Vegetated aquatic or regularly flooded -> Water
        60, 4,   # Moss and lichen -> Barren
        70, 4,   # Bare / sparse vegetation -> Barren
        80, 3,   # Built-up -> Urban
        90, 4,   # Snow and ice -> Barren
        95, 0,   # Permanent water bodies -> Water
        100, 0   # Herbaceous wetland -> Water
    ]
    
    # Apply the remapping to the WorldCover band
    remapped_worldcover = worldcover.remap(
        remapping_list[::2], # Old values
        remapping_list[1::2] # New values
    ).rename('class')

    # Add the remapped WorldCover to the training image
    training_image = composite_training.addBands(remapped_worldcover)

    # Sample training points from the combined image
    # Use a larger scale for sampling to get more diverse pixels
    training_points = training_image.sample(
        region=training_geometry,
        scale=10, # Sentinel-2 resolution
        numPixels=5000, # Number of training points
        seed=0,
        tileScale=8 # Increase tileScale for larger regions
    ).filter(ee.Filter.neq('class', None)) # Filter out points where WorldCover is No Data

    # Train the Random Forest classifier
    try:
        classifier = ee.Classifier.smileRandomForest(numberOfTrees=50).train(
            features=training_points,
            classProperty='class',
            inputProperties=bands
        )
        CLASSIFIER = classifier
        print("Classifier training complete!")
    except ee.EEException as e:
        print(f"Earth Engine error during classifier training: {e}")
        CLASSIFIER = None
    except Exception as e:
        print(f"Unexpected error during classifier training: {e}")
        CLASSIFIER = None

if GEE_INITIALIZED:
    _train_classifier()

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<title>UNOPS Land Cover Classifier</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter',sans-serif;background:#0D1E2F;color:#E0E0E0;min-height:100vh}
header{background:#001F3F;padding:16px 24px;display:flex;align-items:center;gap:16px;border-bottom:2px solid #0092D1}
header h1{font-size:1.4rem;color:#0092D1}
.container{display:grid;grid-template-columns:350px 1fr;height:calc(100vh - 64px)}
.sidebar{background:#001830;padding:20px;overflow-y:auto;border-right:1px solid #0092D133}
.map-area{position:relative}
#map{width:100%;height:100%}
label{display:block;font-size:0.85rem;color:#88A0B8;margin:12px 0 4px}
select,input[type=range]{width:100%;padding:8px;background:#0D2A42;border:1px solid #0092D144;border-radius:6px;color:white;font-family:inherit}
.btn{width:100%;padding:12px;background:#0092D1;color:white;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;margin-top:16px;transition:all 0.2s}
.btn:hover{background:#00A3E8;transform:translateY(-1px)}
.btn:disabled{opacity:0.5;cursor:not-allowed}
.results{margin-top:20px}
.results h3{color:#0092D1;margin-bottom:12px;font-size:1rem}
.stat-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #ffffff11}
.stat-label{color:#88A0B8}.stat-value{color:#0092D1;font-weight:600}
.chart-container{background:#0D2A42;border-radius:8px;padding:16px;margin-top:12px}
.loading-overlay{position:absolute;inset:0;background:rgba(13,30,47,0.85);display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:1000}
.spinner{width:48px;height:48px;border:4px solid #0092D133;border-top-color:#0092D1;border-radius:50%;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.coords{font-size:0.8rem;color:#0092D1;margin-top:8px;padding:8px;background:#0D2A42;border-radius:4px}
@media(max-width:768px){.container{grid-template-columns:1fr;grid-template-rows:auto 50vh}}
</style>
</head>
<body>
<header><h1>🌍 UNOPS Land Cover Classifier</h1><span style="color:#88A0B8;font-size:0.85rem">Powered by GEE + Random Forest</span></header>
<div class="container">
<div class="sidebar">
  <h3 style="color:white;margin-bottom:8px">Analysis Parameters</h3>
  <p style="color:#88A0B8;font-size:0.8rem">Click on the map to select a point</p>
  <div class="coords" id="coords">No point selected</div>
  <label>Year</label>
  <select id="year">
    <option value="2024">2024</option><option value="2023" selected>2023</option>
    <option value="2022">2022</option><option value="2021">2021</option>
    <option value="2020">2020</option><option value="2019">2019</option>
  </select>
  <label>Radius: <span id="radiusVal">10</span> km</label>
  <input type="range" id="radius" min="1" max="50" value="10">
  <button class="btn" id="classifyBtn" onclick="classify()" disabled>Select a point first</button>
  <div class="results" id="results" style="display:none">
    <h3>Classification Results</h3>
    <div id="stats"></div>
    <div class="chart-container"><canvas id="chart" height="200"></canvas></div>
  </div>
</div>
<div class="map-area">
  <div id="map"></div>
  <div class="loading-overlay" id="loading" style="display:none">
    <div class="spinner"></div>
    <p style="margin-top:16px;color:#0092D1">Classifying land cover...</p>
  </div>
</div>
</div>
<script>
let map=L.map('map').setView([46.5,6.6],10);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'OSM'}).addTo(map);
let marker=null,circle=null,tileLayer=null,chart=null,selectedLat=null,selectedLng=null;
document.getElementById('radius').oninput=function(){
  document.getElementById('radiusVal').textContent=this.value;
  if(circle)circle.setRadius(this.value*1000);
};
map.on('click',function(e){
  selectedLat=e.latlng.lat;selectedLng=e.latlng.lng;
  if(marker)map.removeLayer(marker);if(circle)map.removeLayer(circle);
  marker=L.marker(e.latlng).addTo(map);
  let r=document.getElementById('radius').value*1000;
  circle=L.circle(e.latlng,{radius:r,color:'#0092D1',fillOpacity:0.1}).addTo(map);
  document.getElementById('coords').textContent=`Lat: ${selectedLat.toFixed(4)}, Lng: ${selectedLng.toFixed(4)}`;
  document.getElementById('classifyBtn').disabled=false;
  document.getElementById('classifyBtn').textContent='🔍 Classify Land Cover';
});
async function classify(){
  if(!selectedLat)return;
  document.getElementById('loading').style.display='flex';
  document.getElementById('classifyBtn').disabled=true;
  document.getElementById('classifyBtn').textContent='Processing...';
  try{
    let res=await fetch('/api/classify',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({lat:selectedLat,lng:selectedLng,year:+document.getElementById('year').value,radius:+document.getElementById('radius').value})});
    let data=await res.json();
    if(!res.ok)throw new Error(data.error||'Classification failed');
    showResults(data);
  }catch(e){alert('Error: '+e.message)}
  finally{document.getElementById('loading').style.display='none';document.getElementById('classifyBtn').disabled=false;document.getElementById('classifyBtn').textContent='🔍 Classify Land Cover'}
}
function showResults(data){
  document.getElementById('results').style.display='block';
  let html='';
  const names=['Water','Forest','Agriculture','Urban','Barren'];
  const colors=['#2196F3','#4CAF50','#FFEB3B','#F44336','#9E9E9E'];
  data.classes.forEach((c,i)=>{html+=`<div class="stat-row"><span class="stat-label">${names[i]}</span><span class="stat-value">${c.toFixed(1)}%</span></div>`});
  document.getElementById('stats').innerHTML=html;
  if(chart)chart.destroy();
  chart=new Chart(document.getElementById('chart'),{type:'pie',data:{labels:names,datasets:[{data:data.classes,backgroundColor:colors}]},options:{plugins:{legend:{labels:{color:'#E0E0E0'}}}}});
  if(tileLayer)map.removeLayer(tileLayer);
  if(data.tile_url){tileLayer=L.tileLayer(data.tile_url,{opacity:0.6}).addTo(map)}
}
</script>
</body>
</html>"""

@app.route('/')
def index():
    return Response(HTML_TEMPLATE, mimetype='text/html')

@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "gee": GEE_INITIALIZED})

@app.route('/api/classify', methods=['POST'])
def classify():
    if not GEE_INITIALIZED:
        return jsonify({"error": "GEE not initialized. Please check server logs for details."}), 500
    data = request.get_json()
    lat = data.get('lat')
    lng = data.get('lng')
    year = data.get('year', 2023)
    radius = data.get('radius', 10) * 1000 # Convert km to meters
    
    if lat is None or lng is None:
        return jsonify({"error": "Latitude and Longitude are required."}), 400

    if CLASSIFIER is None:
        return jsonify({"error": "Classifier not trained. Please check server logs for details."}), 500

    try:
        point = ee.Geometry.Point([lng, lat])
        roi = point.buffer(radius)
        
        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'
        
        # Filter Sentinel-2 image collection
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(roi).filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)).median()
        
        # Calculate spectral indices
        ndvi = s2.normalizedDifference(['B8', 'B4']).rename('NDVI') # NIR, Red
        ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI') # Green, NIR
        ndbi = s2.normalizedDifference(['B11', 'B8']).rename('NDBI') # SWIR1, NIR
        
        # Combine bands and indices for classification
        bands = ['B2','B3','B4','B8','B11','B12','NDVI','NDWI','NDBI']
        composite = s2.select(['B2','B3','B4','B8','B11','B12']).addBands([ndvi, ndwi, ndbi])
        
        # Classify the image within the ROI using the pre-trained classifier
        classified = composite.clip(roi).classify(CLASSIFIER)
        
        # Calculate class percentages
        # The frequencyHistogram reducer returns a dictionary where keys are class values
        # and values are pixel counts.
        counts = classified.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=roi, scale=30, maxPixels=1e9 # Use a coarser scale for histogram to speed up
        ).get('classification')
        
        hist = counts.getInfo() # Get the dictionary from the Earth Engine object
        total = sum(hist.values()) if hist else 1
        classes = [0]*5 # Initialize percentages for 5 classes
        for k, v in (hist or {}).items():
            idx = int(float(k)) # Class keys might be float strings
            if 0 <= idx < 5:
                classes[idx] = round(v / total * 100, 1)
        
        # Define visualization parameters and get tile URL
        palette = ['2196F3','4CAF50','FFEB3B','F44336','9E9E9E'] # Water, Forest, Agriculture, Urban, Barren
        vis_params = {'min': 0, 'max': 4, 'palette': palette}
        map_id = classified.getMapId(vis_params)
        tile_url = map_id['tile_fetcher'].url_format
        
        return jsonify({"classes": classes, "tile_url": tile_url, "total_pixels": total})
    except ee.EEException as e:
        print(f"Earth Engine error during classification: {e}")
        return jsonify({"error": f"Earth Engine processing failed: {str(e)}"}), 500
    except Exception as e:
        print(f"Server error during classification: {e}")
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)