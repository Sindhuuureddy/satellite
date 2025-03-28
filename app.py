import ee
import folium
from folium.plugins import FloatImage
from streamlit_folium import st_folium
import streamlit as st
import json
import requests
import tempfile
from PIL import Image

# Add custom CSS to improve the theme
st.set_page_config(page_title="Satellite Image Analysis", layout="centered")

st.markdown("""
    <style>
    body {
        background-color: #E6F8E0;  /* Light green background */
        font-family: 'Arial', sans-serif;
    }
    .stButton>button {
        background-color: #4CAF50;  /* Green button */
        color: white;
        border-radius: 8px;
        padding: 10px 20px;
    }
    .stTitle {
        color: #2c6b2f;  /* Dark green title */
    }
    .stTextInput>div>div>input {
        background-color: #f4f7f3;  /* Light input box background */
        border: 1px solid #4CAF50;  /* Green border for inputs */
    }
    .stSidebar {
        background-color: #b2d8b2;  /* Sidebar green */
    }
    .stAlert {
        background-color: #ffcc00;  /* Yellow warning background */
    }
    .stSuccess {
        background-color: #d4edda;  /* Light green success background */
    }
    .stWarning {
        background-color: #ffeeba;  /* Light yellow warning background */
    }
    </style>
""", unsafe_allow_html=True)

# Function to add Earth Engine layers to a folium map
def add_ee_layer(self, ee_image, vis_params, name):
    """Adds an Earth Engine image as a layer to the folium map."""
    map_id_dict = ee.Image(ee_image).getMapId(vis_params)
    folium.raster_layers.TileLayer(
        tiles=map_id_dict["tile_fetcher"].url_format,
        attr="Google Earth Engine",
        name=name,
        overlay=True,
        control=True,
    ).add_to(self)

# Patch folium.Map
folium.Map.add_ee_layer = add_ee_layer

# Initialize Earth Engine credentials
st.write("✅ App is starting...")

