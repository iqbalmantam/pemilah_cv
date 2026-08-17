import streamlit as st
import PyPDF2
import pandas as pd
import docx
import json
import altair as alt
from groq import Groq

# Konfigurasi Halaman
st.set_page_config(page_title="AI CV Screener", page_icon="🤖", layout="wide")

# CSS untuk Rapi
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .styled-table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 14px; background-color: #0e1117; color: #fafafa; }
    .styled-table th, .styled-table td { padding: 12px 15px; border: 1px solid #262730; text-align: left; word-break: break-word; white-space: normal !important; }
    .styled-table th { background-color: #161a25; font-weight: bold; }
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==================== PENGATURAN GROQ AI ====================
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except:
    st.error("⚠️ GROQ_API_KEY belum diatur di Streamlit Secrets.")
    st.stop()

# ==================== FUNGSI EKSTRAKSI TEKS ====================
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        # Mengambil seluruh teks dengan spasi
        return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except:
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = docx.Document(docx_file)
        return "\n".join([para.text for para in doc.paragraphs])
    except:
        return ""

# ==================== FUNGSI AI ====================
def analyze_cv_with_groq(text):
    # Prompt diperbarui: Meminta AI mengekstrak Nomor HP secara eksplisit
    prompt = f"""
    Anda adalah HR Expert. Analisis teks CV berikut.
    Tugas Anda:
    1. Ekstrak Nama Lengkap.
    2. Ekstrak semua Nomor HP yang ditemukan di CV.
    3. Ekstrak Email.
    4. Tentukan Profil Profesional utama kandidat.
    5. Berikan skor kecocokan (0-100). Jika kandidat berpengalaman, berikan nilai minimal 50.
    6. Ekstrak total pengalaman kerja (angka tahun).
    7. Ekstrak Riwayat Jabatan (jabatan dan perusahaan secara ringkas).
    8. Ekstrak Pendidikan Terakhir.
    9. Cari nilai IPK/GPA maksimal 4.00.
    10. Sebutkan maksimal 5 skill utama.
    
    Berikan jawaban HANYA dalam format JSON yang valid seperti ini:
    {{
        "nama_lengkap": "Nama",
        "email": "Email",
        "no_hp": "08123456789",
        "profil_profesional": "Latar Belakang",
        "skor": 85,
        "pengalaman": "3 Tahun",
        "riwayat_jabatan": "Jabatan 1 di PT X, Jabatan 2 di PT Y",
        "pendidikan_terakhir": "S1 Jurusan - Univ X",
        "ipk": "3.50",
        "skill": "Skill A, Skill B"
    }}
    
    Teks CV:
    {text[:4000]}
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Anda adalah sistem output JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return json.loads(chat_completion.choices[0].message.content)
    except:
        return {"nama_lengkap": "-", "email": "-", "no_hp": "-", "profil_profesional": "-", "skor": 0, "pengalaman": "-", "riwayat_jabatan": "-", "pendidikan_terakhir": "-", "ipk": "-", "skill": "-"}

# ==================== UI APLIKASI ====================
st.title("🤖 Smart CV Screener Dashboard (Powered by Groq AI)")
st.caption("Developed by iqbalmantam")
st.markdown("---")

uploaded_files = st.file_uploader("Upload File CV (PDF / DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files:
    results = []
    progress_bar = st.progress(0)
    for i, file in enumerate(uploaded_files):
        cv_text = extract_text_from_pdf(file) if file.name.lower().endswith('.pdf') else extract_text_from_docx(file)
        if cv_text:
            ai = analyze_cv_with_groq(cv_text)
            results.append({
                "Nama Lengkap": ai.get("nama_lengkap", "-"),
                "Profil": ai.get("profil_profesional", "-"),
                "Skor (%)": ai.get("skor", 0),
                "Pengalaman": ai.get("pengalaman", "-"),
                "Jabatan": ai.get("riwayat_jabatan", "-"),
                "Pendidikan": ai.get("pendidikan_terakhir", "-"),
                "IPK": ai.get("ipk", "-"),
                "Skill": ai.get("skill", "-"),
                "Email": ai.get("email", "-"),
                "No. HP": ai.get("no_hp", "-")
            })
        progress_bar.progress((i + 1) / len(uploaded_files))
            
    df = pd.DataFrame(results).sort_values(by='Skor (%)', ascending=False)
    
    # Tampilan Dashboard
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("📊 Distribusi Profil")
        st.altair_chart(alt.Chart(df['Profil'].value_counts().reset_index().rename(columns={'index':'Profil','Profil':'Jumlah'})).mark_bar().encode(
            x='Jumlah:Q', y=alt.Y('Profil:N', sort='-x')), use_container_width=True)
            
    with col2:
        st.subheader("📋 Tabel Screening")
        st.markdown(df.to_html(classes='styled-table', index=False, escape=False), unsafe_allow_html=True)
