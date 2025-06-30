import streamlit as st
import json
import sqlite3
import os
import tempfile
import datetime
import copy
import uuid

# Normalize publication data to ensure correct structure
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

# Initialize expander states for publications
def initialize_expander_states(data, session_id):
    expanded_publications = {}
    for i, _ in enumerate(data['publications']['under_review']):
        expanded_publications[f"under_review_{i}_{session_id}"] = False
    for year, pubs in data['publications']['by_year'].items():
        for i, _ in enumerate(pubs):
            expanded_publications[f"pub_{year}_{i}_{session_id}"] = False
    return expanded_publications

# Synchronize widget states with data
def sync_widget_states(data, session_id):
    for i, pub in enumerate(data['publications']['under_review']):
        for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
            st.session_state[f"pub_under_{key}_{i}_{session_id}"] = pub[key]
    for year, pubs in data['publications']['by_year'].items():
        for i, pub in enumerate(pubs):
            for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
                st.session_state[f"pub_{year}_{key}_{i}_{session_id}"] = pub[key]

# Create new database with updated data
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

# Default data structure
default_data = {
    "publications": {
        "under_review": [],
        "by_year": {}
    },
    "last_updated": ""
}

# Initialize session state
if "data" not in st.session_state:
    st.session_state["data"] = copy.deepcopy(default_data)
if "expanded_publications" not in st.session_state:
    st.session_state["expanded_publications"] = {}
if "session_id" not in st.session_state:
    st.session_state["session_id"] = str(uuid.uuid4())
if "add_under_review_clicked" not in st.session_state:
    st.session_state["add_under_review_clicked"] = False
if "add_pub_year_clicked" not in st.session_state:
    st.session_state["add_pub_year_clicked"] = False

# Streamlit app
st.title("Publication Manager MWE")

# Reset session state for testing
st.sidebar.header("Testing Controls")
if st.sidebar.button("Reset Session State (For Testing)"):
    for key in list(st.session_state.keys()):
        if key not in ["data", "expanded_publications", "session_id", "add_under_review_clicked", "add_pub_year_clicked"]:
            del st.session_state[key]
    st.session_state["data"] = copy.deepcopy(default_data)
    st.session_state["expanded_publications"] = {}
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["add_under_review_clicked"] = False
    st.session_state["add_pub_year_clicked"] = False
    st.rerun()

# Upload database
st.sidebar.header("Upload Publication Database")
db_file = st.sidebar.file_uploader("Upload CV Database (.db)", type=["db"], key=f"db_uploader_{st.session_state['session_id']}")
if db_file:
    # Clear all widget-related states to prevent conflicts
    for key in list(st.session_state.keys()):
        if key.startswith("pub_") or key.startswith("add_") or key.startswith("remove_") or key.startswith("toggle_") or key.startswith("db_uploader_"):
            del st.session_state[key]
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db.write(db_file.read())
        tmp_db_path = tmp_db.name
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT filename, content FROM cv_files WHERE filename = 'cv_data.json'")
    files = cursor.fetchall()
    conn.close()
    os.unlink(tmp_db_path)
    
    for filename, content in files:
        if filename == "cv_data.json":
            try:
                loaded_data = json.loads(content)
                st.session_state["session_id"] = str(uuid.uuid4())
                st.session_state["data"] = normalize_publications(loaded_data)
                st.session_state["expanded_publications"] = initialize_expander_states(st.session_state["data"], st.session_state["session_id"])
                sync_widget_states(st.session_state["data"], st.session_state["session_id"])
                st.session_state["add_under_review_clicked"] = False
                st.session_state["add_pub_year_clicked"] = False
                st.success("Database loaded successfully!")
                st.sidebar.write("Loaded publications:", st.session_state["data"]["publications"])
                st.sidebar.write("Expanded publications state:", st.session_state["expanded_publications"])
            except json.JSONDecodeError:
                st.error("Invalid JSON in database for cv_data.json")
    st.rerun()

# Publications section
st.header("Publications")

# Under Review section
st.subheader("Under Review")
if st.button("Add Publication Under Review", key=f"add_under_review_{st.session_state['session_id']}"):
    new_pub = {
        "authors": "", "title": "", "journal": "", "url": "", "impact_factor": "", "citations": ""
    }
    st.session_state["data"]["publications"]["under_review"].append(new_pub)
    index = len(st.session_state["data"]["publications"]["under_review"]) - 1
    st.session_state["expanded_publications"][f"under_review_{index}_{st.session_state['session_id']}"] = True
    for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
        st.session_state[f"pub_under_{key}_{index}_{st.session_state['session_id']}"] = new_pub[key]
    st.session_state["add_under_review_clicked"] = True
    st.success("New publication added under review!")
    st.rerun()

