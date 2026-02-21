
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import google_sheets
import cloudinary_uploader

# --- Constants ---
ICON_OPTIONS = ["Default (●)", "🌵", "🌊", "❄️", "🌲", "🪨", "⛏️", "👨‍🌾", "🏡", "👑", "👾"]
ICON_MAP_REVERSE = {
    "Default (●)": "Default",
    "🌵": "🌵",
    "🌊": "🌊",
    "❄️": "❄️",
    "🌲": "🌲",
    "🪨": "🪨",
    "⛏️": "⛏️",
    "👨‍🌾": "👨‍🌾",
    "🏡": "🏡",
    "👑": "👑",
    "👾": "👾"
}
ICON_MAP_DISPLAY = {v: k for k, v in ICON_MAP_REVERSE.items()}

# --- Setup ---
st.set_page_config(page_title="Minecraft World Mapper", layout="wide")

# --- Backend Functions ---

def load_data():
    """Loads location data from Google Sheets."""
    return google_sheets.load_data()

def save_data(data):
    """Saves location data to Google Sheets."""
    return google_sheets.save_all_data(data)

def save_image(uploaded_file):
    """Uploads image to Cloudinary and returns the URL."""
    if uploaded_file is None:
        return None
    return cloudinary_uploader.upload_image(uploaded_file)

# --- UI ---

st.title("🗺️ Minecraft World Mapper")

# Validating Data exists & Init Session State
if "locations" not in st.session_state:
    with st.spinner("Loading data from Google Sheets..."):
        st.session_state.locations = load_data()

if "edit_mode" not in st.session_state:
    st.session_state.edit_mode = False

if "edit_id" not in st.session_state:
    st.session_state.edit_id = None

