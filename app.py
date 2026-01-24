import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os
import requests  # Обязательно нужно для Telegram
from auth import show_login_page

# --- 1. НАСТРОЙКИ ---
st.set_page_config(page_title="Магазин носков", layout="wide")

DB_FILE = 'socks.xlsx'
IMG_DIR = 'images'
if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

# --- 2. ПОДКЛЮЧЕНИЕ GOOGLE SHEETS ---
scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gspread_credentials"], scopes=scope)
client = gspread.authorize(creds)
sheet = client.open("socks_db")

items_sheet = sheet.worksheet("товары")
users_sheet = sheet.worksheet("аккаунты")
cart_sheet = sheet.worksheet("корзины")

# --- 3. СЕССИЯ И АВТОРИЗАЦИЯ ---
if 'user_phone' not in st.session_state:
    st.session_state.user_phone = None
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if "page" not in st.session_state:
    st.session_state.page = "Покупатель (Каталог)"

# Если не авторизован — показываем вход
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


def save_to_excel(data_dict):
    if os.path.exists(DB_FILE):
        df = pd.read_excel(DB_FILE)
    else:
        df = pd.DataFrame()
    new_row = pd.DataFrame([data_dict])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(DB_FILE, index=False)


# --- 5. МЕНЮ (SIDEBAR) ---
st.sidebar.success(f"👤 {st.session_state.user_name}")

# Простое меню без ложных счетчиков
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

    # Форма добавления
        with st.expander("➕ Добавить новый товар", expanded=True):
            with st.form("add_form", clear_on_submit=True):
                name = st.text_input("Название")
                c1, c2 = st.columns(2)
                cat = c1.selectbox("Категория", ["Мужские", "Женские", "Детские"])
                seas = c2.selectbox("Сезон", ["Лето", "Зима", "Демисезон"])
                qty = st.selectbox("В пачке", ["6", "10", "12", "14", "16"])
                tags = st.text_input("Описание")
                photo = st.file_uploader("Фото", type=['jpg', 'png'])

                if st.form_submit_button("Опубликовать"):
                    if photo and name:
                        # 1. Сохраняем фото локально (для отображения)
                        p_path = os.path.join(IMG_DIR, photo.name)
                        with open(p_path, "wb") as f:
                            f.write(photo.getbuffer())

                        # 2. ЗАПИСЫВАЕМ В GOOGLE ТАБЛИЦУ (вместо Excel)
                        # Важно: порядок должен совпадать с заголовками в таблице
                        items_sheet.append_row([
                            name,   # Название
                            cat,    # Категория
                            seas,   # Сезон
                            qty,    # Количество в пачке
                            tags,   # Описание
                            p_path  # Путь к фото
                        ])
                        
                        st.success("Товар успешно сохранен в Google Таблицу!")
                        st.rerun()
                    else:
                        st.error("Нужно название и фото!")

        # Список для удаления
        st.divider()
        st.subheader("🗑️ Удаление товаров")
        
        # Читаем данные из Google Таблицы
        all_items = items_sheet.get_all_records()
        if all_items:
            df_actual = pd.DataFrame(all_items)
            for i, row in df_actual.iterrows():
                c1, c2, c3 = st.columns([1, 3, 1])
                
                with c1:
                    img_path = str(row['фото'])
                    if os.path.exists(img_path):
                        st.image(img_path, width=350)
                    else:
                        st.write("🖼️")
                
                c2.write(f"**{row['Название']}**")
                
                # Удаление из Google Таблицы (i+2 т.к. в Google нумерация с 1 и есть заголовок)
                if c3.button("Удалить", key=f"del_admin_{i}"):
                    items_sheet.delete_rows(i + 2)
                    st.success("Удалено из облака!")
                    st.rerun()
        else:
            st.info("В Google Таблице пока нет товаров.")
