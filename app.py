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
                qty = st.selectbox("В пачке", ["6","10", "12", "14", "16"])
                tags = st.text_input("Хештеги")
                photo = st.file_uploader("Фото", type=['jpg', 'png'])

                if st.form_submit_button("Опубликовать"):
                    if photo and name:
                        p_path = os.path.join(IMG_DIR, photo.name)
                        with open(p_path, "wb") as f:
                            f.write(photo.getbuffer())

                        save_to_excel({
                            "Категория": cat, "Сезон": seas, "Название": name,
                            "Количество в пачке": qty, "Теги": tags, "фото": p_path
                        })
                        st.success("Товар добавлен!")
                        st.rerun()
                    else:
                        st.error("Нужно название и фото!")

        # Список для удаления
        st.divider()
        st.subheader("🗑️ Удаление товаров")
        if os.path.exists(DB_FILE):
            df_actual = pd.read_excel(DB_FILE)
            if not df_actual.empty:
                for i, row in df_actual.iterrows():
                    c1, c2, c3 = st.columns([1, 3, 1])
                    img_path = str(row['фото'])
                    if os.path.exists(img_path):
                        c1.image(img_path, width=200)
                    else:
                        c1.write("🖼️")
                    c2.write(f"**{row['Название']}**")
                    if c3.button("Удалить", key=f"del_admin_{i}"):
                        df_actual.drop(i).to_excel(DB_FILE, index=False)
                        st.success("Удалено!")
                        st.rerun()
            else:
                st.info("Нет товаров.")
        else:
            st.warning("База данных пуста.")

# --- 7. СТРАНИЦА: КАТАЛОГ ---
elif st.session_state.page == "Покупатель (Каталог)":
    st.title("🧦 Каталог носков")

    if os.path.exists(DB_FILE):
        df = pd.read_excel(DB_FILE)

        # --- 1. ФИЛЬТРЫ СВЕРХУ ---
        # Создаем контейнер для фильтров
        with st.container():
            st.subheader("🔍 Поиск")
            filt_col1, filt_col2 = st.columns(2)

            with filt_col1:
                categories = ["Все", "Мужские", "Женские", "Детские"]
                sel_cat = st.selectbox("Категория", categories)

            with filt_col2:
                seasons = ["Все", "Лето", "Зима", "Демисезон"]
                sel_season = st.selectbox("Сезон", seasons)

        st.divider()  # Линия-разделитель между фильтрами и товарами

        # --- 2. ЛОГИКА ФИЛЬТРАЦИИ ---
        filtered_df = df.copy()

        if sel_cat != "Все":
            filtered_df = filtered_df[filtered_df["Категория"] == sel_cat]

        if sel_season != "Все":
            filtered_df = filtered_df[filtered_df["Сезон"] == sel_season]

        # --- 3. ВЫВОД ТОВАРОВ ---
        if not filtered_df.empty:
            for index, row in filtered_df.iterrows():
                with st.container():
                    # Пропорции колонок: Картинка (1) и Информация (2)
                    c1, c2 = st.columns([1, 2])

                    with c1:
                        # use_container_width=True растягивает фото на всю ширину колонки
                        if os.path.exists(str(row['фото'])):
                            st.image(row['фото'], use_container_width=True)
                        else:
                            st.write("🖼️ Нет фото")

                    with c2:
                        st.subheader(row['Название'])
                        # Красивые плашки с информацией
                        st.write(f"🏷️ **{row['Категория']}** |  ❄️ **{row['Сезон']}**")
                        st.caption(f"В пачке: {row['Количество в пачке']} шт. | #{row['Теги']}")

                        qty_key = f"qty_{index}"
                        comm_key = f"comm_{index}"

                        # Делаем ввод компактнее
                        col_input1, col_input2 = st.columns([1, 2])
                        with col_input1:
                            st.number_input("Кол-во", min_value=1, value=1, key=qty_key)
                        with col_input2:
                            st.text_input("Коммент", placeholder="Размер/Цвет", key=comm_key)

                        # Кнопка на всю ширину для удобства (особенно с телефона)
                        if st.button("🛒 Заказать", key=f"btn_{index}", use_container_width=True):
                            selected_qty = st.session_state[qty_key]
                            selected_comm = st.session_state[comm_key]

                            cart_sheet.append_row([
                                str(st.session_state.user_phone),
                                str(row['Название']),
                                int(selected_qty),
                                str(row['фото']),
                                str(selected_comm)
                            ])
                            st.toast(f"✅ {row['Название']} добавлено!")
                st.divider()
        else:
            st.info("📭 Товаров с такими параметрами пока нет.")

    else:
        st.warning("База товаров еще не создана. Зайдите в Админку.")
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