# --- Sidebar: Add New Location ---
with st.sidebar:
    st.header("📍 Add New Location")
    with st.form("add_location_form", clear_on_submit=True):
        name = st.text_input("Location Name (Optional)")
        
        selected_icon_display = st.selectbox("Map Icon", options=ICON_OPTIONS)
        selected_icon_value = ICON_MAP_REVERSE[selected_icon_display]
        selected_bg_color = st.selectbox("Icon Background Color", options=["Default (#F5DEB3)", "Light Blue"])
        
        col1, col2 = st.columns(2)
        with col1:
            x_coord = st.number_input("X", value=None, step=1)
        with col2:
            z_coord = st.number_input("Z", value=None, step=1)
            
        y_coord = st.number_input("Y (Height)", value=None, step=1, help="Optional vertical coordinate")
        
        description = st.text_area("Description (Optional)")
        uploaded_images = st.file_uploader("Upload Images", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        
        submitted = st.form_submit_button("Save Location")
        
    if submitted:
        if x_coord is None or y_coord is None or z_coord is None:
            st.error("Please enter valid X, Y, and Z coordinates.")
        else:
            final_name = name.strip() if name else f"Location @ {x_coord}, {z_coord}"
            
            image_paths = []
            if uploaded_images:
                with st.spinner("Uploading images to Cloudinary..."):
                    for img_file in uploaded_images:
                        url = save_image(img_file)
                        if url:
                            image_paths.append(url)
                        else:
                            st.warning(f"Failed to upload {img_file.name}")

            new_location = {
                "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                "name": final_name,
                "x": x_coord,
                "y": y_coord,
                "z": z_coord,
                "description": description,
                "image_paths": image_paths,
                "icon": selected_icon_value,
                "bg_color": selected_bg_color
            }
            st.session_state.locations.append(new_location)
            save_data(st.session_state.locations)
            st.success(f"Location '{final_name}' saved!")
            st.rerun()

    # --- Sidebar: Data Migration ---
    with st.expander("🔧 Data Migration (Restore Old Data)"):
        st.write("If you can't see your old locations, use this to upload them to the cloud.")
        if st.button("Load from 'locations.json' & Upload"):
            import json
            import os
            Local_Data_File = "locations.json"
            if os.path.exists(Local_Data_File):
                try:
                    with open(Local_Data_File, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                    
                    if old_data:
                        # Append to current data
                        st.info(f"Found {len(old_data)} local records. Uploading...")
                        
                        # Merge logic: Avoid duplicates by ID
                        current_ids = {loc["id"] for loc in st.session_state.locations}
                        added_count = 0
                        
                        for item in old_data:
                            # Compatibility fix: ensure new fields exist
                            if "icon" not in item: item["icon"] = "Default"
                            if "image_paths" not in item:
                                if "image_path" in item and item["image_path"]:
                                     # Warning: Local image paths won't work in cloud unless re-uploaded
                                     # For now, just keep the path string, but it will appear broken
                                     item["image_paths"] = [item["image_path"]] 
                                else:
                                     item["image_paths"] = []
                            if "image_path" in item: del item["image_path"]

                            if item["id"] not in current_ids:
                                st.session_state.locations.append(item)
                                added_count += 1
                        
                        if added_count > 0:
                            save_data(st.session_state.locations)
                            st.success(f"Successfully migrated {added_count} locations!")
                            st.rerun()
                        else:
                            st.warning("All local locations are already in the cloud.")
                    else:
                        st.warning("Local file is empty.")
                except Exception as e:
                    st.error(f"Error reading local file: {e}")
            else:
                st.error("'locations.json' not found in project directory.")

# --- Main Page: Map ---

locations_data = st.session_state.locations

if locations_data:
    df = pd.DataFrame(locations_data)
    
    # Ensure 'icon' column exists
    if "icon" not in df.columns:
        df["icon"] = "Default"
    if "bg_color" not in df.columns:
        df["bg_color"] = "Default (#F5DEB3)"

    # Split DataFrames
    df_default = df[df["icon"] == "Default"].copy()
    df_emoji = df[df["icon"] != "Default"].copy()

    # --- Layout: Map (Left) vs Details (Right) ---
    col_map, col_details = st.columns([2, 1])

    with col_map:
        # Base Figure
        fig = go.Figure()

        # Trace 0: Default Markers
        if not df_default.empty:
            fig.add_trace(go.Scatter(
                x=df_default["x"],
                y=df_default["z"],
                mode='markers',
                marker=dict(size=12, line=dict(width=2, color='DarkSlateGrey')),
                text=df_default["name"],
                hoverinfo='text',
                name="Markers",
                customdata=df_default["id"] # Store ID for selection
            ))
        else:
            fig.add_trace(go.Scatter(x=[], y=[], mode='markers', name="Markers"))

        # Trace 1: Emoji Markers
        if not df_emoji.empty:
            bg_color_mapped = df_emoji["bg_color"].map({
                "Default (#F5DEB3)": "rgba(0,0,0,0)",
                "Light Blue": "lightblue"
            }).fillna("rgba(0,0,0,0)")

            fig.add_trace(go.Scatter(
                x=df_emoji["x"],
                y=df_emoji["z"],
                mode='markers+text',
                text=df_emoji["icon"],
                textfont=dict(size=20),
                marker=dict(size=26, color=bg_color_mapped, line=dict(width=0)),
                hovertext=df_emoji["name"],
                hoverinfo='text',
                name="Icons",
                customdata=df_emoji["id"] # Store ID for selection
            ))
        else:
            fig.add_trace(go.Scatter(x=[], y=[], mode='markers+text', name="Icons"))

        fig.update_layout(
            title="World Map (X vs Z)",
            xaxis_title="X Coordinate",
            yaxis_title="Z Coordinate",
            height=600,
            clickmode='event+select',
            plot_bgcolor='#F5DEB3',
            margin=dict(l=0, r=0, t=30, b=0)
        )

        event = st.plotly_chart(fig, on_select="rerun", selection_mode="points", use_container_width=True, config={'scrollZoom': True})
    
    # Capture selection
    selected_ids = []
    if event and "selection" in event and "points" in event["selection"]:
         for p in event["selection"]["points"]:
             if "customdata" in p:
                 selected_ids.append(p["customdata"])

    with col_details:
        st.markdown("### Location Details")

        if st.session_state.edit_mode and st.session_state.edit_id:
            st.info("✏️ Edit Mode Active")
            
            # Find the location to edit
            edit_index = next((i for i, item in enumerate(st.session_state.locations) if item["id"] == st.session_state.edit_id), -1)
            
            if edit_index != -1:
                loc_to_edit = st.session_state.locations[edit_index]
                
                with st.form("edit_location_form"):
                    new_name = st.text_input("Name", value=loc_to_edit['name'])
                    
                    # Icon Selection
                    current_icon_val = loc_to_edit.get("icon", "Default")
                    current_display = ICON_MAP_DISPLAY.get(current_icon_val, "Default (●)")
                    index_val = ICON_OPTIONS.index(current_display) if current_display in ICON_OPTIONS else 0
                    
                    new_icon_display = st.selectbox("Icon", options=ICON_OPTIONS, index=index_val)
                    new_icon_value = ICON_MAP_REVERSE[new_icon_display]

                    current_bg_val = loc_to_edit.get("bg_color", "Default (#F5DEB3)")
                    bg_options = ["Default (#F5DEB3)", "Light Blue"]
                    bg_idx = bg_options.index(current_bg_val) if current_bg_val in bg_options else 0
                    new_bg_color = st.selectbox("Icon Background Color", options=bg_options, index=bg_idx)

                    c1, c2 = st.columns(2)
                    new_x = c1.number_input("X", value=loc_to_edit['x'], step=1)
                    new_z = c2.number_input("Z", value=loc_to_edit['z'], step=1)
                    new_y = st.number_input("Y", value=loc_to_edit['y'], step=1)
                    new_desc = st.text_area("Description", value=loc_to_edit['description'])
                    
                    # Show existing images with delete option
                    current_images = loc_to_edit.get("image_paths", [])
                    st.caption("Existing Images:")
                    
                    images_to_keep = []
                    
                    if current_images:
                        for i, img_url in enumerate(current_images):
                            if img_url.startswith("http"):
                                st.image(img_url, width=100)
                            else:
                                st.image(img_url, width=100)

                            if not st.checkbox("Delete", key=f"del_img_{i}_{st.session_state.edit_id}"):
                                images_to_keep.append(img_url)
                    
                    st.caption("Add more images:")
                    new_images_upload = st.file_uploader("Upload", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
                    
                    submitted_update = st.form_submit_button("Update", type="primary")

                if submitted_update:
                    final_new_name = new_name.strip() if new_name else f"Location @ {new_x}, {new_z}"
                    loc_to_edit['name'] = final_new_name
                    loc_to_edit['x'] = new_x
                    loc_to_edit['y'] = new_y
                    loc_to_edit['z'] = new_z
                    loc_to_edit['description'] = new_desc
                    loc_to_edit['icon'] = new_icon_value
                    loc_to_edit['bg_color'] = new_bg_color
                    
                    loc_to_edit['image_paths'] = images_to_keep

                    if new_images_upload:
                        with st.spinner("Uploading..."):
                            for img_file in new_images_upload:
                                url = save_image(img_file)
                                if url:
                                    loc_to_edit['image_paths'].append(url)
                    
                    save_data(st.session_state.locations)
                    st.session_state.edit_mode = False
                    st.session_state.edit_id = None
                    st.success("Updated!")
                    st.rerun()
                
                c_cancel, c_delete = st.columns([1, 1])
                with c_cancel:
                    if st.button("Cancel"):
                        st.session_state.edit_mode = False
                        st.session_state.edit_id = None
                        st.rerun()
                
                with c_delete:
                    if st.button("Delete", type="primary"):
                        st.session_state.locations.pop(edit_index)
                        save_data(st.session_state.locations)
                        
                        st.session_state.edit_mode = False
                        st.session_state.edit_id = None
                        st.success("Deleted!")
                        st.rerun()

            else:
                st.error("Location not found.")
                st.session_state.edit_mode = False
                st.rerun()

        # Normal Details View
        elif selected_ids:
            # Filter DF by selected ID (Handling multiple selections by showing first or list)
            # Default to showing the first selected one for simplicity in side-panel
            
            selected_id = selected_ids[0]
            loc_data = next((item for item in st.session_state.locations if item["id"] == selected_id), None)
            
            if loc_data:
                # Icon + Name
                icon_display = loc_data.get('icon', 'Default')
                if icon_display == 'Default': icon_display = '📍'
                
                st.markdown(f"### {icon_display} {loc_data['name']}")
                
                # Image Carousel
                image_paths = loc_data.get("image_paths", [])
                if image_paths:
                    if len(image_paths) == 1:
                        st.image(image_paths[0], use_column_width=True)
                    else:
                        tabs = st.tabs([f"Img {i+1}" for i in range(len(image_paths))])
                        for i, tab in enumerate(tabs):
                            tab.image(image_paths[i], use_column_width=True)

                st.markdown(f"**Coords**: `{loc_data['x']}, {loc_data['y']}, {loc_data['z']}`")
                
                if loc_data["description"]:
                    st.markdown("**Description:**")
                    st.write(loc_data["description"])
                
                st.caption(f"ID: {loc_data['id']}")
                
                if st.button("📝 Edit", key=f"btn_edit_{loc_data['id']}"):
                    st.session_state.edit_mode = True
                    st.session_state.edit_id = loc_data['id']
                    st.rerun()
                
                if len(selected_ids) > 1:
                    st.info(f"And {len(selected_ids)-1} other locations selected.")

        else:
            st.info("Select a location on the map to see details here.")
            
            with st.expander("List View"):
                st.dataframe(df[["name", "x", "z", "icon"]], height=200)

else:
    st.info("No locations recorded yet. Use the sidebar to add your first discovery!")
