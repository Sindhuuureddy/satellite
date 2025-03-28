import streamlit as st
import ee
import json
import requests
import folium
from streamlit_folium import st_folium
from PIL import Image
from collections.abc import Mapping
import tempfile

st.set_page_config(page_title="Namma Kisan", layout="centered")

st.write("✅ App is starting...")

try:
    # Write secrets to a temporary file and pass the file path to EE
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(dict(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"]), f)
        f.flush()
        credentials = ee.ServiceAccountCredentials(None, f.name)
        ee.Initialize(credentials)
        st.success("🌍 Earth Engine initialized successfully!")
except Exception as e:
    st.error(f"❌ Failed to initialize Earth Engine: {e}")
    st.stop()

# Helper function
st.write("🔍 Ready for user input...")

def get_lat_lon(location_name):
    url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json"
    headers = {"User-Agent": "MyApp"}
    try:
        response = requests.get(url, headers=headers).json()
        if response:
            return float(response[0]["lat"]), float(response[0]["lon"])
    except:
        return None, None
    return None, None

# Pages
if "page" not in st.session_state:
    st.session_state.page = 1

if st.session_state.page == 1:
    st.title("🌱 Namma Kisan - ನಮ್ಮ ರೈತ")
    location = st.text_input("📍 Enter location (Kannada or English):")
    uploaded_image = st.file_uploader("📸 Upload a satellite image (optional):", type=["jpg", "jpeg", "png"])
    if location:
        st.session_state.location = location
        st.session_state.page = 2
        st.stop()

elif st.session_state.page == 2:
    location = st.session_state.location
    lat, lon = get_lat_lon(location)
    if lat and lon:
        st.session_state.lat = lat
        st.session_state.lon = lon
        st.success(f"📌 Location: {location}\nLatitude = {lat}, Longitude = {lon}")
        if st.button("➡️ Next: Soil Analysis"):
            st.session_state.page = 3
            st.stop()
    else:
        st.error("Could not retrieve coordinates. Try another location.")

elif st.session_state.page == 3:
    st.title("🧪 Soil & Crop Recommendation")
    lat, lon = st.session_state.lat, st.session_state.lon
    point = ee.Geometry.Point([lon, lat])

    image = ee.ImageCollection("COPERNICUS/S2_SR") \
        .filterBounds(point) \
        .filterDate('2023-01-01', '2023-12-31') \
        .sort("CLOUDY_PIXEL_PERCENTAGE") \
        .first()

    # Segmentation map
    ndvi = image.normalizedDifference(['B8', 'B4'])
    ndwi = image.normalizedDifference(['B3', 'B8'])
    ndbi = image.normalizedDifference(['B11', 'B8'])
    classified = ee.Image(0) \
        .where(ndvi.gt(0.2), 1) \
        .where(ndwi.gt(0.1), 2) \
        .where(ndbi.gt(0.1), 3) \
        .where(ndvi.lt(0).And(ndwi.lt(0)).And(ndbi.lt(0)), 4)

    Map = folium.Map(location=[lat, lon], zoom_start=13)
    Map.add_child(folium.LatLngPopup())
    Map.add_ee_layer = lambda self, ee_image, vis_params, name: folium.raster_layers.TileLayer(
        tiles=ee_image.getMapId(vis_params)["tile_fetcher"].url_format,
        attr="Map Data &copy; Google Earth Engine",
        name=name,
        overlay=True,
        control=True
    ).add_to(self)

    Map.add_ee_layer(image.visualize(min=0, max=3000, bands=['B4','B3','B2']), {}, "Original Image")
    Map.add_ee_layer(classified.visualize(min=0, max=4, palette=['black', 'green', 'blue', 'gray', 'yellow']), {}, "Segmented Land Cover")
    st_folium(Map, width=700, height=450)

    # Soil analysis
    soil_dataset = ee.Image('OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02')
    soil_texture = soil_dataset.select('b0')
    soil_value = soil_texture.reduceRegion(reducer=ee.Reducer.mode(), geometry=point, scale=250).getInfo()

    soil_type = "Unknown"
    if soil_value:
        soil_class = soil_value.get("b0")
        if soil_class in [1, 2]:
            soil_type = "Sandy Soil / ಮರಳು ಮಣ್ಣು"
        elif soil_class in [3, 4]:
            soil_type = "Loamy Soil / ಮಿಶ್ರ ಮಣ್ಣು"
        elif soil_class in [5, 6]:
            soil_type = "Clayey Soil / ಕಡಲು ಮಣ್ಣು"

    crops = {
        "Sandy Soil / ಮರಳು ಮಣ್ಣು": "Carrots, Peanuts, Watermelon / ಗಾಜರಿಗಳು, ಶೇಂಗಾ, ಕಲಂಗಡಿಗಳು",
        "Loamy Soil / ಮಿಶ್ರ ಮಣ್ಣು": "Wheat, Maize, Vegetables / ಗೋಧಿ, ಜೋಳ, ತರಕಾರಿಗಳು",
        "Clayey Soil / ಕಡಲು ಮಣ್ಣು": "Rice, Sugarcane, Pulses / ಅಕ್ಕಿ, ಸಕ್ಕರೆ, ಕಡಲೆ"
    }

    rainfall = {
        "Sandy Soil / ಮರಳು ಮಣ್ಣು": "300–600 mm (Low to Moderate)",
        "Loamy Soil / ಮಿಶ್ರ ಮಣ್ಣು": "600–1000 mm (Moderate)",
        "Clayey Soil / ಕಡಲು ಮಣ್ಣು": "1000+ mm (High)"
    }

    moisture = {
        "Sandy Soil / ಮರಳು ಮಣ್ಣು": "Low",
        "Loamy Soil / ಮಿಶ್ರ ಮಣ್ಣು": "Moderate",
        "Clayey Soil / ಕಡಲು ಮಣ್ಣು": "High"
    }

    st.write(f"**🟤 Soil Type:** {soil_type}")
    st.write(f"**🌾 Recommended Crops:** {crops.get(soil_type, 'N/A')}")
    st.write(f"**🌧️ Rainfall Required:** {rainfall.get(soil_type, 'N/A')}")
    st.write(f"**💧 Moisture Content:** {moisture.get(soil_type, 'N/A')}")

    if st.button("➡️ Next: Water Analysis"):
        st.session_state.page = 4
        st.stop()

elif st.session_state.page == 4:
    st.title("💧 Water Body Detection")
    lat, lon = st.session_state.lat, st.session_state.lon
    point = ee.Geometry.Point([lon, lat])

    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
    modis_presence = modis_water.reduceRegion(reducer=ee.Reducer.mean(), geometry=point.buffer(1000), scale=250).get("water_mask").getInfo()

    if modis_presence and modis_presence > 0:
        st.success("✅ Water body detected in this region.")
    else:
        st.warning("⚠️ No water body detected in this area.")
        st.info("💡 Suggested Irrigation: Borewell, Drip Irrigation, or Rainwater Harvesting")

    if st.button("🔁 Restart"):
        st.session_state.page = 1
        st.stop()

if "uploaded_image" in locals() and uploaded_image:
    st.image(Image.open(uploaded_image), caption="Uploaded Satellite Image", use_column_width=True)
    st.info("🖼️ You uploaded a custom satellite image.")
