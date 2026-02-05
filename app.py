"""
KodUret - Ultra AI Kod Olusturucu
Coklu AI destegi + Otomatik hata duzeltme
"""

import streamlit as st
import requests
import sqlite3
import hashlib
import secrets
import traceback
from datetime import datetime

st.set_page_config(page_title="KodUret Pro", page_icon="🚀", layout="wide")

# API Keys
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# =============================================================================
# DATABASE
# =============================================================================

def get_db():
    conn = sqlite3.connect("appfab.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY, email TEXT UNIQUE, username TEXT,
        password_hash TEXT, credits INTEGER DEFAULT 10, is_pro INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS apps (
        app_id TEXT PRIMARY KEY, user_id TEXT, name TEXT, description TEXT,
        prompt TEXT, code TEXT, is_public INTEGER DEFAULT 0, likes INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

# =============================================================================
# AUTH
# =============================================================================

def create_user(email, password, username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    if c.fetchone():
        return False, "Email kayitli"
    user_id = f"user_{secrets.token_hex(8)}"
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("INSERT INTO users VALUES (?,?,?,?,10,0)", (user_id, email, username, pwd_hash))
    conn.commit()
    conn.close()
    return True, "Kayit basarili! 10 kredi hediye"

def login_user(email, password):
    conn = get_db()
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE email=? AND password_hash=?", (email, pwd_hash))
    user = c.fetchone()
    conn.close()
    return (True, dict(user)) if user else (False, None)

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def deduct_credit(user_id):
    user = get_user(user_id)
    if user["is_pro"] or user["credits"] > 0:
        if not user["is_pro"]:
            conn = get_db()
            c = conn.cursor()
            c.execute("UPDATE users SET credits = credits - 1 WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
        return True
    return False

def save_app(user_id, name, description, prompt, code, is_public):
    conn = get_db()
    c = conn.cursor()
    app_id = f"app_{int(datetime.now().timestamp())}"
    c.execute("INSERT INTO apps VALUES (?,?,?,?,?,?,?,0,?)", 
              (app_id, user_id, name, description, prompt, code, int(is_public), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return app_id

def get_user_apps(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM apps WHERE user_id=? ORDER BY created_at DESC", (user_id,))
    apps = [dict(row) for row in c.fetchall()]
    conn.close()
    return apps

# =============================================================================
# AI - GELISMIS
# =============================================================================

def generate_with_openai(prompt, system_msg=None):
    """OpenAI ile kod uret"""
    if not OPENAI_API_KEY:
        return None, "OpenAI API Key eksik"
    
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        
        if not system_msg:
            system_msg = """Sen dunyanin en iyi Streamlit ve Python gelistiricisisin. 
            GOREVIN: Kullanicinin istedigi her seyi kusursuz bir sekilde olusturmak.
            
            KURALLAR:
            1. SADECE calisan, hatasiz Python kodu uret
            2. st.set_page_config() MUTLAKA ilk satirda olsun
            3. Tum kutuphaneleri kontrol et (try-except kullan)
            4. Hata olursa kullaniciya anlasilir mesaj goster
            5. Modern, guzel bir UI tasarla
            6. Kullanici ne isterse onu yap - imkansiz yok
            7. Resim isleme, API cagriları, hesaplama, oyun - her seyi yapabilirsin
            8. Kodun basina hangi kutuphaneler gerekiyorsa yorum olarak yaz (ornek: # pip install requests)
            9. TURKCE karakterleri dogru kullan (ş, ç, ö, ğ, ü, ı)
            
            CIKTIDA SADECE KOD OLACAK, aciklama yok!"""
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Bu uygulamayi olustur (mukemmel ve calisan olsun): {prompt}"}
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        response = requests.post("https://api.openai.com/v1/chat/completions", 
                                headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        code = response.json()["choices"][0]["message"]["content"]
        
        return clean_code(code), None
        
    except Exception as e:
        return None, str(e)

def generate_with_gemini(prompt):
    """Gemini ile kod uret (yedek)"""
    if not GEMINI_API_KEY:
        return None, "Gemini API Key eksik"
    
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
        
        data = {
            "contents": [{
                "parts": [{
                    "text": f"Streamlit uygulamasi yaz (sadece kod, aciklama yok): {prompt}"
                }]
            }]
        }
        
        response = requests.post(url, json=data, timeout=60)
        response.raise_for_status()
        result = response.json()
        code = result["candidates"][0]["content"]["parts"][0]["text"]
        
        return clean_code(code), None
        
    except Exception as e:
        return None, str(e)

def fix_code_with_ai(original_code, error_message, prompt):
    """Hatali kodu AI ile duzelt"""
    system_msg = """Sen bir kod duzeltme uzmanisin. Sana hatali kod ve hata mesaji verecegim.
    GOREVIN: Kodu duzelt ve calisir hale getir.
    SADECE duzeltilmis kodu ver, aciklama yok!"""
    
    fix_prompt = f"""ORIJINAL ISTEK: {prompt}
    
    HATALI KOD:
    {original_code}
    
    HATA MESAJI:
    {error_message}
    
    Lutfen kodu duzelt ve calisir hale getir."""
    
    # Once OpenAI dene
    if OPENAI_API_KEY:
        code, err = generate_with_openai(fix_prompt, system_msg)
        if code:
            return code, None
    
    # Olmezse Gemini dene
    if GEMINI_API_KEY:
        return generate_with_gemini(fix_prompt)
    
    return None, "Kod duzeltilemedi"

def clean_code(code):
    """Kodu temizle"""
    if code.startswith("```python"): code = code[9:]
    elif code.startswith("```"): code = code[3:]
    if code.endswith("```"): code = code[:-3]
    return code.strip()

def generate_app(prompt, retry_on_error=True):
    """Ana uretim fonksiyonu - Hata olursa otomatik duzelt"""
    
    # 1. OpenAI dene
    if OPENAI_API_KEY:
        code, error = generate_with_openai(prompt)
        if code:
            return code, None
    
    # 2. Gemini dene (yedek)
    if GEMINI_API_KEY:
        code, error = generate_with_gemini(prompt)
        if code:
            return code, None
    
    return None, "Tum AI modelleri basarisiz oldu"

# =============================================================================
# SESSION
# =============================================================================

if "user" not in st.session_state: st.session_state.user = None
if "page" not in st.session_state: st.session_state.page = "home"
if "generated_code" not in st.session_state: st.session_state.generated_code = None
if "show_preview" not in st.session_state: st.session_state.show_preview = False
if "fix_attempt" not in st.session_state: st.session_state.fix_attempt = 0

# =============================================================================
# UI
# =============================================================================

st.title("🚀 KodUret Pro")
st.caption("Dunyadaki her seyi yapabilen AI")

with st.sidebar:
    st.header("Menu")
    if st.session_state.user:
        user = get_user(st.session_state.user["user_id"])
        st.write(f"👤 {user['username']}")
        st.write(f"💎 {user['credits']} Kredi")
        if st.button("🏠 Ana Sayfa", use_container_width=True): 
            st.session_state.page = "home"
            st.session_state.show_preview = False
            st.rerun()
        if st.button("✨ Kod Uret", use_container_width=True): 
            st.session_state.page = "create"
            st.session_state.show_preview = False
            st.rerun()
        if st.button("📂 Kodlarim", use_container_width=True): 
            st.session_state.page = "myapps"
            st.session_state.show_preview = False
            st.rerun()
        if st.button("🚪 Cikis", use_container_width=True): 
            st.session_state.user = None
            st.session_state.show_preview = False
            st.rerun()
    else:
        if st.button("🏠 Ana Sayfa", use_container_width=True): 
            st.session_state.page = "home"
            st.rerun()
        if st.button("🔐 Giris / Kayit", use_container_width=True): 
            st.session_state.page = "auth"
            st.rerun()

# =============================================================================
# PAGES
# =============================================================================

if st.session_state.page == "home":
    st.header("🚀 KodUret Pro'ya Hos Geldiniz")
    st.write("**Dunyadaki her seyi** yapabilen yapay zeka ile tanisin.")
    
    st.info("""
    ✅ **Neler yapabilir?**
    - Hesap makineleri, BMI hesaplayicilar
    - Excel/PDF islemleri
    - Resim yukleme ve analiz
    - Veri gorsellestirme
    - Oyunlar ve eglence
    - Web scraping
    - Ve daha fazlasi...
    
    💡 **Ipuclari:**
    - "Excel dosyasi yukleyip analiz eden app yap"
    - "Foto yukleyip filtre uygulayan app yap"
    - "Para birimi cevirici yap"
    """)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("⚡ Hizli", "30 sn")
    col2.metric("🤖 AI", "GPT-4 + Gemini")
    col3.metric("🔧 Oto Duzeltme", "Aktif")
    
    if not st.session_state.user:
        if st.button("🔐 Baslamak icin Giris Yap", type="primary"):
            st.session_state.page = "auth"
            st.rerun()

elif st.session_state.page == "auth":
    st.header("🔐 Giris / Kayit")
    tab1, tab2 = st.tabs(["Giris Yap", "Kayit Ol"])
    
    with tab1:
        with st.form("login"):
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Sifre", type="password")
            if st.form_submit_button("Giris Yap", use_container_width=True):
                ok, user = login_user(email, password)
                if ok:
                    st.session_state.user = user
                    st.success("Giris basarili!")
                    st.rerun()
                else:
                    st.error("Hatali giris")
    
    with tab2:
        with st.form("register"):
            username = st.text_input("👤 Kullanici Adi")
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Sifre", type="password")
            if st.form_submit_button("Kayit Ol", use_container_width=True):
                ok, msg = create_user(email, password, username)
                if ok: st.success(msg)
                else: st.error(msg)

elif st.session_state.page == "create":
    if not st.session_state.user:
        st.error("Lutfen giris yapin")
        st.stop()
    
    # PREVIEW MODU
    if st.session_state.show_preview and st.session_state.generated_code:
        st.markdown("""
        <div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0;">▶️ Uygulamaniz Calisiyor</h2>
            <p style="color: white; margin: 5px 0;">Asagida canli olarak kullanabilirsiniz</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        if col1.button("❌ Uygulamayi Kapat", use_container_width=True):
            st.session_state.show_preview = False
            st.rerun()
        if col2.button("🔄 Tekrar Dene (Hata Varsa)", use_container_width=True):
            st.session_state.fix_attempt += 1
            with st.spinner("Kod duzeltiliyor..."):
                fixed_code, err = fix_code_with_ai(
                    st.session_state.generated_code,
                    "Onceki calistirmada hata olustu",
                    st.session_state.last_prompt
                )
                if fixed_code:
                    st.session_state.generated_code = fixed_code
                    save_app(st.session_state.user["user_id"], "Duzeltilmis", "Oto duzeltme", st.session_state.last_prompt, fixed_code, False)
                    st.success("Kod duzeltildi!")
                    st.rerun()
                else:
                    st.error("Duzeltme basarisiz")
        
        # Calistirma alani
        with st.container(border=True):
            try:
                code_to_run = st.session_state.generated_code
                lines = code_to_run.split('\n')
                filtered_lines = [line for line in lines if 'set_page_config' not in line]
                clean_code_exec = '\n'.join(filtered_lines)
                exec(clean_code_exec)
            except Exception as e:
                error_msg = str(e)
                st.error(f"⚠️ Calistirma Hatasi: {error_msg}")
                st.code(traceback.format_exc())
                
                st.warning("Yukaridaki 'Tekrar Dene' butonuna tiklayarak kodun duzeltilmesini saglayabilirsiniz.")
    
    # NORMAL MOD
    else:
        st.header("✨ Ne Yapmak Istiyorsunuz?")
        user = get_user(st.session_state.user["user_id"])
        st.write(f"💎 Krediniz: {user['credits']}")
        
        st.info("""
        **Ornekler:**
        - "Excel dosyasi yukleyip satis analizi yapan app yap"
        - "Fotograf yukleyip siyah-beyaz cevirme app'i yap"  
        - "Tum para birimlerini birbirine ceviren app yap"
        - "Yapay zeka ile chat edebilecegim app yap"
        - "Sudoku oyunu yap"
        """)
        
        prompt = st.text_area("Detayli anlatin:", 
                             placeholder="Ne isterseniz yazin - imkansiz yok! Ornegin: 'Excel yukleyip grafik cizdiren app yap...'",
                             height=120)
        
        col1, col2 = st.columns([3, 1])
        app_name = col1.text_input("Uygulama Adi", "Benim Super App'im")
        is_public = col2.checkbox("Herkese Acik")
        
        if st.button("🚀 KOD URET (AI Calisiyor...)", type="primary", use_container_width=True):
            if prompt:
                st.session_state.last_prompt = prompt
                if deduct_credit(st.session_state.user["user_id"]):
                    with st.spinner("🤖 AI dusunuyor... (Bu biraz zaman alabilir)"):
                        code, error = generate_app(prompt)
                    
                    if code:
                        save_app(st.session_state.user["user_id"], app_name, prompt[:100], prompt, code, is_public)
                        st.session_state.generated_code = code
                        st.session_state.show_preview = False
                        st.session_state.fix_attempt = 0
                        st.success(f"✅ Kod basariyla olusturuldu! (Deneme: {st.session_state.fix_attempt + 1})")
                        st.rerun()
                    else:
                        st.error(f"Hata: {error}")
                else:
                    st.error("Krediniz bitti!")
            else:
                st.error("Lutfen bir seyler yazin")
        
        if st.session_state.generated_code:
            st.divider()
            
            st.markdown("""
            <div style="background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); 
                        padding: 25px; border-radius: 15px; text-align: center; margin: 20px 0;">
                <h2 style="color: white; margin: 0;">🎮 Hazir!</h2>
                <p style="color: white; font-size: 18px; margin: 10px 0;">Uygulamanizi simdi calistirabilir veya kodu inceleyebilirsiniz</p>
            </div>
            """, unsafe_allow_html=True)
            
            col_run, col_show = st.columns(2)
            with col_run:
                if st.button("▶️ UYGULAMAYI CALISTIR", type="primary", use_container_width=True):
                    st.session_state.show_preview = True
                    st.rerun()
            with col_show:
                with st.expander("📜 Kodu Goster"):
                    st.code(st.session_state.generated_code, language="python")
                    st.download_button("💾 Indir (.py)", st.session_state.generated_code, file_name="app.py")

elif st.session_state.page == "myapps":
    if not st.session_state.user:
        st.error("Lutfen giris yapin")
        st.stop()
    
    st.header("📂 Kayitli Uygulamalarim")
    apps = get_user_apps(st.session_state.user["user_id"])
    
    if not apps:
        st.info("Henuz kayitli uygulama yok.")
    else:
        for i, app in enumerate(apps):
            with st.expander(f"{'🌐' if app['is_public'] else '🔒'} {app['name']} | {app['created_at'][:10]}"):
                st.write(f"**Aciklama:** {app['description']}")
                
                col1, col2 = st.columns(2)
                col1.download_button("📥 Indir", app['code'], file_name=f"{app['name']}.py", key=f"dl_{i}")
                
                if col2.button("▶️ Calistir", key=f"run_{i}"):
                    st.session_state.generated_code = app['code']
                    st.session_state.show_preview = True
                    st.session_state.page = "create"
                    st.rerun()
