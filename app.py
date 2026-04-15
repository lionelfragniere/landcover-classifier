import os
import json
import ee
from flask import Flask, request, jsonify, Response, render_template

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
    training_geometry = ee.Geometry.Rectangle([-10.0, 30.0, 20.0, 60.0]) # Expanded region: Europe and North Africa

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
        numPixels=50000, # Number of training points
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

@app.route('/')
def index():
    return render_template('index.html')

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