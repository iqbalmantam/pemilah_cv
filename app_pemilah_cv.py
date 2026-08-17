import streamlit as st
import PyPDF2
import pandas as pd
import docx
import re
import json
import altair as alt
from groq import Groq

# Konfigurasi Halaman
st.set_page_config(page_title="AI CV Screener", page_icon="🤖", layout="wide")

# CSS untuk menyembunyikan Header/Footer Streamlit & Mengaktifkan Wrap Text
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .styled-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 10px;
        font-size: 14px;
        font-family: sans-serif;
        background-color: #0e1117;
        color: #fafafa;
    }
    .styled-table th, .styled-table td {
        padding: 12px 15px;
        border: 1px solid #262730;
        text-align: left;
        word-break: break-word;
        white-space: normal !important;
    }
    .styled-table th {
        background-color: #161a25;
        font-weight: bold;
    }
    .styled-table tr:nth-child(even) {
        background-color: #121620;
    }
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

DAFTAR_POSISI = "Software Engineer, Data Analyst, Digital Marketer, UI/UX Designer, HR / Recruitment"

# ==================== FUNGSI EKSTRAKSI TEKS ====================
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        return "".join([page.extract_text() for page in reader.pages if page.extract_text()]).lower()
    except:
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = docx.Document(docx_file)
        return "\n".join([para.text for para in doc.paragraphs]).lower()
    except:
        return ""

# ==================== FUNGSI REGEX & AI ====================
def extract_contact_info(text):
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    email = email_match.group(0) if email_match else "-"
    
    clean_text = text.replace(" ", "").replace("-", "")
    phone_match = re.search(r'(\+62|62|08)[0-9]{8,11}', clean_text)
    phone = phone_match.group(0) if phone_match else "-"
    
    return email, phone

def analyze_cv_with_groq(text):
    # Prompt diperbarui agar penilaian lebih proporsional untuk kandidat berpengalaman
    prompt = f"""
    Anda adalah HR Expert. Analisis teks CV berikut.
    Tugas Anda:
    1. Ekstrak Nama Lengkap kandidat.
    2. Pilih SATU posisi paling cocok dari daftar ini: [{DAFTAR_POSISI}]. Jika tidak ada yang cocok, tulis "Tidak Teridentifikasi".
    3. Berikan skor kecocokan (0-100). Jika kandidat berpengalaman di bidang tersebut, berikan nilai minimal 50 meskipun skill teknis tidak eksplisit tertulis.
    4. Ekstrak total pengalaman kerja (dalam angka tahun).
    5. Ekstrak Riwayat Jabatan: Tuliskan daftar posisi/jabatan yang pernah dipegang kandidat dengan ringkas.
    6. Ekstrak Pendidikan Terakhir (Jurusan dan Universitas, misal: "S1 Teknik Informatika - Univ X").
    7. Cari nilai IPK/GPA maksimal 4.00.
    8. Sebutkan maksimal 5 skill utama yang relevan.
    
    Berikan jawaban HANYA dalam format JSON yang valid seperti ini:
    {{
        "nama_lengkap": "Nama Kandidat",
        "posisi": "Nama Posisi",
        "skor": 85,
        "pengalaman": "3 Tahun",
        "riwayat_jabatan": "Jabatan 1 di PT X, Jabatan 2 di PT Y",
        "pendidikan_terakhir": "S1 Teknik Informatika - Univ X",
        "ipk": "3.50",
        "skill": "Python, SQL, AWS"
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
        result_json = json.loads(chat_completion.choices[0].message.content)
        return result_json
    except Exception as e:
        return {
            "nama_lengkap": "-",
            "posisi": "Gagal Dianalisis (Error AI)",
            "skor": 0,
            "pengalaman": "-",
            "riwayat_jabatan": "-",
            "pendidikan_terakhir": "-",
            "ipk": "-",
            "skill": "-"
        }

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# ==================== UI APLIKASI ====================
st.title("🤖 Smart CV Screener Dashboard (Powered by Groq AI)")
st.markdown("Sistem pemilah CV berteknologi LLM. Mampu **memahami konteks** pengalaman kerja, bukan sekadar mencocokkan kata kunci.")
st.caption("Developed by iqbalmantam")
st.markdown("---")

uploaded_files = st.file_uploader("Upload File CV (PDF / DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner(f"AI sedang menganalisis {len(uploaded_files)} dokumen..."):
        results = []
        progress_bar = st.progress(0)
        
        for i, file in enumerate(uploaded_files):
            cv_text = ""
            if file.name.lower().endswith('.pdf'):
                cv_text = extract_text_from_pdf(file)
            elif file.name.lower().endswith('.docx'):
                cv_text = extract_text_from_docx(file)
            
            if cv_text:
                email, phone = extract_contact_info(cv_text)
                ai_analysis = analyze_cv_with_groq(cv_text)
                
                results.append({
                    "Nama Lengkap": ai_analysis.get("nama_lengkap", "-"),
                    "Posisi (AI)": ai_analysis.get("posisi", "-"),
                    "Skor (%)": ai_analysis.get("skor", 0),
                    "Pengalaman": ai_analysis.get("pengalaman", "-"),
                    "Riwayat Jabatan": ai_analysis.get("riwayat_jabatan", "-"),
                    "Pendidikan Terakhir": ai_analysis.get("pendidikan_terakhir", "-"),
                    "IPK": ai_analysis.get("ipk", "-"),
                    "Skill Ditemukan": ai_analysis.get("skill", "-"),
                    "Email": email,
                    "No. HP": phone
                })
            
            progress_bar.progress((i + 1) / len(uploaded_files))
                
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by='Skor (%)', ascending=False)
        
        st.success("✅ Analisis AI Selesai!")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📊 Distribusi Posisi")
            
            df_chart = df_results['Posisi (AI)'].value_counts().reset_index()
            df_chart.columns = ['Posisi', 'Jumlah']
            
            chart = alt.Chart(df_chart).mark_bar(color='#4c78a8').encode(
                x=alt.X('Jumlah:Q', title='Jumlah Kandidat', axis=alt.Axis(format='d')),
                y=alt.Y('Posisi:N', sort='-x', title='Posisi')
            ).properties(height=250)
            
            st.altair_chart(chart, use_container_width=True)
            
        with col2:
            st.subheader("🔎 Filter Kandidat")
            posisi_unik = ["Semua Posisi"] + list(df_results['Posisi (AI)'].unique())
            pilih_posisi = st.selectbox("Tampilkan kandidat untuk posisi:", posisi_unik)
            
            if pilih_posisi != "Semua Posisi":
                df_display = df_results[df_results['Posisi (AI)'] == pilih_posisi]
            else:
                df_display = df_results.copy()
            
            csv = convert_df_to_csv(df_display)
            st.download_button(label="📥 Download Data (CSV)", data=csv, file_name='hasil_screening_ai.csv', mime='text/csv')

        st.subheader("📋 Tabel Hasil Screening")
        
        # Merender tabel menggunakan HTML kustom agar wrap text aktif
        table_html = df_display.to_html(classes='styled-table', index=False, escape=False)
        st.markdown(table_html, unsafe_allow_html=True)
