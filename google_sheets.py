import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json

# Scopes required for the API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_gspread_client():
    """Authenticates and returns a gspread client using Streamlit secrets."""
    try:
        # Load credentials from secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # fix formatting of private key if necessary (replace \n with actual newlines)
        if "\\n" in creds_dict["private_key"]:
             creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=SCOPES
        )
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"Failed to authenticate with Google Sheets: {e}")
        return None

def get_worksheet():
    """Opens the spreadsheet and returns the first worksheet."""
    client = get_gspread_client()
    if not client:
        return None
    
    try:
        # Remove any leading/trailing whitespace
        sheet_id = str(st.secrets["sheets"]["spreadsheet_id"]).strip()
        
        # Debug: Show masked ID
        masked_id = f"{sheet_id[:5]}...{sheet_id[-5:]}" if len(sheet_id) > 10 else sheet_id
        st.info(f"Using Spreadsheet ID/URL: {masked_id}")

        # Debug: Show which email is trying to access
        try:
            email = st.secrets["gcp_service_account"]["client_email"]
            # st.info(f"Attempting to access with email: {email}") # Commented out to reduce clutter
        except:
             pass
        
        try:
             # Try to open by the configured ID/URL
            if sheet_id.startswith("http"):
                sh = client.open_by_url(sheet_id)
            else:
                sh = client.open_by_key(sheet_id)
            return sh.sheet1
            
        except Exception as open_err:
            # Fallback: If specific ID failed, look at what we CAN see
            st.warning(f"Could not open by ID ({sheet_id[:5]}...). Checking accessible sheets...")
            
            try:
                accessible = client.openall()
                if accessible:
                    target_sheet = accessible[0]
                    st.success(f"Found accessible sheet: '{target_sheet.title}'. Using this one!")
                    st.info(f"👉 Recommended: Update your secrets.toml with this ID: {target_sheet.id}")
                    return target_sheet.sheet1
                else:
                     st.error("No accessible sheets found. Please share your sheet with the email above.")
                     return None
            except Exception as e:
                st.error(f"Error checking accessible sheets: {e}")
                return None

    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None

def load_data():
    """Loads all data from the Google Sheet and returns it as a list of dicts."""
    worksheet = get_worksheet()
    if not worksheet:
        return []
    
    try:
        records = worksheet.get_all_records()
        
        # Post-processing: Handle JSON fields (image_paths)
        cleaned_records = []
        for row in records:
            # Ensure image_paths is a list
            if "image_paths" in row and isinstance(row["image_paths"], str):
                try:
                    # Try parsing as JSON if it looks like a list
                    if row["image_paths"].startswith("["):
                        row["image_paths"] = json.loads(row["image_paths"])
                    elif row["image_paths"]:
                         # Fallback for comma separated or single url
                        row["image_paths"] = [url.strip() for url in row["image_paths"].split(",") if url.strip()]
                    else:
                        row["image_paths"] = []
                except:
                    row["image_paths"] = []
            
            # Ensure missing coordinates are properly cast to None instead of empty strings
            for col in ["x", "y", "z"]:
                if col in row and row[col] == "":
                    row[col] = None

            cleaned_records.append(row)
            
        return cleaned_records
    except Exception as e:
        st.error(f"Error reading data from Google Sheet: {e}")
        return []

def save_all_data(data):
    """
    Overwrites the Google Sheet with the provided data.
    Note: For production apps with many users, simple overwrite is risky (race conditions).
    For a personal/small team tool, this is acceptable.
    """
    worksheet = get_worksheet()
    if not worksheet:
        return False
    
    try:
        if not data:
            worksheet.clear()
            return True

        # Prepare data for upload
        # We need to serialize lists (like image_paths) to strings/JSON
        df = pd.DataFrame(data)
        
        # Ensure consistent columns
        required_cols = ["id", "name", "x", "y", "z", "description", "icon", "image_paths"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = "" # Fill missing columns
        
        # Convert image_paths list to JSON string for storage
        df["image_paths"] = df["image_paths"].apply(lambda x: json.dumps(x) if isinstance(x, list) else "[]")
        
        # Replace NaN/None with empty strings to prevent Google Sheets API JSON serialization errors
        df = df.fillna("")
        
        # Update session state with the serialized version? No, we shouldn't touch the passed data object if possible.
        # But we made a new DF, so it's fine.

        # Clear and update
        worksheet.clear()
        
        # set_with_dataframe is from gspread-dataframe usually, but we are using pure gspread
        # gspread uses list of lists.
        # Header
        header = df.columns.tolist()
        # Values
        values = df.values.tolist()
        
        # Update
        worksheet.update([header] + values)
        return True
        
    except Exception as e:
        st.error(f"Error saving data to Google Sheet: {e}")
        return False