# --- 7. СТРАНИЦА: КАТАЛОГ ---
elif st.session_state.page == "Покупатель (Каталог)":
    st.title("🧦 Каталог носков")
    
    # 1. Загружаем данные из Google Sheets (лист "товары")
    all_values = items_sheet.get_all_values()
    
    if len(all_values) > 1:
        # Первая строка — заголовки, остальное — товары
        data = all_values[1:]
        
        # --- БЛОК ФИЛЬТРОВ (СВЕРХУ) ---
        with st.container():
            f1, f2 = st.columns(2)
            sel_cat = f1.selectbox("Категория", ["Все", "Мужские", "Женские", "Детские"])
            sel_season = f2.selectbox("Сезон", ["Все", "Лето", "Зима", "Демисезон"])
        
        st.divider()      
        # --- ВЫВОД ТОВАРОВ ---
        for i, row in enumerate(data):
            
            # --- ВАШ ТЕКУЩИЙ ПОРЯДОК В ТАБЛИЦЕ ---
            # Судя по скрину: A=Название, B=Категория, C=Сезон
            
            p_name = row[0]     # Колонка A - Название ("Gg aa")
            p_cat = row[1]      # Колонка B - Категория ("Мужские")
            p_season = row[2]   # Колонка C - Сезон ("Лето")
            p_qty = row[3]      # Колонка D - Кол-во
            p_tags = row[4]     # Колонка E - Теги
            p_photo = row[5] if len(row) > 5 else "" # Колонка F - Фото
            
            # -----------------------------------------------------------

            # Фильтрация
            if sel_cat != "Все" and p_cat != sel_cat: continue
            if sel_season != "Все" and p_season != sel_season: continue

            with st.container():
                c1, c2 = st.columns([1, 2])
                
                with c1:
                    if os.path.exists(str(p_photo)):
                        st.image(p_photo, use_container_width=True)
                    else:
                        st.write("🖼️")

                with c2:
                    st.subheader(p_name)  # Теперь тут будет "Gg aa"
                    st.write(f"🏷️ **{p_cat}** | ❄️ **{p_season}**")
                    st.caption(f"В пачке: {p_qty} шт. | #{p_tags}")

                    qty_key = f"qty_{i}_{p_name}"
                    comm_key = f"comm_{i}_{p_name}"
                    
                    col_q, col_c = st.columns([1, 2])
                    with col_q:
                        st.number_input("Кол-во", min_value=1, value=1, key=qty_key)
                    with col_c:
                        st.text_input("Комментарий", placeholder="Цвет...", key=comm_key)

                    if st.button("🛒 В корзину", key=f"btn_{i}_{p_name}", use_container_width=True):
                        cart_sheet.append_row([
                            str(st.session_state.user_phone),
                            str(p_name),
                            int(st.session_state[qty_key]),
                            str(p_photo),
                            str(st.session_state[comm_key])
                        ])
                        st.toast(f"✅ {p_name} добавлен!")
            st.divider()
    else:
        st.info("В каталоге пока нет товаров. Добавьте их через панель администратора.")
# --- 8. СТРАНИЦА: КОРЗИНА ---
elif st.session_state.page == "📦 Заказ":
    st.title("🛒 Ваш заказ")

    # Получаем данные
    all_rows = cart_sheet.get_all_values()

    if len(all_rows) > 1:
        df_cart = pd.DataFrame(all_rows[1:], columns=all_rows[0])
        my_phone = str(st.session_state.user_phone).strip().replace('+', '')

        # Фильтрация по телефону (1-я колонка)
        my_items = df_cart[df_cart.iloc[:, 0].str.replace('+', '').str.strip() == my_phone]

        if not my_items.empty:
            for idx, item in my_items.iterrows():
                with st.container():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    path = item.iloc[3]

                    with c1:  # или c1, смотря как названа колонка
                        image_path = str(item.iloc[3])
                        if os.path.exists(image_path):
                            st.image(image_path, width=100)
                        else:
                            st.write("🖼️")
                    with c2:
                        st.subheader(item.iloc[1])
                        st.write(f"**{item.iloc[2]} пачек.**")
                        if len(item) > 4 and item.iloc[4]:
                            st.info(f"💬 {item.iloc[4]}")

                    if c3.button("❌", key=f"del_{idx}"):
                        # Удаляем (индекс + 2 для учета заголовка и нумерации с 1)
                        cart_sheet.delete_rows(int(idx) + 2)
                        st.rerun()
                st.divider()

            if st.button("🚀 Отправить заказ", use_container_width=True):
                msg = f"📦 *ЗАКАЗ*\n👤 {st.session_state.user_name}\n📞 {st.session_state.user_phone}\n---\n"
                for _, r in my_items.iterrows():
                    msg += f"• {r.iloc[1]} — {r.iloc[2]} пачек."
                    if len(r) > 4 and r.iloc[4]: msg += f" ({r.iloc[4]})"
                    msg += "\n"

                if send_telegram_message(msg):
                    st.success("Отправлено!")
                    with st.spinner('Очистка...'):
                        # Удаляем строки снизу вверх
                        all_data = cart_sheet.get_all_values()
                        target = str(st.session_state.user_phone).strip().replace('+', '')
                        for i in range(len(all_data) - 1, 0, -1):
                            if all_data[i][0].strip().replace('+', '') == target:
                                cart_sheet.delete_rows(i + 1)
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Ошибка сети")
        else:
            st.info("Корзина пуста.")
    else:

        st.info("Корзина пуста.")