for i, pub in enumerate(st.session_state["data"]["publications"]["under_review"]):
    key = f"under_review_{i}_{st.session_state['session_id']}"
    if key not in st.session_state["expanded_publications"]:
        st.session_state["expanded_publications"][key] = False
    with st.expander(f"Publication Under Review {i+1}", expanded=st.session_state["expanded_publications"][key]):
        with st.form(key=f"under_review_edit_form_{i}_{st.session_state['session_id']}"):
            authors = st.text_input("Authors", value=pub["authors"], key=f"pub_under_authors_{i}_{st.session_state['session_id']}")
            title = st.text_input("Title", value=pub["title"], key=f"pub_under_title_{i}_{st.session_state['session_id']}")
            journal = st.text_input("Journal", value=pub["journal"], key=f"pub_under_journal_{i}_{st.session_state['session_id']}")
            url = st.text_input("URL", value=pub["url"], key=f"pub_under_url_{i}_{st.session_state['session_id']}")
            impact_factor = st.text_input("Impact Factor", value=pub["impact_factor"], key=f"pub_under_if_{i}_{st.session_state['session_id']}")
            citations = st.text_input("Citations", value=pub["citations"], key=f"pub_under_citations_{i}_{st.session_state['session_id']}")
            if st.form_submit_button(f"Update Publication {i+1}"):
                st.session_state["data"]["publications"]["under_review"][i].update({
                    "authors": authors,
                    "title": title,
                    "journal": journal,
                    "url": url,
                    "impact_factor": impact_factor,
                    "citations": citations
                })
                st.session_state["expanded_publications"][key] = True
                st.success(f"Publication {i+1} updated!")
                st.rerun()
        if st.button(f"Remove Publication {i+1}", key=f"remove_pub_under_{i}_{st.session_state['session_id']}"):
            st.session_state["data"]["publications"]["under_review"].pop(i)
            del st.session_state["expanded_publications"][key]
            for j in range(i, len(st.session_state["data"]["publications"]["under_review"])):
                old_key = f"under_review_{j+1}_{st.session_state['session_id']}"
                new_key = f"under_review_{j}_{st.session_state['session_id']}"
                if old_key in st.session_state["expanded_publications"]:
                    st.session_state["expanded_publications"][new_key] = st.session_state["expanded_publications"].pop(old_key)
                for field in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
                    old_widget_key = f"pub_under_{field}_{j+1}_{st.session_state['session_id']}"
                    new_widget_key = f"pub_under_{field}_{j}_{st.session_state['session_id']}"
                    if old_widget_key in st.session_state:
                        st.session_state[new_widget_key] = st.session_state.pop(old_widget_key)
            st.rerun()
        if st.button(f"{'Collapse' if st.session_state['expanded_publications'][key] else 'Expand'} Publication {i+1}", key=f"toggle_under_{i}_{st.session_state['session_id']}"):
            st.session_state["expanded_publications"][key] = not st.session_state["expanded_publications"][key]
            st.rerun()

# Published by Year section
st.subheader("Published by Year")
year_input = st.text_input("Year for New Publication", key=f"pub_year_{st.session_state['session_id']}")
if st.button("Add Publication for Year", key=f"add_pub_year_{st.session_state['session_id']}"):
    if year_input and year_input.isdigit():
        year = year_input
        if year not in st.session_state["data"]["publications"]["by_year"]:
            st.session_state["data"]["publications"]["by_year"][year] = []
        new_pub = {
            "authors": "", "title": "", "journal": "", "url": "", "impact_factor": "", "citations": ""
        }
        st.session_state["data"]["publications"]["by_year"][year].append(new_pub)
        index = len(st.session_state["data"]["publications"]["by_year"][year]) - 1
        st.session_state["expanded_publications"][f"pub_{year}_{index}_{st.session_state['session_id']}"] = True
        for key in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
            st.session_state[f"pub_{year}_{key}_{index}_{st.session_state['session_id']}"] = new_pub[key]
        st.session_state["add_pub_year_clicked"] = True
        st.success(f"New publication added for year {year}!")
        st.rerun()
    else:
        st.error("Please enter a valid year (digits only)")

