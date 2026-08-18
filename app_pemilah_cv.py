import streamlit as st
import PyPDF2
import pandas as pd
import docx
import json
import re
import altair as alt
from groq import Groq

# Konfigurasi Halaman
st.set_page_config(page_title="AI CV Screener", page_icon="🤖", layout="wide")

# CSS untuk menyembunyikan Header/Footer Streamlit & Mengaktifkan Wrap Text Tabel
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
except Exception as e:
    st.error(f"⚠️ GROQ_API_KEY belum diatur di Streamlit Secrets. Error: {e}")
    st.stop()

# ==================== FUNGSI EKSTRAKSI TEKS ====================
def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    except:
        return ""

def extract_text_from_docx(docx_file):
    try:
        doc = docx.Document(docx_file)
        return "\n".join([para.text for para in doc.paragraphs])
    except:
        return ""

# ==================== FUNGSI AI DENGAN MULTI-MODEL & PARSER AMAN ====================
def analyze_cv_with_groq(text):
    prompt = f"""
    Anda adalah HR Expert. Analisis teks CV berikut.
    Tugas Anda:
    1. Ekstrak Nama Lengkap.
    2. Ekstrak semua Nomor HP yang ditemukan di CV.
    3. Ekstrak Email.
    4. Tentukan Profil Profesional/Latar Belakang utama kandidat (misal: "Administrasi", "Logistik", "Akuntan", "Human Resources", "IT Support").
    5. Berikan skor kecocokan (0-100). Jika kandidat berpengalaman, berikan nilai minimal 50.
    6. Ekstrak total pengalaman kerja (angka tahun).
    7. Ekstrak Riwayat Jabatan (jabatan dan perusahaan secara ringkas).
    8. Ekstrak Pendidikan Terakhir (Jurusan dan Universitas).
    9. Cari nilai IPK/GPA maksimal 4.00.
    10. Sebutkan maksimal 5 skill utama yang relevan.
    
    Berikan jawaban HANYA dalam format JSON murni dengan struktur berikut tanpa teks lain di luar JSON:
    {{
        "nama_lengkap": "Nama Kandidat",
        "email": "Email",
        "no_hp": "No HP",
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
    
    # Daftar model aktif saat ini di Groq
    models_to_try = [
        "deepseek-r1-distill-llama-70b",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "deepseek-r1-distill-qwen-32b"
    ]
    
    last_error = None
    for model_name in models_to_try:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "Anda adalah sistem output JSON murni."},
                    {"role": "user", "content": prompt}
                ],
                model=model_name,
                temperature=0.1,
            )
            
            raw_content = chat_completion.choices[0].message.content.strip()
            
            # Ekstrasi teks JSON secara otomatis menggunakan regex (mengabaikan tag think atau markdown)
            match = re.search(r'\{.*\}', raw_content, re.DOTALL)
            if match:
                json_str = match.group(0)
                return json.loads(json_str)
                
        except Exception as e:
            last_error = e
            continue
            
    st.error(f"Gagal memproses AI dengan semua model. Error terakhir: {last_error}")
    return {
        "nama_lengkap": "-", "email": "-", "no_hp": "-", 
        "profil_profesional": "Lainnya", "skor": 0, 
        "pengalaman": "-", "riwayat_jabatan": "-", 
        "pendidikan_terakhir": "-", "ipk": "-", "skill": "-"
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
            cv_text = extract_text_from_pdf(file) if file.name.lower().endswith('.pdf') else extract_text_from_docx(file)
            if cv_text:
                ai = analyze_cv_with_groq(cv_text)
                results.append({
                    "Nama Lengkap": ai.get("nama_lengkap", "-"),
                    "Profil Profesional": ai.get("profil_profesional", "-"),
                    "Skor (%)": ai.get("skor", 0),
                    "Pengalaman": ai.get("pengalaman", "-"),
                    "Riwayat Jabatan": ai.get("riwayat_jabatan", "-"),
                    "Pendidikan Terakhir": ai.get("pendidikan_terakhir", "-"),
                    "IPK": ai.get("ipk", "-"),
                    "Skill Ditemukan": ai.get("skill", "-"),
                    "Email": ai.get("email", "-"),
                    "No. HP": ai.get("no_hp", "-")
                })
            progress_bar.progress((i + 1) / len(uploaded_files))
            
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by='Skor (%)', ascending=False)
        
        st.success("✅ Analisis AI Selesai!")
        
        # Layout Atas: Grafik Distribusi (Kolom Kiri) & Filter + Download (Kolom Kanan)
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📊 Distribusi Profil")
            df_chart = df_results['Profil Profesional'].value_counts().reset_index()
            df_chart.columns = ['Profil', 'Jumlah']
            
            chart = alt.Chart(df_chart).mark_bar(color='#4c78a8').encode(
                x=alt.X('Jumlah:Q', title='Jumlah Kandidat', axis=alt.Axis(format='d')),
                y=alt.Y('Profil:N', sort='-x', title='Profil Profesional')
            ).properties(height=250)
            
            st.altair_chart(chart, use_container_width=True)
            
        with col2:
            st.subheader("🔎 Filter Kandidat")
            profil_unik = ["Semua Profil"] + list(df_results['Profil Profesional'].unique())
            pilih_profil = st.selectbox("Tampilkan kandidat berdasarkan profil:", profil_unik)
            
            if pilih_profil != "Semua Profil":
                df_display = df_results[df_results['Profil Profesional'] == pilih_profil]
            else:
                df_display = df_results.copy()
            
            st.write("")
            csv = convert_df_to_csv(df_display)
            st.download_button(
                label="📥 Download Data (CSV)", 
                data=csv, 
                file_name='hasil_screening_ai.csv', 
                mime='text/csv'
            )

        # Layout Bawah: Tabel Hasil Screening Full Lebar
        st.markdown("---")
        st.subheader("📋 Tabel Hasil Screening")
        table_html = df_display.to_html(classes='styled-table', index=False, escape=False)
        st.markdown(table_html, unsafe_allow_html=True)
