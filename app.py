"""
AppFab - Basit Çalışan Versiyon
"""

import streamlit as st
import requests
from datetime import datetime
import sqlite3
import hashlib
import secrets

# Page config
st.set_page_config(
    page_title="AppFab - AI App Generator",
    page_icon="⚡",
    layout="wide"
)

# OpenAI API Key
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
# AUTH
# =============================================================================

def create_user(email, password, username):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    if c.fetchone():
        return False, "Email kayıtlı", None
    
    user_id = f"user_{secrets.token_hex(8)}"
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("INSERT INTO users (user_id, email, username, password_hash, credits) VALUES (?,?,?,?,10)",
              (user_id, email, username, pwd_hash))
    conn.commit()
    conn.close()
    
    return True, "Kayıt başarılı!", {"user_id": user_id, "email": email, "username": username}

def login_user(email, password):
    conn = get_db()
    c = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE email=? AND password_hash=?", (email, pwd_hash))
    user = c.fetchone()
    conn.close()
    
    if user:
        return True, "Giriş başarılı", dict(user)
    return False, "Email veya şifre hatalı", None

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

def deduct_credit(user_id):
    user = get_user(user_id)
    if user["is_pro"]:
        return True
    if user["credits"] > 0:
        conn = get_db()
        c = conn.cursor()
        c.execute("UPDATE users SET credits = credits - 1 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        return True
    return False

# =============================================================================
# APP MANAGER
# =============================================================================

def save_app(user_id, name, description, prompt, code, is_public):
    conn = get_db()
    c = conn.cursor()
    app_id = f"app_{int(datetime.now().timestamp())}"
    c.execute("INSERT INTO apps (app_id, user_id, name, description, prompt, code, is_public) VALUES (?,?,?,?,?,?,?)",
              (app_id, user_id, name, description, prompt, code, is_public))
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

def get_public_apps():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM apps WHERE is_public=1 ORDER BY likes DESC")
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
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "Sen Streamlit uzmanısın. SADECE çalışan Python kodu üret. st.set_page_config ile başla. Modern UI kullan. SADECE kod, açıklama yok."},
                {"role": "user", "content": f"Streamlit app oluştur: {prompt}"}
            ],
            "temperature": 0.7,
            "max_tokens": 2000
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        code = data["choices"][0]["message"]["content"]
        
        # Kod bloğunu temizle
        if code.startswith("```python"):
            code = code[9:]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        
        return code.strip(), None
        
    except Exception as e:
        return None, str(e)

# =============================================================================
# SESSION STATE
# =============================================================================

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "home"

# =============================================================================
# UI
# =============================================================================

st.title("⚡ AppFab - AI App Generator")
st.caption("Prompt yaz → App oluştur → Anında kullan")

# Sidebar navigation
with st.sidebar:
    st.header("Menü")
    
    if st.session_state.user:
        user = get_user(st.session_state.user["user_id"])
        st.write(f"👤 {user['username']}")
        st.write(f"💎 {user['credits']} Kredi")
        
        if st.button("🏠 Ana Sayfa"):
            st.session_state.page = "home"
            st.rerun()
        if st.button("✨ App Üret"):
            st.session_state.page = "create"
            st.rerun()
        if st.button("📱 App'lerim"):
            st.session_state.page = "myapps"
            st.rerun()
        if st.button("🌐 Galeri"):
            st.session_state.page = "gallery"
            st.rerun()
        if st.button("🚪 Çıkış"):
            st.session_state.user = None
            st.session_state.page = "home"
            st.rerun()
    else:
        if st.button("🏠 Ana Sayfa"):
            st.session_state.page = "home"
            st.rerun()
        if st.button("🔐 Giriş / Kayıt"):
            st.session_state.page = "auth"
            st.rerun()
        if st.button("🌐 Galeri"):
            st.session_state.page = "gallery"
            st.rerun()

# =============================================================================
# PAGES
# =============================================================================

