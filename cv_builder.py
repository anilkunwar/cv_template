import streamlit as st
import json
import os
import tempfile
import subprocess
import copy
import re
import sqlite3
import datetime
from jinja2 import Environment, FileSystemLoader
from pdf2image import convert_from_path
import base64
from io import BytesIO

# Utility function to escape LaTeX special characters
def escape_latex(text):
    if not isinstance(text, str):
        text = str(text)
    special_chars = {
        '&': r'\&',
        '%': r'\%',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
        '\\': r'\textbackslash{}'
    }
    for char, escaped in special_chars.items():
        text = text.replace(char, escaped)
    return text

# Validate URL format
def validate_url(url):
    regex = r'^(https?://)?[\w\-]+(\.[\w\-]+)+[/#?]?.*$'
    return bool(re.match(regex, url)) if url else True

# Validate required fields and URLs
def validate_data(data):
    errors = []
    if not data['personal_info']['name']:
        errors.append("Full Name is required.")
    if not data['languages']['mother_tongue']:
        errors.append("Mother Tongue is required.")
    for pub in data['publications']['under_review']:
        if pub['url'] and not validate_url(pub['url']):
            errors.append(f"Invalid URL in Under Review Publication: {pub['url']}")
    for year, pubs in data['publications']['by_year'].items():
        for pub in pubs:
            if pub['url'] and not validate_url(pub['url']):
                errors.append(f"Invalid URL in Publication (Year {year}): {pub['url']}")
    for year, confs in data['conference_proceedings'].items():
        for conf in confs:
            if conf['url'] and not validate_url(conf['url']):
                errors.append(f"Invalid URL in Conference Proceeding (Year {year}): {conf['url']}")
    for profile in data['academic_activities']['profiles']:
        if profile['url'] and not validate_url(profile['url']):
            errors.append(f"Invalid URL in Scholarly Profile: {profile['url']}")
    for talk in data['academic_activities']['talks']:
        if talk['url'] and not validate_url(talk['url']):
            errors.append(f"Invalid URL in Invited Talk: {talk['url']}")
    for edit in data['academic_activities']['editorial']:
        if edit['url'] and not validate_url(edit['url']):
            errors.append(f"Invalid URL in Editorial Work: {edit['url']}")
    for membership in data['memberships']:
        if membership['url'] and not validate_url(membership['url']):
            errors.append(f"Invalid URL in Membership: {membership['url']}")
    for software in data['skills']['softwares']:
        if software['url'] and not validate_url(software['url']):
            errors.append(f"Invalid URL in Software: {software['url']}")
    return errors

# Generate LaTeX CV and PDF, return file contents
def generate_latex_cv(data, tex_content, sty_content):
    with tempfile.TemporaryDirectory() as tmpdirname:
        with open(f"{tmpdirname}/cv_template.tex", "w") as f:
            f.write(tex_content)
        with open(f"{tmpdirname}/cv_style.sty", "w") as f:
            f.write(sty_content)
        env = Environment(loader=FileSystemLoader(tmpdirname), autoescape=False)
        env.filters['escape_latex'] = escape_latex
        template = env.get_template('cv_template.tex')
        generated_tex = template.render(data=data)
        tex_path = f"{tmpdirname}/cv.tex"
        with open(tex_path, "w") as f:
            f.write(generated_tex)
        pdf_content = None
        try:
            subprocess.run(['pdflatex', '-interaction=nonstopmode', 'cv.tex'], cwd=tmpdirname, check=True, capture_output=True)
            pdf_path = f"{tmpdirname}/cv.pdf"
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as f:
                    pdf_content = f.read()
        except (subprocess.CalledProcessError, FileNotFoundError):
            st.error("pdflatex not found or compilation failed. Please download the LaTeX file and compile it manually.")
        return generated_tex, pdf_content

# Convert PDF to images for preview
def pdf_to_images(pdf_content):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
        tmp_pdf.write(pdf_content)
        tmp_pdf_path = tmp_pdf.name
    images = convert_from_path(tmp_pdf_path)
    os.unlink(tmp_pdf_path)
    image_data = []
    for img in images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        image_data.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))
    return image_data

