from aiogram.types import InlineKeyboardMarkup

from .util import Button
# from .util import get_close_button
from .util import get_condition_smile
from .util import get_paging_button
from .util import split_array
from .util import get_back_button
from .util import get_date_by_ind

from bot.functions import month_translate
from bot.functions import week_day_translate
from bot.functions import get_week_day_name_by_id

from bot.misc import Donate
from bot.misc import Communicate
from bot.misc import GoogleDrive


def type_names() -> InlineKeyboardMarkup:
    """Выбор профиля"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    student_btn = Button("Студент").inline("g_list")
    teacher_btn = Button("Преподаватель").inline("t_list")

    keyboard.add(student_btn)
    keyboard.add(teacher_btn)

    return keyboard


def groups__list(group__name_array: list,
                 course: int = 1,
                 add_back_button: bool = False,
                 callback: str = "g_list",
                 last_callback_data: str = "s",
                 row_width: int = 4) -> InlineKeyboardMarkup:
    """Список групп"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)
    buttons = []

    for group__id, group__name in group__name_array[course - 1][0].items():
        group__btn = Button(group__name).inline(f"{last_callback_data} {callback} {course} gc {group__id}")
        buttons.append(group__btn)

    keyboard.add(*buttons)

    paging_button_array = []

    if course > 1:
        paging_left_btn = get_paging_button(f"{last_callback_data} {callback} {course - 1}")
        paging_button_array.append(paging_left_btn)

    if course < len(group__name_array) and course < 4:
        paging_right_btn = get_paging_button(f"{last_callback_data} {callback} {course + 1}", direction="right")
        paging_button_array.append(paging_right_btn)

    keyboard.add(*paging_button_array)

    if add_back_button:
        keyboard.add(get_back_button(last_callback_data))

    return keyboard


def teachers_list(teacher_names_array: list,
                  start_: int = 0,
                  offset: int = 15,
                  add_back_button: bool = False,
                  callback: str = "t_list",
                  last_callback_data: str = "s",
                  row_width: int = 2) -> InlineKeyboardMarkup:
    """Список преподавателей"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)
    buttons = []

    for teacher_info in teacher_names_array[start_:start_ + offset]:
        [teacher_id, teacher_name] = teacher_info
        teacher_btn = Button(teacher_name).inline(f"{last_callback_data} {callback} {start_} tc {teacher_id}")
        buttons.append(teacher_btn)

    keyboard.add(*buttons)

    paging_button_array = []

    if start_ > 0:
        paging_left_btn = get_paging_button(f"{last_callback_data} {callback} {start_ - offset}")
        paging_button_array.append(paging_left_btn)

    if (start_ + offset) < len(teacher_names_array):
        paging_right_btn = get_paging_button(f"{last_callback_data} {callback} {start_ + offset}",
                                             direction="right")
        paging_button_array.append(paging_right_btn)

    keyboard.add(*paging_button_array)

    if add_back_button:
        keyboard.add(get_back_button(last_callback_data))

    return keyboard


def create_name_list(keyboard: InlineKeyboardMarkup,
                     names_array: list,
                     short_type_name: str,
                     row_width: int = 1) -> InlineKeyboardMarkup:
    """Список групп/преподавателей в меню настроек"""
    names_array_dict = {}
    for one_name in names_array:
        [id_, name_, spam_state] = one_name
        names_array_dict[name_] = [id_, spam_state]

    names_sort = sorted(names_array_dict.keys())
    for row_names in split_array(names_sort, row_width):
        name_list_button = []
        for name_ in row_names:
            [id_, spam_state] = names_array_dict[name_]
            smile_spam_state = '🌀' if spam_state == 'true' else ''  # 🌀 🔰 ▫ 📍

            group_btn = Button(f"{name_} {smile_spam_state}").inline(f"s {short_type_name}c {id_}")
            name_list_button.append(group_btn)
        keyboard.add(*name_list_button)

    return keyboard


def user_settings(user_settings_data: list,
                  row_width_group_: int = 3,
                  row_width_teacher: int = 2,
                  row_width: int = 3) -> InlineKeyboardMarkup:
    """Меню настроек"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)

    [type_name,
     name_,
     name_id,
     groups_array,
     teachers_array] = user_settings_data[0:5]

    short_type_name = {'group_': 'g', 'teacher': 't'}.get(type_name)

    main_subscribe_btn = Button(f"⭐ {name_}").inline(f"s {short_type_name}c {name_id}")
    groups_list_btn = Button('👨🏻‍🎓 Группы 👩🏻‍🎓').inline("s g_list 1")
    teacher_list_btn = Button('👨🏻‍🏫 Преподаватели 👩🏻‍🏫').inline("s t_list 0")

    group_first_row = [groups_list_btn]
    teacher_first_row = [teacher_list_btn]

    # create_name_list - group
    if name_id is not None and short_type_name == 'g':
        group_first_row.append(main_subscribe_btn)

    keyboard.add(*group_first_row)

    # group names
    keyboard = create_name_list(keyboard, groups_array, "g", row_width=row_width_group_)

    # create_name_list - teacher
    if name_id is not None and short_type_name == 't':
        teacher_first_row.append(main_subscribe_btn)

    keyboard.add(*teacher_first_row)

    # teacher names
    keyboard = create_name_list(keyboard, teachers_array, "t", row_width=row_width_teacher)

    call_schedule_btn = Button("⏰").inline("s cs")
    main_settings_btn = Button("⚙").inline("s ms")
    support_btn = Button("🌝").inline("s support")

    keyboard.add(call_schedule_btn, main_settings_btn, support_btn)

    # keyboard.add(get_close_button())

    return keyboard