if st.session_state.page == "home":
    st.header("🚀 Hoş Geldiniz")
    st.write("Yapay zeka ile tek cümlede uygulamalar oluşturun.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("⚡ Hızlı", "30 saniye")
    with col2:
        st.metric("🤖 AI Destekli", "GPT-4")
    with col3:
        st.metric("💾 Kayıtlı", "Kalıcı")
    
    st.divider()
    
    if not st.session_state.user:
        st.info("Başlamak için giriş yapın veya kayıt olun.")
        if st.button("🔐 Giriş Yap / Kayıt Ol", type="primary"):
            st.session_state.page = "auth"
            st.rerun()
    else:
        st.success("Hazırsınız! Sol menüden 'App Üret' seçeneğine tıklayın.")

elif st.session_state.page == "auth":
    st.header("🔐 Giriş / Kayıt")
    
    tab1, tab2 = st.tabs(["Giriş Yap", "Kayıt Ol"])
    
    with tab1:
        with st.form("login"):
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Şifre", type="password")
            if st.form_submit_button("Giriş Yap", use_container_width=True):
                success, msg, user = login_user(email, password)
                if success:
                    st.session_state.user = user
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
    
    with tab2:
        with st.form("register"):
            username = st.text_input("👤 Kullanıcı Adı")
            email = st.text_input("📧 Email")
            password = st.text_input("🔒 Şifre", type="password")
            if st.form_submit_button("Kayıt Ol", use_container_width=True):
                success, msg, user = create_user(email, password, username)
                if success:
                    st.session_state.user = user
                    st.success(msg + " 10 kredi hediye!")
                    st.rerun()
                else:
                    st.error(msg)

elif st.session_state.page == "create":
    if not st.session_state.user:
        st.warning("Lütfen önce giriş yapın.")
        st.stop()
    
    st.header("✨ Yeni App Üret")
    
    user = get_user(st.session_state.user["user_id"])
    st.write(f"💎 Krediniz: {user['credits']}")
    
    if user["credits"] <= 0 and not user["is_pro"]:
        st.error("Krediniz bitti!")
        st.stop()
    
    prompt = st.text_area("Ne yapmak istiyorsunuz?", 
                         placeholder="Örn: Basit bir hesap makinesi yap. Toplama, çıkarma, çarpma, bölme olsun.",
                         height=100)
    
    col1, col2 = st.columns(2)
    with col1:
        app_name = st.text_input("App Adı", "Benim App'im")
    with col2:
        is_public = st.checkbox("Herkese Açık", value=False)
    
    if st.button("🚀 APP ÜRET", type="primary", use_container_width=True):
        if not prompt:
            st.error("Lütfen bir açıklama yazın.")
        else:
            with st.spinner("AI düşünüyor..."):
                code, error = generate_app(prompt)
            
            if error:
                st.error(f"Hata: {error}")
            else:
                # Kredi düş
                if deduct_credit(st.session_state.user["user_id"]):
                    # Kaydet
                    save_app(st.session_state.user["user_id"], app_name, prompt[:100], prompt, code, is_public)
                    st.success("✅ App oluşturuldu ve kaydedildi!")
                    
                    # Göster
                    st.subheader("📝 Oluşturulan Kod")
                    st.code(code, language="python")
                    
                    # İndir
                    st.download_button("📥 app.py İndir", code, file_name="app.py")
                else:
                    st.error("Kredi hatası")

elif st.session_state.page == "myapps":
    if not st.session_state.user:
        st.warning("Lütfen önce giriş yapın.")
        st.stop()
    
    st.header("📱 Benim App'lerim")
    
    apps = get_user_apps(st.session_state.user["user_id"])
    
    if not apps:
        st.info("Henüz app oluşturmadınız.")
    else:
        for app in apps:
            with st.expander(f"{'🌐' if app['is_public'] else '🔒'} {app['name']}"):
                st.write(f"**Açıklama:** {app['description']}")
                st.write(f"**Tarih:** {app['created_at']}")
                st.code(app['code'], language="python")
                st.download_button("📥 İndir", app['code'], file_name=f"{app['name']}.py", key=app['app_id'])

elif st.session_state.page == "gallery":
    st.header("🌐 Topluluk Galerisi")
    
    apps = get_public_apps()
    
    if not apps:
        st.info("Henüz public app yok.")
    else:
        for app in apps:
            with st.expander(f"❤️ {app['likes']} | {app['name']}"):
                st.write(f"**Açıklama:** {app['description']}")
                st.code(app['code'], language="python")