# Create new database with updated data
def create_new_db(json_content, tex_content, sty_content):
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M")
    db_filename = f"cv{timestamp}.db"
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
    cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                  ("cv_template.tex", tex_content, current_time))
    cursor.execute("INSERT OR REPLACE INTO cv_files (filename, content, created_at) VALUES (?, ?, ?)",
                  ("cv_style.sty", sty_content, current_time))
    conn.commit()
    conn.close()
    with open(db_filename, "rb") as f:
        db_content = f.read()
    return db_filename, db_content

# Streamlit app
st.title("CV Builder and Updater")

# Default data structure
default_data = {
    "personal_info": {"name": "", "nationality": "", "dob": "", "current_address": "", "permanent_address": "", "email": ""},
    "languages": {"mother_tongue": "", "english_listening": "C2 (proficient)", "english_reading": "C2 (proficient)", "english_speaking": "C2 (proficient)", "english_writing": "C2 (proficient)", "hindi_listening": "C2 (proficient)", "hindi_reading": "C2 (proficient)", "hindi_speaking": "C2 (proficient)", "hindi_writing": "C2 (proficient)"},
    "professional_experience": [],
    "education": [],
    "publications": {"under_review": [], "by_year": {}},
    "conference_proceedings": {},
    "book": {"authors": "", "title": "", "publisher": "", "year": "", "isbn": ""},
    "academic_activities": {"conferences": [], "talks": [], "editorial": [], "profiles": [], "reviews": [], "journals": []},
    "grants_awards": {"grants": [], "awards": []},
    "skills": {"h_index": "", "researchgate_score": "", "programming_languages": "", "softwares": [], "parallel_computing": "", "experiments": ""},
    "memberships": [],
    "last_updated": ""
}

# Initialize session state
if "data" not in st.session_state:
    st.session_state["data"] = copy.deepcopy(default_data)
if "tex_content" not in st.session_state:
    st.session_state["tex_content"] = ""
if "sty_content" not in st.session_state:
    st.session_state["sty_content"] = ""
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "Personal Info"

# Sidebar navigation
st.sidebar.header("Upload CV Database")
db_file = st.sidebar.file_uploader("Upload CV Database (.db)", type=["db"])
if db_file:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        tmp_db.write(db_file.read())
        tmp_db_path = tmp_db.name
    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT filename, content FROM cv_files")
    files = cursor.fetchall()
    conn.close()
    os.unlink(tmp_db_path)
    
    for filename, content in files:
        if filename == "cv_data.json":
            try:
                st.session_state["data"] = json.loads(content)
            except json.JSONDecodeError:
                st.error("Invalid JSON in database for cv_data.json")
        elif filename == "cv_template.tex":
            st.session_state["tex_content"] = content
        elif filename == "cv_style.sty":
            st.session_state["sty_content"] = content
    st.success("Database loaded successfully!")

st.sidebar.header("Navigate Sections")
tab_names = [
    "Personal Info", "Languages", "Professional Experience", "Education", "Publications",
    "Conference Proceedings", "Book", "Academic Activities", "Grants & Awards", "Skills & Memberships"
]
for tab_name in tab_names:
    if st.sidebar.button(tab_name, key=f"sidebar_{tab_name}"):
        st.session_state["active_tab"] = tab_name

# Main content area
st.header(st.session_state["active_tab"])
if st.session_state["active_tab"] == "Personal Info":
    st.session_state["data"]["personal_info"]["name"] = st.text_input("Full Name", value=st.session_state["data"]["personal_info"]["name"], key="name")
    st.session_state["data"]["personal_info"]["nationality"] = st.text_input("Nationality", value=st.session_state["data"]["personal_info"]["nationality"], key="nationality")
    st.session_state["data"]["personal_info"]["dob"] = st.text_input("Date of Birth", value=st.session_state["data"]["personal_info"]["dob"], key="dob")
    st.session_state["data"]["personal_info"]["current_address"] = st.text_input("Current Address", value=st.session_state["data"]["personal_info"]["current_address"], key="current_address")
    st.session_state["data"]["personal_info"]["permanent_address"] = st.text_input("Permanent Address", value=st.session_state["data"]["personal_info"]["permanent_address"], key="permanent_address")
    st.session_state["data"]["personal_info"]["email"] = st.text_input("Email", value=st.session_state["data"]["personal_info"]["email"], key="email")

