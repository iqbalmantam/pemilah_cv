import streamlit as st
import PyPDF2
import pandas as pd
import docx
import re
import json
from groq import Groq

# Konfigurasi Halaman
st.set_page_config(page_title="AI CV Screener", page_icon="🤖", layout="wide")

# ==================== PENGATURAN GROQ AI ====================
# Mengambil API Key dari Streamlit Secrets
try:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
    client = Groq(api_key=GROQ_API_KEY)
except:
    st.error("⚠️ GROQ_API_KEY belum diatur di Streamlit Secrets. Silakan tambahkan terlebih dahulu.")
    st.stop()

# Daftar posisi untuk prompt AI
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
    """Tetap gunakan Regex untuk Email dan No HP karena lebih pasti dan hemat token"""
    email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
    email = email_match.group(0) if email_match else "-"
    
    clean_text = text.replace(" ", "").replace("-", "")
    phone_match = re.search(r'(\+62|62|08)[0-9]{8,11}', clean_text)
    phone = phone_match.group(0) if phone_match else "-"
    
    return email, phone

def analyze_cv_with_groq(text):
    """Fungsi utama menggunakan AI Groq untuk menganalisis konteks CV"""
    prompt = f"""
    Anda adalah HR Expert. Analisis teks CV berikut.
    Tugas Anda:
    1. Pilih SATU posisi paling cocok dari daftar ini: [{DAFTAR_POSISI}]. Jika tidak ada yang cocok, tulis "Tidak Teridentifikasi".
    2. Berikan skor kecocokan (0-100) berdasarkan keahlian teknis.
    3. Ekstrak total pengalaman kerja dalam bentuk tahun (misal: "3 Tahun"). Jika tidak jelas, tulis "Cek Manual".
    4. Cari nilai IPK/GPA maksimal 4.00 (misal: "3.80"). Jika tidak ada, tulis "-".
    5. Sebutkan maksimal 5 skill utama yang relevan dengan posisi tersebut.
    
    Berikan jawaban HANYA dalam format JSON yang valid seperti ini:
    {{
        "posisi": "Nama Posisi",
        "skor": 85,
        "pengalaman": "3 Tahun",
        "ipk": "3.50",
        "skill": "Python, SQL, AWS"
    }}
    
    Teks CV:
    {text[:4000]}  # Membatasi teks agar tidak melebihi token limit
    """
    
    try:
        # Memanggil API Groq (Menggunakan model llama3-8b-8192 yang sangat cepat)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Anda adalah sistem output JSON."},
                {"role": "user", "content": prompt}
            ],
            model="llama3-8b-8192",
            response_format={"type": "json_object"}, # Memaksa output berupa JSON
            temperature=0.2, # Dibuat rendah agar jawabannya konsisten/objektif
        )
        
        # Mengubah teks JSON dari AI menjadi Dictionary Python
        result_json = json.loads(chat_completion.choices[0].message.content)
        return result_json
        
    except Exception as e:
        # Jika gagal (misal API limit), kembalikan nilai default
        return {
            "posisi": "Gagal Dianalisis (Error AI)",
            "skor": 0,
            "pengalaman": "-",
            "ipk": "-",
            "skill": "-"
        }

def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

# ==================== UI APLIKASI ====================
st.title("🤖 Smart CV Screener Dashboard (Powered by Groq AI)")
st.markdown("Sistem pemilah CV berteknologi LLM. Mampu **memahami konteks** pengalaman kerja, bukan sekadar mencocokkan kata kunci.")

uploaded_files = st.file_uploader("Upload File CV (PDF / DOCX)", type=["pdf", "docx"], accept_multiple_files=True)

if uploaded_files:
    with st.spinner(f"AI sedang membaca dan menganalisis {len(uploaded_files)} dokumen. Mohon tunggu..."):
        results = []
        
        # Progress bar agar UI terlihat lebih interaktif
        progress_bar = st.progress(0)
        
        for i, file in enumerate(uploaded_files):
            cv_text = ""
            if file.name.lower().endswith('.pdf'):
                cv_text = extract_text_from_pdf(file)
            elif file.name.lower().endswith('.docx'):
                cv_text = extract_text_from_docx(file)
            
            if cv_text:
                # 1. Gunakan Regex untuk data pasti
                email, phone = extract_contact_info(cv_text)
                # 2. Gunakan AI Groq untuk analisis pintar
                ai_analysis = analyze_cv_with_groq(cv_text)
                
                results.append({
                    "Nama File": file.name,
                    "Posisi (AI)": ai_analysis.get("posisi", "-"),
                    "Skor (%)": ai_analysis.get("skor", 0),
                    "Pengalaman (AI)": ai_analysis.get("pengalaman", "-"),
                    "IPK": ai_analysis.get("ipk", "-"),
                    "Skill Ditemukan": ai_analysis.get("skill", "-"),
                    "Email": email,
                    "No. HP": phone
                })
            
            # Update progress bar
            progress_bar.progress((i + 1) / len(uploaded_files))
                
        # Memproses hasil ke dalam tabel
        df_results = pd.DataFrame(results)
        df_results = df_results.sort_values(by='Skor (%)', ascending=False)
        
        # Tampilan
        st.success("✅ Analisis AI Selesai!")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            st.subheader("📊 Distribusi Posisi")
            st.bar_chart(df_results['Posisi (AI)'].value_counts())
            
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
        st.dataframe(df_display, use_container_width=True)
