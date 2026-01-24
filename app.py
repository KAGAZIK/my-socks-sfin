import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import os
import base64
import requests
from auth import show_login_page

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="Магазин носков", layout="wide")

# --- 2. ПОДКЛЮЧЕНИЕ GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gspread_credentials"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("socks_db")

items_sheet = sheet.worksheet("товары")
users_sheet = sheet.worksheet("аккаунты")
cart_sheet = sheet.worksheet("корзины")

def upload_to_imgbb(file_obj):
    try:
        api_key = st.secrets["IMGBB_API_KEY"]
        url = "https://api.imgbb.com/1/upload"
        file_content = file_obj.read()
        base64_image = base64.b64encode(file_content)
        payload = {"key": api_key, "image": base64_image}
        response = requests.post(url, payload)
        res_data = response.json()
        if res_data["status"] == 200:
            return res_data["data"]["url"]
        else:
            st.error(f"Ошибка ImgBB: {res_data['error']['message']}")
            return None
    except Exception as e:
        st.error(f"Ошибка при загрузке: {e}")
        return None

# --- 3. СЕССИЯ И АВТОРИЗАЦИЯ ---
if 'user_phone' not in st.session_state:
    st.session_state.user_phone = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if "page" not in st.session_state:
    st.session_state.page = "Покупатель (Каталог)"

if st.session_state.user_phone is None:
    show_login_page(users_sheet, cart_sheet)
    st.stop()

# --- 4. ФУНКЦИИ ---
def send_telegram_message(text):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
        return True
    except:
        return False

# --- 5. МЕНЮ (SIDEBAR) ---
st.sidebar.success(f"👤 {st.session_state.user_name}")
menu_options = ["Покупатель (Каталог)", "📦 Заказ", "Продавец (Добавить)"]
st.session_state.page = st.sidebar.radio("Перейти к:", menu_options, index=menu_options.index(st.session_state.page))

if st.sidebar.button("Выйти"):
    st.session_state.user_phone = None
    st.rerun()

# --- 6. СТРАНИЦА: ПРОДАВЕЦ (АДМИНКА) ---
if st.session_state.page == "Продавец (Добавить)":
    st.title("🔐 Панель администратора")
    if "admin_auth" not in st.session_state:
        st.session_state.admin_auth = False

    if not st.session_state.admin_auth:
        if st.text_input("Введите секретный код:", type="password") == st.secrets["ADMIN"]:
            if st.button("Войти"):
                st.session_state.admin_auth = True
                st.rerun()
    else:
        if st.sidebar.button("Выйти из админки"):
            st.session_state.admin_auth = False
            st.rerun()

        with st.expander("➕ Добавить новый товар", expanded=True):
            with st.form("add_form", clear_on_submit=True):
                uploaded_photo = st.file_uploader("Выберите фото", type=['jpg', 'jpeg', 'png'])
                name = st.text_input("Название")
                c1, c2 = st.columns(2)
                cat = c1.selectbox("Категория", ["Мужские", "Женские", "Детские"])
                seas = c2.selectbox("Сезон", ["Лето", "Зима", "Демисезон"])
                qty = st.selectbox("В пачке", ["6", "10", "12", "14", "16"])
                tags = st.text_input("Описание")

                if st.form_submit_button("Опубликовать товар"):
                    if uploaded_photo and name:
                        with st.spinner("⏳ Загружаем фото в облако..."):
                            public_url = upload_to_imgbb(uploaded_photo)
                            if public_url:
                                items_sheet.append_row([str(name), str(cat), str(seas), str(qty), str(tags), str(public_url)])
                                st.success("✅ Товар успешно добавлен!")
                                st.rerun()

        st.divider()
        st.subheader("🗑️ Удаление товаров")
        all_items = items_sheet.get_all_records()
        if all_items:
            for i, row in enumerate(all_items):
                c1, c2, c3 = st.columns([1, 3, 1])
                with c1:
                    img = row.get('фото', '')
                    if str(img).startswith("http"): st.image(img, width=100)
                c2.write(f"**{row.get('Название', 'Без названия')}**")
                if c3.button("Удалить", key=f"del_adm_{i}"):
                    items_sheet.delete_rows(i + 2)
                    st.rerun()