elif st.session_state["active_tab"] == "Languages":
    st.session_state["data"]["languages"]["mother_tongue"] = st.text_input("Mother Tongue", value=st.session_state["data"]["languages"]["mother_tongue"], key="mother_tongue")
    st.subheader("English Proficiency")
    st.session_state["data"]["languages"]["english_listening"] = st.selectbox("English Listening", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["english_listening"]), key="english_listening")
    st.session_state["data"]["languages"]["english_reading"] = st.selectbox("English Reading", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["english_reading"]), key="english_reading")
    st.session_state["data"]["languages"]["english_speaking"] = st.selectbox("English Speaking", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["english_speaking"]), key="english_speaking")
    st.session_state["data"]["languages"]["english_writing"] = st.selectbox("English Writing", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["english_writing"]), key="english_writing")
    st.subheader("Hindi Proficiency")
    st.session_state["data"]["languages"]["hindi_listening"] = st.selectbox("Hindi Listening", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["hindi_listening"]), key="hindi_listening")
    st.session_state["data"]["languages"]["hindi_reading"] = st.selectbox("Hindi Reading", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["hindi_reading"]), key="hindi_reading")
    st.session_state["data"]["languages"]["hindi_speaking"] = st.selectbox("Hindi Speaking", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["hindi_speaking"]), key="hindi_speaking")
    st.session_state["data"]["languages"]["hindi_writing"] = st.selectbox("Hindi Writing", ["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"], index=["C2 (proficient)", "C1 (proficient)", "B2 (independent)", "B1 (independent)", "A2 (basic)", "A1 (basic)"].index(st.session_state["data"]["languages"]["hindi_writing"]), key="hindi_writing")

elif st.session_state["active_tab"] == "Professional Experience":
    if st.button("Add Professional Experience", key="add_exp"):
        st.session_state["data"]["professional_experience"].append({
            "duration": "", "position": "", "employer": "", "activity": ""
        })
    for i, exp in enumerate(st.session_state["data"]["professional_experience"]):
        with st.expander(f"Experience {i+1}"):
            exp["duration"] = st.text_input(f"Duration (e.g., 01/06/2021--Present)", value=exp["duration"], key=f"exp_duration_{i}")
            exp["position"] = st.text_input(f"Position", value=exp["position"], key=f"exp_position_{i}")
            exp["employer"] = st.text_input(f"Employer", value=exp["employer"], key=f"exp_employer_{i}")
            exp["activity"] = st.text_area(f"Activity", value=exp["activity"], key=f"exp_activity_{i}")
            if st.button(f"Remove Experience {i+1}", key=f"remove_exp_{i}"):
                st.session_state["data"]["professional_experience"].pop(i)
                st.rerun()

elif st.session_state["active_tab"] == "Education":
    if st.button("Add Education Entry", key="add_edu"):
        st.session_state["data"]["education"].append({
            "duration": "", "qualification": "", "thesis_title": "", "organization": ""
        })
    for i, edu in enumerate(st.session_state["data"]["education"]):
        with st.expander(f"Education {i+1}"):
            edu["duration"] = st.text_input(f"Duration (e.g., 09/2012--06/2016)", value=edu["duration"], key=f"edu_duration_{i}")
            edu["qualification"] = st.text_input(f"Qualification", value=edu["qualification"], key=f"edu_qualification_{i}")
            edu["thesis_title"] = st.text_input(f"Thesis Title", value=edu["thesis_title"], key=f"edu_thesis_{i}")
            edu["organization"] = st.text_input(f"Organization", value=edu["organization"], key=f"edu_organization_{i}")
            if st.button(f"Remove Education {i+1}", key=f"remove_edu_{i}"):
                st.session_state["data"]["education"].pop(i)
                st.rerun()

