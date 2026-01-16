
import streamlit as st
import pandas as pd


def show_login_page(users_sheet, cart_sheet):
    st.title("🔐 Авторизация")

    tab1, tab2 = st.tabs(["Вход", "Регистрация"])

    # Список популярных кодов стран (можно дополнить)
    country_codes = ["+7", "+996", "+380", "+375", "+994", "+998"]

    # Загружаем пользователей
    all_users = users_sheet.get_all_records()
    df_users = pd.DataFrame(all_users)
    if not df_users.empty:
        # Чистим базу от мусора (пробелы, точки)
        df_users['phone'] = df_users['phone'].astype(str).str.strip().str.replace('.0', '', regex=False)

    with tab1:
        with st.form("login_form"):
            st.write("### Войти")
            col1, col2 = st.columns([1, 3])
            with col1:
                code = st.selectbox("Код", country_codes, key="login_code")
            with col2:
                phone = st.text_input("Номер телефона (без кода)")

            password = st.text_input("Пароль", type="password")

            if st.form_submit_button("Войти"):
                # Собираем то, что ввел пользователь, и оставляем только цифры
                entered_full = f"{code}{phone.strip()}"
                clean_entered = "".join(filter(str.isdigit, entered_full))

                if not df_users.empty:
                    # Чистим номера из базы (убираем +, пробелы и .0)
                    df_users['search_phone'] = df_users['phone'].astype(str).str.replace(r'\D', '', regex=True)

                    # Ищем совпадение по чистым цифрам
                    user_data = df_users[df_users['search_phone'] == clean_entered]

                    if not user_data.empty:
                        db_pass = str(user_data.iloc[0]['password']).strip().replace('.0', '')
                        if db_pass == password.strip():
                            st.session_state.user_phone = entered_full
                            st.session_state.user_name = user_data.iloc[0]['name']
                            st.success(f"Привет, {st.session_state.user_name}!")
                            st.rerun()
                        else:
                            st.error("❌ Неверный пароль")
                    else:
                        st.error(f"Пользователь с номером {clean_entered} не найден в базе")
    with tab2:
        with st.form("reg_form"):
            st.write("### Регистрация")
            name = st.text_input("Ваше имя")
            col1, col2 = st.columns([1, 3])
            with col1:
                reg_code = st.selectbox("Код", country_codes, key="reg_code_ui")
            with col2:
                reg_phone = st.text_input("Номер телефона (без кода)")

            reg_password = st.text_input("Придумайте пароль", type="password")

            if st.form_submit_button("Создать аккаунт"):
                if reg_phone and name and reg_password:
                    # Формируем полный номер для сохранения
                    full_reg_phone = f"{reg_code}{reg_phone.strip()}"

                    # 1. Проверяем, нет ли уже такого номера (сравниваем только цифры)
                    clean_reg = "".join(filter(str.isdigit, full_reg_phone))

                    already_exists = False
                    if not df_users.empty:
                        # Создаем временный список очищенных номеров из базы
                        existing_phones = df_users['phone'].astype(str).str.replace(r'\D', '', regex=True).tolist()
                        if clean_reg in existing_phones:
                            already_exists = True

                    if already_exists:
                        st.warning("⚠️ Этот номер уже зарегистрирован! Перейдите во вкладку 'Вход'")
                    else:
                        # 2. Записываем в Google Таблицу
                        # Добавляем кавычку ' перед номером, чтобы Google сохранил его как текст
                        users_sheet.append_row(["'" + full_reg_phone, name, str(reg_password)])

                        # 3. Показываем сообщение и ПЕРЕЗАГРУЖАЕМ, чтобы обновить данные в памяти
                        st.success(f"✅ Аккаунт {full_reg_phone} создан!")
                        st.info("Теперь введите данные во вкладке 'Вход'")
                        # Небольшая задержка перед перезагрузкой для пользователя
                        st.balloons()
                else:
                    st.error("Заполните все поля регистрации!")