import streamlit as st
import cloudinary
import cloudinary.uploader
import cloudinary.api

def init_cloudinary():
    """Initializes Cloudinary configuration from secrets."""
    try:
        cloudinary.config(
            cloud_name = st.secrets["cloudinary"]["cloud_name"],
            api_key = st.secrets["cloudinary"]["api_key"],
            api_secret = st.secrets["cloudinary"]["api_secret"],
            secure = True
        )
        return True
    except Exception as e:
        st.error(f"Cloudinary configuration error: {e}")
        return False

def upload_image(image_file):
    """
    Uploads an image to Cloudinary.
    Returns the secure URL of the uploaded image or None if failed.
    """
    if not init_cloudinary():
        return None

    try:
        # Determine if it's a file-like object or bytes
        # Cloudinary's upload function handles file-like objects directly
        response = cloudinary.uploader.upload(image_file)
        
        return response.get("secure_url")
            
    except Exception as e:
        # Debugging: Print more details
        st.error(f"Error uploading to Cloudinary: {type(e).__name__} - {e}")
        # Check if secrets are loaded
        try:
             cloud_name = st.secrets["cloudinary"]["cloud_name"]
             st.error(f"Secrets loaded. Cloud name: {cloud_name}")
        except:
             st.error("Could not load Cloudinary secrets.")
        return None