elif st.session_state["active_tab"] == "Publications":
    st.subheader("Under Review")
    if st.button("Add Publication Under Review", key="add_pub_under"):
        st.session_state["data"]["publications"]["under_review"].append({
            "authors": "", "title": "", "journal": "", "url": "", "impact_factor": "", "citations": ""
        })
    for i, pub in enumerate(st.session_state["data"]["publications"]["under_review"]):
        with st.expander(f"Publication Under Review {i+1}"):
            pub["authors"] = st.text_input(f"Authors", value=pub["authors"], key=f"pub_under_authors_{i}")
            pub["title"] = st.text_input(f"Title", value=pub["title"], key=f"pub_under_title_{i}")
            pub["journal"] = st.text_input(f"Journal", value=pub["journal"], key=f"pub_under_journal_{i}")
            pub["url"] = st.text_input(f"URL", value=pub["url"], key=f"pub_under_url_{i}")
            pub["impact_factor"] = st.text_input(f"Impact Factor", value=pub["impact_factor"], key=f"pub_under_if_{i}")
            pub["citations"] = st.text_input(f"Citations", value=pub["citations"], key=f"pub_under_citations_{i}")
            if st.button(f"Remove Publication Under Review {i+1}", key=f"remove_pub_under_{i}"):
                st.session_state["data"]["publications"]["under_review"].pop(i)
                st.rerun()
    st.subheader("Published by Year")
    year = st.text_input("Year for New Publication", key="pub_year")
    if st.button("Add Publication for Year", key="add_pub_year"):
        if year and year.isdigit():
            if year not in st.session_state["data"]["publications"]["by_year"]:
                st.session_state["data"]["publications"]["by_year"][year] = []
            st.session_state["data"]["publications"]["by_year"][year].append({
                "authors": "", "title": "", "journal": "", "url": "", "impact_factor": "", "citations": ""
            })
    for year in sorted(st.session_state["data"]["publications"]["by_year"].keys(), reverse=True):
        with st.expander(f"Year {year}"):
            for i, pub in enumerate(st.session_state["data"]["publications"]["by_year"][year]):
                st.subheader(f"Publication {i+1}")
                pub["authors"] = st.text_input(f"Authors (Year {year})", value=pub["authors"], key=f"pub_{year}_authors_{i}")
                pub["title"] = st.text_input(f"Title", value=pub["title"], key=f"pub_{year}_title_{i}")
                pub["journal"] = st.text_input(f"Journal", value=pub["journal"], key=f"pub_{year}_journal_{i}")
                pub["url"] = st.text_input(f"URL", value=pub["url"], key=f"pub_{year}_url_{i}")
                pub["impact_factor"] = st.text_input(f"Impact Factor", value=pub["impact_factor"], key=f"pub_{year}_if_{i}")
                pub["citations"] = st.text_input(f"Citations", value=pub["citations"], key=f"pub_{year}_citations_{i}")
                if st.button(f"Remove Publication {i+1} (Year {year})", key=f"remove_pub_{year}_{i}"):
                    st.session_state["data"]["publications"]["by_year"][year].pop(i)
                    if not st.session_state["data"]["publications"]["by_year"][year]:
                        del st.session_state["data"]["publications"]["by_year"][year]
                    st.rerun()

elif st.session_state["active_tab"] == "Conference Proceedings":
    conf_year = st.text_input("Year for New Conference Proceeding", key="conf_year")
    if st.button("Add Conference Proceeding", key="add_conf"):
        if conf_year and conf_year.isdigit():
            if conf_year not in st.session_state["data"]["conference_proceedings"]:
                st.session_state["data"]["conference_proceedings"][conf_year] = []
            st.session_state["data"]["conference_proceedings"][conf_year].append({
                "authors": "", "title": "", "venue": "", "url": "", "citations": ""
            })
    for year in sorted(st.session_state["data"]["conference_proceedings"].keys(), reverse=True):
        with st.expander(f"Year {year}"):
            for i, conf in enumerate(st.session_state["data"]["conference_proceedings"][year]):
                st.subheader(f"Conference Proceeding {i+1}")
                conf["authors"] = st.text_input(f"Authors (Year {year})", value=conf["authors"], key=f"conf_{year}_authors_{i}")
                conf["title"] = st.text_input(f"Title", value=conf["title"], key=f"conf_{year}_title_{i}")
                conf["venue"] = st.text_input(f"Venue", value=conf["venue"], key=f"conf_{year}_venue_{i}")
                conf["url"] = st.text_input(f"URL", value=conf["url"], key=f"conf_{year}_url_{i}")
                conf["citations"] = st.text_input(f"Citations", value=conf["citations"], key=f"conf_{year}_citations_{i}")
                if st.button(f"Remove Conference Proceeding {i+1} (Year {year})", key=f"remove_conf_{year}_{i}"):
                    st.session_state["data"]["conference_proceedings"][year].pop(i)
                    if not st.session_state["data"]["conference_proceedings"][year]:
                        del st.session_state["data"]["conference_proceedings"][year]
                    st.rerun()