def personal_account_headman_or_form_master():
    """Личный кабинет Старосты или Классного руководителя"""
    pass


def main_settings(user_settings_data: list, row_width: int = 2) -> InlineKeyboardMarkup:
    """Меню основных настроек"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)

    [spamming,
     empty_spamming,
     pin_msg,
     view_name,
     view_type_lesson_mark,
     view_week_day,
     view_add,
     view_time,
     view_dpo_info] = user_settings_data[5:14]

    button_info = {'spamming': ['🔔 Рассылка', spamming],
                   'empty_spamming': ['...при отсутствии', empty_spamming],
                   'pin_msg': ['📌 Закреплять', pin_msg],
                   'view_name': ['ℹ Заголовок', view_name],
                   'view_type_lesson_mark': ['🔘 Маркировка', view_type_lesson_mark],
                   'view_week_day': ['День недели', view_week_day],
                   'view_add': ['🏷 Подробно', view_add],
                   'view_time': ['⌚ Время', view_time],
                   'view_dpo_info': ['ДПО', view_dpo_info]}

    for key, val in button_info.items():
        text = val[0]
        bool_obj = val[1]
        text_btn = Button(text).inline(f"settings_info {key}")
        condition_text = Button(get_condition_smile(bool_obj)).inline(f"update_main_settings_bool {key}")
        keyboard.row(text_btn, condition_text)

    statement_template_btn = Button("Шаблоны ведомостей").inline("", url=GoogleDrive.SAMPLES)
    keyboard.add(statement_template_btn)

    keyboard.add(get_back_button("s"))

    return keyboard


def support(callback_data: str, last_callback_data: str) -> InlineKeyboardMarkup:
    """Меню поддержки"""
    keyboard = InlineKeyboardMarkup()

    # vk_btn = Button('💬 Вконтакте 💬').inline("", url=Communicate.DEVELOPER_VK)
    tg_btn = Button('Telegram').inline("", url=Communicate.DEVELOPER_TG)
    # inst_btn = Button('📷 Instagram 📷').inline("", url=Communicate.INSTAGRAM)
    # future_updates_btn = Button("Баги и будущие обновы").inline(f"{callback_data} future_updates")
    donate_btn = Button("💳 Помочь с оплатой хостинга 💳").inline(f"{callback_data} donate")
    back_btn = get_back_button(last_callback_data)

    # keyboard.add(vk_btn)
    keyboard.add(tg_btn)
    # keyboard.add(inst_btn)
    # keyboard.add(future_updates_btn)
    keyboard.add(donate_btn)
    keyboard.add(back_btn)

    return keyboard


def donate(last_callback_data: str) -> InlineKeyboardMarkup:
    """Меню с вариантами донатов"""
    keyboard = InlineKeyboardMarkup()

    # qiwi_balance_btn = Button(f"Баланс Qiwi: {rubBalance} ₽").inline("*", url=None)    # Donate.QIWI
    tinkoff_btn = Button('🟡 Тинькофф 🟡').inline("", url=Donate.TINKOFF)
    boosty_btn = Button('🟠 Boosty 🟠').inline("", url=Donate.BOOSTY)
    sberbank_btn = Button('🟢 Сбер 🟢').inline("", url=Donate.SBERBANK)
    yoomoney_btn = Button('🟣 ЮMoney 🟣').inline("", url=Donate.YOOMONEY)
    back_btn = get_back_button(last_callback_data)

    # keyboard.add(qiwi_balance_btn)
    keyboard.add(tinkoff_btn)
    keyboard.add(boosty_btn)
    keyboard.add(sberbank_btn)
    keyboard.add(yoomoney_btn)
    keyboard.add(back_btn)

    return keyboard


def group__card(group__user_info: list,
                callback_data: str,
                last_callback_data: str) -> InlineKeyboardMarkup:
    """Карточка группы"""
    keyboard = InlineKeyboardMarkup()

    # group__id = group__user_info[0]
    [group__name,
     department,
     dpo_state,
     main_subscribe,
     subscribe_state,
     spam_state] = group__user_info[1:7]

    department_smile = {0: '💰', 1: '🧪', 2: '🛠️'}.get(department, '')
    group__name_btn = Button(f"{department_smile} {group__name} {department_smile}").inline(f"* {group__name}")

    main_subscribe_btn = Button(f"⭐ {get_condition_smile(main_subscribe)}").inline(f"{callback_data} m_sub_gr")

    week_days_main_timetable_btn = Button("Основное расписание").inline(f"{callback_data} wdmt")
    history_ready_timetable_btn = Button("История").inline(f"{callback_data} mhrt")
    dpo_btn = Button("ДПО").inline(f"{callback_data} dpo")
    spam_text_btn = Button("🌀 Рассылка").inline("settings_info spamming")
    spam_btn = Button(get_condition_smile(spam_state)).inline(f"{callback_data} sp_gr")
    subscribe_text_btn = Button("☄ Подписка").inline("settings_info subscribe")
    subscribe_btn = Button(get_condition_smile(subscribe_state)).inline(f"{callback_data} sub_gr")
    back_btn = get_back_button(last_callback_data)
    ready_timetable_btn = Button("Текущее расписание").inline(f"{callback_data} g_rt")

    keyboard.add(group__name_btn, main_subscribe_btn)
    keyboard.add(week_days_main_timetable_btn)
    keyboard.add(history_ready_timetable_btn)
    if dpo_state:
        keyboard.add(dpo_btn)
    keyboard.add(spam_text_btn, spam_btn)
    keyboard.add(subscribe_text_btn, subscribe_btn)
    keyboard.add(back_btn, ready_timetable_btn)

    return keyboard


def teacher_card(teacher_user_info: list,
                 callback_data: str,
                 last_callback_data: str) -> InlineKeyboardMarkup:
    """Карточка преподавателя"""
    keyboard = InlineKeyboardMarkup()

    [teacher_id,
     teacher_name,
     gender,
     dpo_state,
     main_subscribe,
     subscribe_state,
     spam_state] = teacher_user_info[0:7]

    gender_smile = '' if gender is None else '👨🏻‍🏫 ' if gender else '👩🏻‍🏫 '
    teacher_name_btn = Button(f"{gender_smile}{teacher_name}").inline(f"* {teacher_name}")

    main_subscribe_btn = Button(f"⭐ {get_condition_smile(main_subscribe)}").inline(f"{callback_data} m_sub_tch")

    week_days_main_timetable_btn = Button("Основное расписание").inline(f"{callback_data} wdmt")
    history_ready_timetable_btn = Button("История").inline(f"{callback_data} mhrt")
    lessons_list_btn = Button("📋 Список дисциплин").inline(f"{callback_data} lessons_list {teacher_id}")
    dpo_btn = Button("ДПО").inline(f"{callback_data} dpo")
    spam_text_btn = Button("🌀 Рассылка").inline("settings_info spamming")
    spam_btn = Button(get_condition_smile(spam_state)).inline(f"{callback_data} sp_tch")
    subscribe_text_btn = Button("☄ Подписка").inline("settings_info subscribe")
    subscribe_btn = Button(get_condition_smile(subscribe_state)).inline(f"{callback_data} sub_tch")
    back_btn = get_back_button(last_callback_data)
    ready_timetable_btn = Button("Текущее расписание").inline(f"{callback_data} t_rt")

    keyboard.add(teacher_name_btn, main_subscribe_btn)
    keyboard.add(week_days_main_timetable_btn)
    keyboard.add(history_ready_timetable_btn)
    keyboard.add(lessons_list_btn)
    if dpo_state:
        keyboard.add(dpo_btn)
    keyboard.add(spam_text_btn, spam_btn)
    keyboard.add(subscribe_text_btn, subscribe_btn)
    keyboard.add(back_btn, ready_timetable_btn)

    return keyboard


def week_days_main_timetable(week_days_id_main_timetable_array,
                             callback_data: str,
                             current_week_day_id: int = None,
                             last_callback_data: str = None,
                             row_width: int = 2) -> InlineKeyboardMarkup:
    """Список дней недели для выбора основного расписания"""
    keyboard = InlineKeyboardMarkup(row_width=row_width)
    buttons = []

    get_main_timetable_btn = Button("📥 Скачать txt 📥").inline(f"{callback_data} download_main_timetable")
    keyboard.add(get_main_timetable_btn)

    for week_day_id in week_days_id_main_timetable_array:
        week_day_text_btn = get_week_day_name_by_id(week_day_id, bold=False)
        if week_day_id == current_week_day_id:
            week_day_text_btn = f"🟢 {week_day_text_btn} 🟢"
        week_day_btn = Button(week_day_text_btn).inline(f"{callback_data} {week_day_id}")
        buttons.append(week_day_btn)

    keyboard.add(*buttons)
    keyboard.add(get_back_button(last_callback_data))

    return keyboard


def months_ready_timetable(months_array: list,
                           callback_data: str,
                           last_callback_data: str) -> InlineKeyboardMarkup:
    """Список месяцев для просмотра истории расписания"""
    keyboard = InlineKeyboardMarkup()

    for month in months_array:
        text_btn = month_translate(month)
        month_btn = Button(text_btn).inline(f"{callback_data} {month}")
        keyboard.add(month_btn)

    keyboard.add(get_back_button(last_callback_data))

    return keyboard


def dates_ready_timetable(dates_array: list,
                          callback_data: str,
                          last_callback_data: str) -> InlineKeyboardMarkup:
    """Список дат для просмотра истории расписания"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    buttons = []

    get_ready_timetable_by_month_btn = Button("📥 Скачать txt 📥").inline(f"{callback_data} download_rt_by_month")
    view_stat_ready_timetable_bnt = Button("📊 Статистика 📊").inline(f"{callback_data} view_stat_rt_by_month")
    keyboard.add(get_ready_timetable_by_month_btn, view_stat_ready_timetable_bnt)

    for date_ in dates_array:
        week_day_number = date_.strftime('%d').lstrip('0')
        week_day_name = week_day_translate(date_.strftime('%a'))

        date__text_btn = f"{week_day_number} ({week_day_name})"
        date__callback = f"{callback_data} {date_.strftime('%d.%m.%Y')}"

        date__btn = Button(date__text_btn).inline(date__callback)
        buttons.append(date__btn)

        if week_day_name == 'Понедельник':
            keyboard.add(*buttons)
            buttons.clear()

    keyboard.add(*buttons)
    keyboard.add(get_back_button(last_callback_data))

    return keyboard


def timetable_paging(type_name: str,
                     name_id: int,
                     dates_array: list,
                     date_: str,
                     last_callback_data: str,
                     add_back_button: bool = False) -> InlineKeyboardMarkup:
    """Кнопки листания расписания"""
    keyboard = InlineKeyboardMarkup(row_width=2)

    ind_date_ = dates_array.index(date_)
    last_date_ = get_date_by_ind(dates_array, ind_date_ - 1)
    next_date = get_date_by_ind(dates_array, ind_date_ + 1)

    left_btn = get_paging_button(f"{last_callback_data} t_p {type_name} {name_id} {last_date_}", direction="left")
    right_btn = get_paging_button(f"{last_callback_data} t_p {type_name} {name_id} {next_date}", direction="right")
    keyboard.add(left_btn, right_btn)

    if add_back_button:
        keyboard.add(get_back_button(last_callback_data))

    return keyboard
