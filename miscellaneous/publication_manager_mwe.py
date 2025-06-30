import streamlit as st
import json
import sqlite3
import os
import tempfile
import datetime
import copy

# Normalize publication data
def normalize_publications(data):
    if 'publications' not in data or not isinstance(data['publications'], dict):
        data['publications'] = {"under_review": [], "by_year": {}}
    if 'under_review' not in data['publications']:
        data['publications']['under_review'] = []
    if 'by_year' not in data['publications']:
        data['publications']['by_year'] = {}
    for pub in data['publications']['under_review']:
        for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
            if key not in pub:
                pub[key] = ""
    for year, pubs in data['publications']['by_year'].items():
        for pub in pubs:
            for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
                if key not in pub:
                    pub[key] = ""
    return data

# Initialize expander states
def initialize_expander_states(data):
    expanded = {}
    for i, _ in enumerate(data['publications']['under_review']):
        expanded[f"under_review_{i}"] = False
    for year, pubs in data['publications']['by_year'].items():
        for i, _ in enumerate(pubs):
            expanded[f"pub_{year}_{i}"] = False
    return expanded

# Save to sqlite3 db
def create_new_db(json_content):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    db_filename = f"publications_{timestamp}.db"
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cv_files (
            filename TEXT PRIMARY KEY,
            content TEXT,
            created_at TEXT
        )
    ''')
    current_time = datetime.datetime.now().isoformat()
    cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                  ("cv_data.json", json_content, current_time))
    conn.commit()
    conn.close()
    with open(db_filename, "rb") as f:
        db_content = f.read()
    return db_filename, db_content

# Default structure
default_data = {
    "publications": {
        "under_review": [],
        "by_year": {}
    },
    "last_updated": ""
}

# Initialize session state safely
if "data" not in st.session_state:
    st.session_state["data"] = copy.deepcopy(default_data)

if "expanded_publications" not in st.session_state:
    st.session_state["expanded_publications"] = initialize_expander_states(st.session_state["data"])

# --- Streamlit UI ---
st.title("📚 Simple Publication Manager")

# Upload Section
st.sidebar.header("📥 Upload Database")
db_file = st.sidebar.file_uploader("Upload Publication Database (.db)", type=["db"])

if db_file:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db.write(db_file.read())
        tmp_db_path = tmp_db.name

    try:
        conn = sqlite3.connect(tmp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT filename, content FROM cv_files WHERE filename = 'cv_data.json'")
        files = cursor.fetchall()
        conn.close()
        os.unlink(tmp_db_path)

        for filename, content in files:
            if filename == "cv_data.json":
                loaded_data = json.loads(content)
                loaded_data = normalize_publications(loaded_data)

                # Replace session state only if valid
                st.session_state["data"] = loaded_data
                st.session_state["expanded_publications"] = initialize_expander_states(loaded_data)

                st.success("✅ Database loaded successfully!")

    except Exception as e:
        st.error(f"❌ Failed to load database: {e}")

# Publications Section
st.header("📝 Publications")
st.subheader("📄 Under Review")

# Add new under-review publication
with st.form(key="under_review_form"):
    if st.form_submit_button("➕ Add Publication"):
        st.session_state["data"]["publications"]["under_review"].append({
            "authors": "", "title": "", "journal": "", "url": "", "impact_factor": "", "citations": ""
        })
        i = len(st.session_state["data"]["publications"]["under_review"]) - 1
        st.session_state["expanded_publications"][f"under_review_{i}"] = True
        st.rerun()

# Editable publications
for i, pub in enumerate(st.session_state["data"]["publications"]["under_review"]):
    if f"under_review_{i}" not in st.session_state["expanded_publications"]:
        st.session_state["expanded_publications"][f"under_review_{i}"] = False
    with st.expander(f"Publication {i+1}", expanded=st.session_state["expanded_publications"][f"under_review_{i}"]):
        with st.form(key=f"under_review_edit_form_{i}"):
            authors = st.text_input("Authors", value=pub["authors"], key=f"pub_authors_{i}")
            title = st.text_input("Title", value=pub["title"], key=f"pub_title_{i}")
            journal = st.text_input("Journal", value=pub["journal"], key=f"pub_journal_{i}")
            url = st.text_input("URL", value=pub["url"], key=f"pub_url_{i}")
            impact = st.text_input("Impact Factor", value=pub["impact_factor"], key=f"pub_impact_{i}")
            citations = st.text_input("Citations", value=pub["citations"], key=f"pub_citations_{i}")
            if st.form_submit_button(f"✅ Update Publication {i+1}"):
                st.session_state["data"]["publications"]["under_review"][i].update({
                    "authors": authors,
                    "title": title,
                    "journal": journal,
                    "url": url,
                    "impact_factor": impact,
                    "citations": citations
                })
                st.session_state["expanded_publications"][f"under_review_{i}"] = True
                st.success(f"✔️ Publication {i+1} updated!")

# Save and Download
st.header("💾 Save and Download")
if st.button("💾 Save Data"):
    st.session_state["data"]["last_updated"] = datetime.datetime.now().isoformat()
    json_content = json.dumps(st.session_state["data"], indent=4)

    with open("publications.json", "w") as f:
        f.write(json_content)
    st.success("✅ Data saved to publications.json")

    db_filename, db_content = create_new_db(json_content)
    st.download_button(
        label=f"⬇️ Download Database ({db_filename})",
        data=db_content,
        file_name=db_filename,
        mime="application/octet-stream"
    )