elif st.session_state["active_tab"] == "Book":
    st.session_state["data"]["book"]["authors"] = st.text_input("Book Authors", value=st.session_state["data"]["book"]["authors"], key="book_authors")
    st.session_state["data"]["book"]["title"] = st.text_input("Book Title", value=st.session_state["data"]["book"]["title"], key="book_title")
    st.session_state["data"]["book"]["publisher"] = st.text_input("Publisher", value=st.session_state["data"]["book"]["publisher"], key="book_publisher")
    st.session_state["data"]["book"]["year"] = st.text_input("Year", value=st.session_state["data"]["book"]["year"], key="book_year")
    st.session_state["data"]["book"]["isbn"] = st.text_input("ISBN", value=st.session_state["data"]["book"]["isbn"], key="book_isbn")

elif st.session_state["active_tab"] == "Academic Activities":
    st.subheader("International Conferences")
    if st.button("Add Conference", key="add_conf_activity"):
        st.session_state["data"]["academic_activities"]["conferences"].append({
            "date": "", "role": "", "event": "", "url": ""
        })
    for i, conf in enumerate(st.session_state["data"]["academic_activities"]["conferences"]):
        with st.expander(f"Conference {i+1}"):
            conf["date"] = st.text_input(f"Date", value=conf["date"], key=f"conf_date_{i}")
            conf["role"] = st.text_input(f"Role", value=conf["role"], key=f"conf_role_{i}")
            conf["event"] = st.text_input(f"Event", value=conf["event"], key=f"conf_event_{i}")
            conf["url"] = st.text_input(f"URL", value=conf["url"], key=f"conf_url_{i}")
            if st.button(f"Remove Conference {i+1}", key=f"remove_conf_activity_{i}"):
                st.session_state["data"]["academic_activities"]["conferences"].pop(i)
                st.rerun()
    st.subheader("Invited Talks")
    if st.button("Add Invited Talk", key="add_talk"):
        st.session_state["data"]["academic_activities"]["talks"].append({
            "date": "", "title": "", "event": "", "url": ""
        })
    for i, talk in enumerate(st.session_state["data"]["academic_activities"]["talks"]):
        with st.expander(f"Talk {i+1}"):
            talk["date"] = st.text_input(f"Date", value=talk["date"], key=f"talk_date_{i}")
            talk["title"] = st.text_input(f"Title", value=talk["title"], key=f"talk_title_{i}")
            talk["event"] = st.text_input(f"Event", value=talk["event"], key=f"talk_event_{i}")
            talk["url"] = st.text_input(f"URL", value=talk["url"], key=f"talk_url_{i}")
            if st.button(f"Remove Talk {i+1}", key=f"remove_talk_{i}"):
                st.session_state["data"]["academic_activities"]["talks"].pop(i)
                st.rerun()
    st.subheader("Editorial Works")
    if st.button("Add Editorial Work", key="add_edit"):
        st.session_state["data"]["academic_activities"]["editorial"].append({
            "date": "", "role": "", "journal": "", "url": ""
        })
    for i, edit in enumerate(st.session_state["data"]["academic_activities"]["editorial"]):
        with st.expander(f"Editorial Work {i+1}"):
            edit["date"] = st.text_input(f"Date", value=edit["date"], key=f"edit_date_{i}")
            edit["role"] = st.text_input(f"Role", value=edit["role"], key=f"edit_role_{i}")
            edit["journal"] = st.text_input(f"Journal", value=edit["journal"], key=f"edit_journal_{i}")
            edit["url"] = st.text_input(f"URL", value=edit["url"], key=f"edit_url_{i}")
            if st.button(f"Remove Editorial Work {i+1}", key=f"remove_edit_{i}"):
                st.session_state["data"]["academic_activities"]["editorial"].pop(i)
                st.rerun()
    st.subheader("Scholarly Profiles")
    if st.button("Add Scholarly Profile", key="add_profile"):
        st.session_state["data"]["academic_activities"]["profiles"].append({
            "name": "", "url": ""
        })
    for i, profile in enumerate(st.session_state["data"]["academic_activities"]["profiles"]):
        with st.expander(f"Profile {i+1}"):
            profile["name"] = st.text_input(f"Name", value=profile["name"], key=f"profile_name_{i}")
            profile["url"] = st.text_input(f"URL", value=profile["url"], key=f"profile_url_{i}")
            if st.button(f"Remove Profile {i+1}", key=f"remove_profile_{i}"):
                st.session_state["data"]["academic_activities"]["profiles"].pop(i)
                st.rerun()
    st.subheader("Papers Reviewed")
    if st.button("Add Review Entry", key="add_review"):
        st.session_state["data"]["academic_activities"]["reviews"].append({
            "year": "", "count": ""
        })
    for i, review in enumerate(st.session_state["data"]["academic_activities"]["reviews"]):
        with st.expander(f"Review Entry {i+1}"):
            review["year"] = st.text_input(f"Year", value=review["year"], key=f"review_year_{i}")
            review["count"] = st.text_input(f"Number of Reviews", value=review["count"], key=f"review_count_{i}")
            if st.button(f"Remove Review Entry {i+1}", key=f"remove_review_{i}"):
                st.session_state["data"]["academic_activities"]["reviews"].pop(i)
                st.rerun()
    st.subheader("Journals Reviewed")
    if st.button("Add Journal", key="add_journal"):
        st.session_state["data"]["academic_activities"]["journals"].append("")
    for i, journal in enumerate(st.session_state["data"]["academic_activities"]["journals"]):
        st.session_state["data"]["academic_activities"]["journals"][i] = st.text_input(f"Journal {i+1}", value=journal, key=f"journal_{i}")
        if st.button(f"Remove Journal {i+1}", key=f"remove_journal_{i}"):
            st.session_state["data"]["academic_activities"]["journals"].pop(i)
            st.rerun()