for year in sorted(st.session_state["data"]["publications"]["by_year"].keys(), reverse=True):
    st.markdown(f"### Year {year}")
    for i, pub in enumerate(st.session_state["data"]["publications"]["by_year"][year]):
        key = f"pub_{year}_{i}_{st.session_state['session_id']}"
        if key not in st.session_state["expanded_publications"]:
            st.session_state["expanded_publications"][key] = False
        with st.expander(f"Publication {i+1} (Year {year})", expanded=st.session_state["expanded_publications"][key]):
            with st.form(key=f"pub_year_edit_form_{year}_{i}_{st.session_state['session_id']}"):
                authors = st.text_input("Authors", value=pub["authors"], key=f"pub_{year}_authors_{i}_{st.session_state['session_id']}")
                title = st.text_input("Title", value=pub["title"], key=f"pub_{year}_title_{i}_{st.session_state['session_id']}")
                journal = st.text_input("Journal", value=pub["journal"], key=f"pub_{year}_journal_{i}_{st.session_state['session_id']}")
                url = st.text_input("URL", value=pub["url"], key=f"pub_{year}_url_{i}_{st.session_state['session_id']}")
                impact_factor = st.text_input("Impact Factor", value=pub["impact_factor"], key=f"pub_{year}_if_{i}_{st.session_state['session_id']}")
                citations = st.text_input("Citations", value=pub["citations"], key=f"pub_{year}_citations_{i}_{st.session_state['session_id']}")
                if st.form_submit_button(f"Update Publication {i+1}"):
                    st.session_state["data"]["publications"]["by_year"][year][i].update({
                        "authors": authors,
                        "title": title,
                        "journal": journal,
                        "url": url,
                        "impact_factor": impact_factor,
                        "citations": citations
                    })
                    st.session_state["expanded_publications"][key] = True
                    st.success(f"Publication {i+1} for year {year} updated!")
                    st.rerun()
            if st.button(f"Remove Publication {i+1} (Year {year})", key=f"remove_pub_{year}_{i}_{st.session_state['session_id']}"):
                st.session_state["data"]["publications"]["by_year"][year].pop(i)
                del st.session_state["expanded_publications"][key]
                for j in range(i, len(st.session_state["data"]["publications"]["by_year"][year])):
                    old_key = f"pub_{year}_{j+1}_{st.session_state['session_id']}"
                    new_key = f"pub_{year}_{j}_{st.session_state['session_id']}"
                    if old_key in st.session_state["expanded_publications"]:
                        st.session_state["expanded_publications"][new_key] = st.session_state["expanded_publications"].pop(old_key)
                    for field in ["authors", "title", "journal", "url", "impact_factor", "citations"]:
                        old_widget_key = f"pub_{year}_{field}_{j+1}_{st.session_state['session_id']}"
                        new_widget_key = f"pub_{year}_{field}_{j}_{st.session_state['session_id']}"
                        if old_widget_key in st.session_state:
                            st.session_state[new_widget_key] = st.session_state.pop(old_widget_key)
                if not st.session_state["data"]["publications"]["by_year"][year]:
                    del st.session_state["data"]["publications"]["by_year"][year]
                st.rerun()
            if st.button(f"{'Collapse' if st.session_state['expanded_publications'][key] else 'Expand'} Publication {i+1}", key=f"toggle_pub_{year}_{i}_{st.session_state['session_id']}"):
                st.session_state["expanded_publications"][key] = not st.session_state["expanded_publications"][key]
                st.rerun()

# Debug output
st.write("Current publications:", st.session_state["data"]["publications"])
st.write("Expanded publications state:", st.session_state["expanded_publications"])
st.write("Button states:", {
    f"add_under_review_{st.session_state['session_id']}": st.session_state.get("add_under_review_clicked", False),
    f"add_pub_year_{st.session_state['session_id']}": st.session_state.get("add_pub_year_clicked", False)
})
st.write("Sample widget states:", {
    f"pub_under_authors_0_{st.session_state['session_id']}": st.session_state.get(f"pub_under_authors_0_{st.session_state['session_id']}", "Not set")
})

# Save and Download section
st.header("Save and Download")
col1, col2 = st.columns(2)
with col1:
    if st.button("Save Data to JSON"):
        st.session_state["data"]["last_updated"] = datetime.datetime.now().isoformat()
        json_content = json.dumps(st.session_state["data"], indent=4)
        with open("publications.json", "w") as f:
            f.write(json_content)
        st.success("Data saved to publications.json")
with col2:
    json_content = json.dumps(st.session_state["data"], indent=4)
    st.download_button("Download JSON", json_content, file_name="publications.json", mime="text/json")
    db_filename, db_content = create_new_db(json_content)
    st.download_button(f"Download Database ({db_filename})", db_content, file_name=db_filename, mime="application/octet-stream")