# --- 7. СТРАНИЦА: КАТАЛОГ ---
elif st.session_state.page == "Покупатель (Каталог)":
    st.title("🧦 Каталог носков")
    all_values = items_sheet.get_all_values()
    
    if len(all_values) > 1:
        headers = all_values[0]
        data = all_values[1:]
        
        f1, f2 = st.columns(2)
        sel_cat = f1.selectbox("Категория", ["Все", "Мужские", "Женские", "Детские"])
        sel_season = f2.selectbox("Сезон", ["Все", "Лето", "Зима", "Демисезон"])
        st.divider()      

        for i, row in enumerate(data):
            p_name, p_cat, p_season, p_qty, p_tags, p_photo = row[0], row[1], row[2], row[3], row[4], row[5]
            if sel_cat != "Все" and p_cat != sel_cat: continue
            if sel_season != "Все" and p_season != sel_season: continue

            with st.container():
                c1, c2 = st.columns([1, 2])
                with c1:
                    if str(p_photo).startswith("http"): st.image(p_photo, use_container_width=True)
                with c2:
                    st.subheader(p_name)
                    st.write(f"🏷️ **{p_cat}** | ❄️ **{p_season}**")
                    st.caption(f"В пачке: {p_qty} шт. | #{p_tags}")
                    
                    col_q, col_c = st.columns([1, 2])
                    q_val = col_q.number_input("Кол-во", min_value=1, value=1, key=f"q_{i}")
                    c_val = col_c.text_input("Комментарий", placeholder="Цвет...", key=f"c_{i}")

                    if st.button("🛒 заказать", key=f"btn_{i}", use_container_width=True):
                        cart_sheet.append_row([str(st.session_state.user_phone), p_name, q_val, p_photo, c_val])
                        st.toast(f"✅ {p_name} добавлен!")
            st.divider()

# --- 8. СТРАНИЦА: КОРЗИНА ---
elif st.session_state.page == "📦 Заказ":
    st.title("🛒 Ваш заказ")
    rows = cart_sheet.get_all_values()
    if len(rows) > 1:
        headers = rows[0]
        my_phone = str(st.session_state.user_phone).strip().replace('+', '')
        
        my_items = []
        for idx, r in enumerate(rows[1:]):
            if r[0].strip().replace('+', '') == my_phone:
                my_items.append({'idx': idx + 2, 'data': r})

        if my_items:
            for item in my_items:
                r = item['data']
                with st.container():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    with c1:
                        if str(r[3]).startswith("http"): st.image(r[3], width=100)
                    with c2:
                        st.subheader(r[1])
                        st.write(f"**{r[2]} пачек.**")
                        if r[4]: st.info(f"💬 {r[4]}")
                    if c3.button("❌", key=f"del_cart_{item['idx']}"):
                        cart_sheet.delete_rows(item['idx'])
                        st.rerun()
            
            if st.button("🚀 Отправить заказ", use_container_width=True):
                msg = f"📦 ЗАКАЗ\n👤 {st.session_state.user_name}\n📞 {st.session_state.user_phone}\n"
                for it in my_items:
                    msg += f"• {it['data'][1]} — {it['data'][2]} шт.\n"
                
                if send_telegram_message(msg):
                    # Очистка корзины для этого пользователя
                    all_data = cart_sheet.get_all_values()
                    for i in range(len(all_data) - 1, 0, -1):
                        if all_data[i][0].strip().replace('+', '') == my_phone:
                            cart_sheet.delete_rows(i + 1)
                    st.balloons()
                    st.rerun()
    else:
        st.info("Корзина пуста.")