elif st.session_state["active_tab"] == "Grants & Awards":
    st.subheader("Grants")
    if st.button("Add Grant", key="add_grant"):
        st.session_state["data"]["grants_awards"]["grants"].append({
            "duration": "", "agency": "", "category": "", "number": "", "amount": ""
        })
    for i, grant in enumerate(st.session_state["data"]["grants_awards"]["grants"]):
        with st.expander(f"Grant {i+1}"):
            grant["duration"] = st.text_input(f"Duration", value=grant["duration"], key=f"grant_duration_{i}")
            grant["agency"] = st.text_input(f"Funding Agency", value=grant["agency"], key=f"grant_agency_{i}")
            grant["category"] = st.text_input(f"Category", value=grant["category"], key=f"grant_category_{i}")
            grant["number"] = st.text_input(f"Grant Number", value=grant["number"], key=f"grant_number_{i}")
            grant["amount"] = st.text_input(f"Amount", value=grant["amount"], key=f"grant_amount_{i}")
            if st.button(f"Remove Grant {i+1}", key=f"remove_grant_{i}"):
                st.session_state["data"]["grants_awards"]["grants"].pop(i)
                st.rerun()
    st.subheader("Awards")
    if st.button("Add Award", key="add_award"):
        st.session_state["data"]["grants_awards"]["awards"].append({
            "year": "", "description": ""
        })
    for i, award in enumerate(st.session_state["data"]["grants_awards"]["awards"]):
        with st.expander(f"Award {i+1}"):
            award["year"] = st.text_input(f"Year", value=award["year"], key=f"award_year_{i}")
            award["description"] = st.text_input(f"Description", value=award["description"], key=f"award_description_{i}")
            if st.button(f"Remove Award {i+1}", key=f"remove_award_{i}"):
                st.session_state["data"]["grants_awards"]["awards"].pop(i)
                st.rerun()

