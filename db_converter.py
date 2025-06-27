import streamlit as st
import sqlite3
import datetime
import os

st.title("CV Database Converter")

# File uploaders
json_file = st.file_uploader("Upload cv_data.json", type=["json"])
tex_file = st.file_uploader("Upload cv_template.tex", type=["tex"])
sty_file = st.file_uploader("Upload cv_style.sty", type=["sty"])

if st.button("Create Database"):
    if json_file and tex_file and sty_file:
        # Read file contents
        json_content = json_file.read().decode("utf-8")
        tex_content = tex_file.read().decode("utf-8")
        sty_content = sty_file.read().decode("utf-8")

        # Generate timestamp for filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
        db_filename = f"cv{timestamp}.db"

        # Create SQLite database
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()

        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cv_files (
                filename TEXT PRIMARY KEY,
                content TEXT,
                created_at TEXT
            )
        ''')

        # Insert file contents
        current_time = datetime.datetime.now().isoformat()
        cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                      ("cv_data.json", json_content, current_time))
        cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                      ("cv_template.tex", tex_content, current_time))
        cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                      ("cv_style.sty", sty_content, current_time))

        conn.commit()
        conn.close()

        # Provide download link for the database
        with open(db_filename, "rb") as f:
            st.download_button(f"Download {db_filename}", f, file_name=db_filename, mime="application/octet-stream")
        st.success(f"Database {db_filename} created successfully!")
    else:
        st.error("Please upload all three files: cv_data.json, cv_template.tex, and cv_style.sty.")