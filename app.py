import streamlit as st
import ee
import json
import requests
import folium
from streamlit_folium import st_folium
from PIL import Image
from collections.abc import Mapping
import tempfile

st.set_page_config(page_title="Satellite Image Analysis", layout="centered")

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

if "page" not in st.session_state:
    st.session_state.page = 1

if st.session_state.page == 1:
    st.title("🌱 Satellite Image Analysis")
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
        st.warning("⚠️ No water body detected in this area. / ಈ ಪ್ರದೇಶದಲ್ಲಿ ಯಾವುದೇ ನೀರಿನ ನಿಕ್ಷೇಪ ಪತ್ತೆಯಾಗಿಲ್ಲ.")
        st.info("💡 Suggested Irrigation / ಶಿಫಾರಸು ಮಾಡಿದ ನೀರಾವರಿ: Borewell (ಬೋರ್‌ವೆಲ್), Drip (ಟಪಕ ನೀರಾವರಿ), Rainwater Harvesting (ಮಳೆ ನೀರಿನ ಸಂಗ್ರಹಣೆ)")
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

    if image:
        # NDVI health visualization
        ndvi_health = image.normalizedDifference(['B8', 'B4']).rename("NDVI")
        ndvi_vis = {"min": 0.0, "max": 1.0, "palette": ['red', 'yellow', 'green']}

        ndvi_map = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
        ndvi_map.add_ee_layer = add_ee_layer
        ndvi_map.add_ee_layer(ndvi_health, ndvi_vis, 'NDVI Vegetation Health')

        st.markdown("**🌿 NDVI Vegetation Health / ಸಸ್ಯಾವರಣದ ಆರೋಗ್ಯ:**")
        st_folium(ndvi_map, width=700, height=350)

        # Land Use / Land Cover (LULC) Change Detection
        lulc_early = ee.ImageCollection("ESA/WorldCover/v100").filterDate('2020-01-01', '2020-12-31').first()
        lulc_recent = ee.ImageCollection("ESA/WorldCover/v100").filterDate('2023-01-01', '2023-12-31').first()

        lulc_diff = lulc_recent.subtract(lulc_early).clip(point.buffer(1000))
        lulc_vis = {"min": -100, "max": 100, "palette": ['red', 'white', 'green']}

        lulc_map = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
        lulc_map.add_ee_layer = add_ee_layer
        lulc_map.add_ee_layer(lulc_diff, lulc_vis, 'LULC Change Detection')

        st.markdown("**🗺️ Land Use / Land Cover Change (2020 → 2023) / ಭೂಪಯೋಗ ಬದಲಾವಣೆ:**")
        st_folium(lulc_map, width=700, height=350)

        ndvi = image.normalizedDifference(['B8', 'B4'])
        ndwi = image.normalizedDifference(['B3', 'B8'])
        ndbi = image.normalizedDifference(['B11', 'B8'])
        classified = ee.Image(0) \
            .where(ndvi.gt(0.2), 1) \
            .where(ndwi.gt(0.1), 2) \
            .where(ndbi.gt(0.1), 3) \
            .where(ndvi.lt(0).And(ndwi.lt(0)).And(ndbi.lt(0)), 4)

        def add_ee_layer(self, ee_image, vis_params, name):
            map_id_dict = ee.Image(ee_image).getMapId(vis_params)
            folium.raster_layers.TileLayer(
                tiles=map_id_dict["tile_fetcher"].url_format,
                attr="Google Earth Engine",
                name=name,
                overlay=True,
                control=True,
            ).add_to(self)

        folium.Map.add_ee_layer = add_ee_layer

        original_map = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)
        segmented_map = folium.Map(location=[lat, lon], zoom_start=13, control_scale=True)

        original_map.add_ee_layer(image.visualize(min=0, max=3000, bands=['B4','B3','B2']), {}, "Original Image")
        segmented_map.add_ee_layer(classified.visualize(min=0, max=4, palette=['black', 'green', 'blue', 'gray', 'yellow']), {}, "Segmented")

        col1, col2 = st.columns(2)
        with col1:
            st.write("🛰️ Original Satellite Image")
            st_folium(original_map, width=340, height=350)
        with col2:
            st.write("🗺️ Segmented Land Cover")
            st_folium(segmented_map, width=340, height=350)

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

elif st.session_state.page == 4:
    st.title("💧 Water Body Detection")
    lat, lon = st.session_state.lat, st.session_state.lon
    point = ee.Geometry.Point([lon, lat])

    modis_water = ee.ImageCollection("MODIS/006/MOD44W").mosaic().select("water_mask")
    modis_presence = modis_water.reduceRegion(reducer=ee.Reducer.mean(), geometry=point.buffer(1000), scale=250).get("water_mask").getInfo()

    if modis_presence and modis_presence > 0:
        st.success("✅ Water body detected in this region. / ಈ ಪ್ರದೇಶದಲ್ಲಿ ನೀರಿನ ನಿಕ್ಷೇಪ ಪತ್ತೆಯಾಗಿದೆ.")

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

if "uploaded_image" in locals() and uploaded_image:
    st.image(Image.open(uploaded_image), caption="Uploaded Satellite Image", use_column_width=True)
    st.info("🖼️ You uploaded a custom satellite image.")