elif st.session_state["active_tab"] == "Skills & Memberships":
    st.subheader("Skills")
    st.session_state["data"]["skills"]["h_index"] = st.text_input("h-index", value=st.session_state["data"]["skills"]["h_index"], key="h_index")
    st.session_state["data"]["skills"]["researchgate_score"] = st.text_input("ResearchGate Score", value=st.session_state["data"]["skills"]["researchgate_score"], key="researchgate_score")
    st.session_state["data"]["skills"]["programming_languages"] = st.text_input("Programming Languages", value=st.session_state["data"]["skills"]["programming_languages"], key="programming_languages")
    if st.button("Add Software", key="add_software"):
        st.session_state["data"]["skills"]["softwares"].append({"name": "", "url": ""})
    for i, software in enumerate(st.session_state["data"]["skills"]["softwares"]):
        with st.expander(f"Software {i+1}"):
            software["name"] = st.text_input(f"Name", value=software["name"], key=f"software_name_{i}")
            software["url"] = st.text_input(f"URL", value=software["url"], key=f"software_url_{i}")
            if st.button(f"Remove Software {i+1}", key=f"remove_software_{i}"):
                st.session_state["data"]["skills"]["softwares"].pop(i)
                st.rerun()
    st.session_state["data"]["skills"]["parallel_computing"] = st.text_input("Parallel Computing", value=st.session_state["data"]["skills"]["parallel_computing"], key="parallel_computing")
    st.session_state["data"]["skills"]["experiments"] = st.text_input("Experiments", value=st.session_state["data"]["skills"]["experiments"], key="experiments")
    st.subheader("Memberships")
    if st.button("Add Membership", key="add_membership"):
        st.session_state["data"]["memberships"].append({
            "name": "", "url": "", "details": ""
        })
    for i, membership in enumerate(st.session_state["data"]["memberships"]):
        with st.expander(f"Membership {i+1}"):
            membership["name"] = st.text_input(f"Name", value=membership["name"], key=f"membership_name_{i}")
            membership["url"] = st.text_input(f"URL", value=membership["url"], key=f"membership_url_{i}")
            membership["details"] = st.text_input(f"Details", value=membership["details"], key=f"membership_details_{i}")
            if st.button(f"Remove Membership {i+1}", key=f"remove_membership_{i}"):
                st.session_state["data"]["memberships"].pop(i)
                st.rerun()

# Save and Download Section
st.header("Save and Download")
col1, col2 = st.columns(2)
with col1:
    if st.button("Save Data to JSON"):
        errors = validate_data(st.session_state["data"])
        if errors:
            for error in errors:
                st.error(error)
        else:
            st.session_state["data"]["last_updated"] = datetime.datetime.now().isoformat()
            json_content = json.dumps(st.session_state["data"], indent=4)
            with open("cv_data.json", "w") as f:
                f.write(json_content)
            st.success("Data saved to cv_data.json")
with col2:
    st.download_button("Download JSON", json.dumps(st.session_state["data"], indent=4), file_name="cv_data.json", mime="text/json")
    if st.session_state["tex_content"]:
        st.download_button("Download cv_template.tex", st.session_state["tex_content"], file_name="cv_template.tex", mime="text/plain")
    if st.session_state["sty_content"]:
        st.download_button("Download cv_style.sty", st.session_state["sty_content"], file_name="cv_style.sty", mime="text/plain")

# Generate CV and Display PDF
if st.button("Generate CV"):
    errors = validate_data(st.session_state["data"])
    if errors:
        for error in errors:
            st.error(error)
    else:
        if not st.session_state["tex_content"] or not st.session_state["sty_content"]:
            st.error("Please upload a .db file containing cv_template.tex and cv_style.sty")
        else:
            generated_tex, pdf_content = generate_latex_cv(st.session_state["data"], st.session_state["tex_content"], st.session_state["sty_content"])
            json_content = json.dumps(st.session_state["data"], indent=4)
            
            # Download buttons for generated files
            st.download_button("Download LaTeX", generated_tex, file_name="cv.tex", mime="text/plain")
            if pdf_content:
                st.download_button("Download PDF", pdf_content, file_name="cv.pdf", mime="application/pdf")
                # Display PDF preview
                with st.expander("PDF Preview"):
                    images = pdf_to_images(pdf_content)
                    for img_data in images:
                        st.image(f"data:image/png;base64,{img_data}")
            else:
                st.error("PDF compilation failed. Please download the LaTeX file and compile it manually.")

            # Create and offer new database download
            db_filename, db_content = create_new_db(json_content, st.session_state["tex_content"], st.session_state["sty_content"])
            st.download_button(f"Download Database ({db_filename})", db_content, file_name=db_filename, mime="application/octet-stream")