try:
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(dict(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"]), f)
        f.flush()
        credentials = ee.ServiceAccountCredentials(None, f.name)
        ee.Initialize(credentials)
        st.success("🌍 Earth Engine initialized successfully!")
except Exception as e:
    st.error(f"❌ Failed to initialize Earth Engine: {e}")
    st.stop()

# Get latitude and longitude from location name
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

if "page" not in st.session_state:
    st.session_state.page = 1

# First page: Input location and optional satellite image
if st.session_state.page == 1:
    st.title("🌱 Satellite Image Analysis")
    location = st.text_input("📍 Enter location (Kannada or English):")
    uploaded_image = st.file_uploader("📸 Upload a satellite image (optional):", type=["jpg", "jpeg", "png"])
    if location:
        st.session_state.location = location
        st.session_state.page = 2
        st.stop()

# Second page: Display latitude, longitude, and proceed to soil analysis
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
        st.warning("⚠️ No water body detected in this area. / ಈ ಪ್ರದೇಶದಲ್ಲಿ ಯಾವುದೇ ನೀರಿನ ನಿಕ್ಷೇಪ ಪತ್ತೆಯಾಗಿಲ್ಲ.")
        st.info("💡 Suggested Irrigation / ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಾವರಿ: Borewell (ಬೋರ್‌ವೆಲ್), Drip (ಟಪಕ ನೀರಾವರಿ), Rainwater Harvesting (ಮಳೆ ನೀರಿನ ಸಂಗ್ರಹಣೆ)")
        st.error("Could not retrieve coordinates. Try another location.")

# Third page: Soil and crop recommendation, NDVI
elif st.session_state.page == 3:
    st.title("🧪 Soil & Crop Recommendation")
    lat, lon = st.session_state.lat, st.session_state.lon
    point = ee.Geometry.Point([lon, lat])

    # Sentinel-2 image for analysis
    image = ee.ImageCollection("COPERNICUS/S2_SR") \
        .filterBounds(point) \
        .filterDate('2023-01-01', '2023-12-31') \
        .sort("CLOUDY_PIXEL_PERCENTAGE") \
        .first()

    if image:
        # NDVI (Vegetation Health)
        ndvi_health = image.normalizedDifference(['B8', 'B4']).rename("NDVI")
        ndvi_vis = {"min": 0.0, "max": 1.0, "palette": ['red', 'yellow', 'green']}

        ndvi_map = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
        ndvi_map.add_ee_layer(ndvi_health, ndvi_vis, 'NDVI Vegetation Health')

        st.markdown("**🌿 NDVI Vegetation Health / ಸಸ್ಯಾವರಣದ ಆರೋಗ್ಯ:**")
        st_folium(ndvi_map, width=700, height=350)

        # Soil type, crop recommendation, moisture, and rainfall
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

        st.write(f"**🟤 Soil Type / ಮಣ್ಣು ಪ್ರಕಾರ:** {soil_type}")
        st.write(f"**🌾 Recommended Crops / ಶಿಫಾರಸು ಮಾಡಿದ ಬೆಳೆಗಳು:** {crops.get(soil_type, 'N/A')}")
        st.write(f"**🌧️ Rainfall Required / ಅಗತ್ಯವಿರುವ ಮಳೆಯ ಪ್ರಮಾಣ:** {rainfall.get(soil_type, 'N/A')}")
        st.write(f"**💧 Moisture Content / ತೇವಾಂಶದ ಮಟ್ಟ:** {moisture.get(soil_type, 'N/A')}")

        if st.button("➡️ Next: Water Analysis"):
            st.session_state.page = 4
            st.stop()

# Fourth page: Water body detection, pollution status, and fishery possibility
elif st.session_state.page == 4:
    st.title("💧 Water Body Detection")
    lat, lon = st.session_state.lat, st.session_state.lon
    point = ee.Geometry.Point([lon, lat])

    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
    modis_presence = modis_water.reduceRegion(reducer=ee.Reducer.mean(), geometry=point.buffer(1000), scale=250).get("water_mask").getInfo()

    if modis_presence and modis_presence > 0:
        st.success("✅ Water body detected in this region. / ಈ ಪ್ರದೇಶದಲ್ಲಿ ನೀರಿನ ನಕ್ಷೇಪ ಪತ್ತೆಯಾಗಿದೆ.")

        # Water Quality Indicators (Pollution & Fish Feasibility)
        water_quality = ee.ImageCollection("ECMWF/ERA5_LAND/MONTHLY") \
            .filterBounds(point) \
            .select(["lake_total_layer_temperature", "lake_mix_layer_depth", "lake_bottom_temperature"]) \
            .mean()

        quality_data = water_quality.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point.buffer(1000),
            scale=500,
            maxPixels=1e13
        ).getInfo()

        temp = quality_data.get("lake_total_layer_temperature")
        depth = quality_data.get("lake_mix_layer_depth")

        pollution_status = "Moderate"
        if temp and temp > 305:
            pollution_status = "High / ಹೆಚ್ಚಿನ ಮಾಲಿನ್ಯ"
        elif temp and temp < 295:
            pollution_status = "Low / ಕಡಿಮೆ ಮಾಲಿನ್ಯ"

        fishing_possible = "Yes / ಹೌದು" if depth and depth > 0.5 else "No / ಇಲ್ಲ"

        st.markdown(f"**🌊 Water Pollution Estimate / ನೀರಿನ ಮಾಲಿನ್ಯ ಪ್ರಮಾಣ:** {pollution_status}")
        st.markdown(f"**🐟 Fishery Possibility / ಮೀನುಗಾರಿಕೆ ಸಾಧ್ಯತೆ:** {fishing_possible}")

    else:
        st.warning("⚠️ No water body detected in this area. / ಈ ಪ್ರದೇಶದಲ್ಲಿ ಯಾವುದೇ ನೀರಿನ ನಿಕ್ಷೇಪ ಪತ್ತೆಯಾಗಿಲ್ಲ.")
        st.info("💡 Suggested Irrigation / ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಾವರಿ: Borewell (ಬೋರ್‌ವೆಲ್), Drip (ಟಪಕ ನೀರಾವರಿ), Rainwater Harvesting (ಮಳೆ ನೀರಿನ ಸಂಗ್ರಹಣೆ)")

    if st.button("🔁 Restart"):
        st.session_state.page = 1
        st.stop()
