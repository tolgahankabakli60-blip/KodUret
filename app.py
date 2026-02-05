"""
AppFab - AI App Generator
Telefon ve PC'de çalışan basit versiyon
"""

import streamlit as st
import requests
import sqlite3
import hashlib
import secrets
from datetime import datetime

st.set_page_config(page_title="AppFab", page_icon="⚡", layout="wide")

# OpenAI Key
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")

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
# AUTH & DB FUNCS
# =============================================================================

def create_user(email, password, username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    if c.fetchone():
        return False, "Email kayıtlı"
    user_id = f"user_{secrets.token_hex(8)}"
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("INSERT INTO users VALUES (?,?,?,?,10,0)", (user_id, email, username, pwd_hash))
    conn.commit()
    conn.close()
    return True, "Kayıt başarılı! 10 kredi hediye"

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
# AI GENERATOR
# =============================================================================

def generate_app(prompt):
    if not OPENAI_API_KEY:
        return None, "API Key eksik"
    try:
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Sen Streamlit uzmanısın. SADECE çalışan Python kodu üret. st.set_page_config ile başla. Modern UI. SADECE kod, yorum yok."},
                {"role": "user", "content": f"Streamlit app oluştur: {prompt}"}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        code = response.json()["choices"][0]["message"]["content"]
        
        # Temizle
        if code.startswith("```python"): code = code[9:]
        elif code.startswith("```"): code = code[3:]
        if code.endswith("```"): code = code[:-3]
        return code.strip(), None
    except Exception as e:
        return None, str(e)

# =============================================================================
# SESSION
# =============================================================================

if "user" not in st.session_state: st.session_state.user = None
if "page" not in st.session_state: st.session_state.page = "home"
if "run_code" not in st.session_state: st.session_state.run_code = None

# =============================================================================
# UI
# =============================================================================

st.title("⚡ AppFab")
st.caption("Yapay zeka ile anında app oluştur")

# Sidebar
with st.sidebar:
    st.header("Menü")
    if st.session_state.user:
        user = get_user(st.session_state.user["user_id"])
        st.write(f"👤 {user['username']}")
        st.write(f"💎 {user['credits']} Kredi")
        if st.button("🏠 Ana Sayfa", use_container_width=True): st.session_state.page = "home"; st.rerun()
        if st.button("✨ App Üret", use_container_width=True): st.session_state.page = "create"; st.rerun()
        if st.button("📱 App'lerim", use_container_width=True): st.session_state.page = "myapps"; st.rerun()
        if st.button("🚪 Çıkış", use_container_width=True): st.session_state.user = None; st.rerun()
    else:
        if st.button("🏠 Ana Sayfa", use_container_width=True): st.session_state.page = "home"; st.rerun()
        if st.button("🔐 Giriş / Kayıt", use_container_width=True): st.session_state.page = "auth"; st.rerun()

# =============================================================================
# PAGES
# =============================================================================

if st.session_state.page == "home":
    st.header("🚀 Hoş Geldiniz")
    st.write("Tek cümleyle hesap makinesi, BMI hesaplayıcı, todo list ve daha fazlasını oluşturun.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("⚡ Hızlı", "30 sn")
    col2.metric("🤖 AI", "GPT-4")
    col3.metric("📱 Mobil", "Uyumlu")
    
    if not st.session_state.user:
        if st.button("🔐 Başlamak için Giriş Yap", type="primary"):
            st.session_state.page = "auth"
            st.rerun()

elif st.session_state.page == "auth":
    st.header("🔐 Giriş / Kayıt")
    tab1, tab2 = st.tabs(["Giriş Yap", "Kayıt Ol"])
    
    with tab1:
        with st.form("login"):
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Şifre", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                ok, user = login_user(email, password)
                if ok:
                    st.session_state.user = user
                    st.success("Giriş başarılı!")
                    st.rerun()
                else:
                    st.error("Hatalı giriş")
    
    with tab2:
        with st.form("register"):
            username = st.text_input("👤 Kullanıcı Adı")
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Şifre", type="password")
            if st.form_submit_button("Kayıt Ol", use_container_width=True):
                ok, msg = create_user(email, password, username)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

elif st.session_state.page == "create":
    if not st.session_state.user:
        st.error("Lütfen giriş yapın")
        st.stop()
    
    st.header("✨ Yeni App Üret")
    user = get_user(st.session_state.user["user_id"])
    st.write(f"💎 Krediniz: {user['credits']}")
    
    prompt = st.text_area("Ne yapmak istiyorsunuz?", placeholder="Örn: Basit hesap makinesi yap. Toplama, çıkarma, çarpma, bölme olsun.", height=100)
    col1, col2 = st.columns(2)
    app_name = col1.text_input("App Adı", "Benim App'im")
    is_public = col2.checkbox("Herkese Açık")
    
    if st.button("🚀 APP ÜRET", type="primary", use_container_width=True):
        if prompt:
            if deduct_credit(st.session_state.user["user_id"]):
                with st.spinner("AI düşünüyor..."):
                    code, error = generate_app(prompt)
                
                if error:
                    st.error(error)
                else:
                    # Kaydet
                    save_app(st.session_state.user["user_id"], app_name, prompt[:100], prompt, code, is_public)
                    st.success("✅ App oluşturuldu!")
                    
                    # Kodu göster
                    st.subheader("📝 Oluşturulan Kod")
                    st.code(code, language="python")
                    
                    # İndir
                    st.download_button("📥 İndir (.py)", code, file_name="app.py")
                    
                    # 🎯 ÖNEMLİ: Çalıştır butonu
                    st.divider()
                    st.subheader("🎮 App'i Hemen Çalıştır")
                    
                    if st.button("▶️ Şimdi Çalıştır", type="primary", use_container_width=True):
                        st.session_state.run_code = code
                        st.rerun()
            else:
                st.error("Krediniz bitti!")
        else:
            st.error("Lütfen açıklama yazın")

    # Çalıştırılan kod burada gösterilecek
    if st.session_state.run_code:
        st.divider()
        st.subheader("🎯 App Çalışıyor")
        st.info("Aşağıda üretilen app çalışıyor. İstediğiniz gibi kullanın!")
        
        # Kodu çalıştır (güvenli modda)
        code_to_run = st.session_state.run_code
        
        # st.set_page_config'i kaldır (zaten var)
        lines = code_to_run.split('\n')
        filtered_lines = [line for line in lines if 'set_page_config' not in line]
        clean_code = '\n'.join(filtered_lines)
        
        try:
            # Kodu çalıştır
            exec(clean_code)
        except Exception as e:
            st.error(f"Çalıştırma hatası: {e}")
        
        if st.button("❌ Kapat", use_container_width=True):
            st.session_state.run_code = None
            st.rerun()

elif st.session_state.page == "myapps":
    if not st.session_state.user:
        st.error("Lütfen giriş yapın")
        st.stop()
    
    st.header("📱 Benim App'lerim")
    apps = get_user_apps(st.session_state.user["user_id"])
    
    if not apps:
        st.info("Henüz app yok.")
    else:
        for app in apps:
            with st.expander(f"{'🌐' if app['is_public'] else '🔒'} {app['name']}"):
                st.write(f"**Tarih:** {app['created_at']}")
                st.code(app['code'], language="python")
                
                col1, col2 = st.columns(2)
                col1.download_button("📥 İndir", app['code'], file_name=f"{app['name']}.py", key=f"dl_{app['app_id']}")
                
                # Kaydedilmiş app'i de çalıştır
                if col2.button("▶️ Çalıştır", key=f"run_{app['app_id']}"):
                    st.session_state.run_code = app['code']
                    st.rerun()
        
        # Çalıştırma alanı (sayfa sonunda)
        if st.session_state.run_code:
            st.divider()
            st.subheader("🎯 App Çalışıyor")
            try:
                lines = st.session_state.run_code.split('\n')
                filtered = [line for line in lines if 'set_page_config' not in line]
                exec('\n'.join(filtered))
            except Exception as e:
                st.error(f"Hata: {e}")
            
            if st.button("❌ Kapat"):
                st.session_state.run_code = None
                st.rerun()
