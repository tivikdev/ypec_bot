import asyncio
from aiogram import Dispatcher
from aiogram.types import Message, CallbackQuery

from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
import aiogram.utils.markdown as fmt

from datetime import datetime
from io import StringIO
from loguru import logger
from typing import Union

from bot.database import Select
from bot.database import Insert
from bot.database import Update

from bot.tg_module import answers
from bot.tg_module.config import ADMINS_TG
from bot.tg_module.handlers.functions import check_call
from bot.tg_module.handlers.functions import get_callback_values
from bot.tg_module.keyboards import Inline
from bot.tg_module.keyboards import Reply
from bot.tg_module.throttling import rate_limit

from bot.message_timetable import MessageTimetable

from bot.functions import column_name_by_callback
from bot.functions import get_week_day_name_by_id
from bot.functions import get_week_day_id_by_date_
from bot.functions import month_translate

AnswerText = answers.Text
AnswerCallback = answers.Callback


class UserStates(StatesGroup):
    """Класс состояний пользователя"""
    choice_type_name = State()
    choice_name = State()


async def new_user(message: Message, state: FSMContext) -> None:
    """Обработчик для нового пользователя"""
    user_id = message.chat.id
    joined = message.date

    if user_id > 0:
        user_name = message.chat.first_name
        user_name_quote = fmt.quote_html(user_name)
        text = AnswerText.welcome_message_private(user_name_quote)
    else:
        user_name = message.chat.title
        user_name_quote = fmt.quote_html(user_name)
        text = AnswerText.welcome_message_group(user_name_quote)

    new_user_data = (user_id, user_name, joined)
    Insert.new_user("telegram", new_user_data)

    logger.info(f"message {user_id} {user_name}")

    await state.update_data(send_help_message=True)
    await choice_type_name(message, text=text)


async def choice_group__name(callback: CallbackQuery, course: int = 1) -> None:
    """Выбор группы из списка для нового пользователя"""
    user_id = callback.message.chat.id

    Update.user_settings(user_id, "type_name", "True")
    group__names_array = Select.group_()

    text = AnswerText.choice_name("group_")
    keyboard = Inline.groups__list(group__names_array, course=course)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    await UserStates.choice_name.set()
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def paging_group__list_state(callback: CallbackQuery) -> None:
    """Обработчик листания списка групп для новых пользователей"""
    await paging_group__list(callback, add_back_button=False)


async def paging_group__list(callback: CallbackQuery,
                             last_ind: int = -2,
                             add_back_button: bool = True) -> None:
    """Обработчик листания списка групп"""
    user_id = callback.message.chat.id
    last_callback_data = get_callback_values(callback, last_ind)[-1]
    course = int(callback.data.split()[-1])

    group__names_array = Select.group_()

    text = AnswerText.choice_name("group_")
    keyboard = Inline.groups__list(group__names_array,
                                   course=course,
                                   add_back_button=add_back_button,
                                   last_callback_data=last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {course}")


async def choice_teacher_name(callback: CallbackQuery) -> None:
    """Выбор преподавателя из списка для нового пользователя"""
    user_id = callback.message.chat.id

    Update.user_settings(user_id, "type_name", "False")
    teacher_names_array = Select.teacher()

    text = AnswerText.choice_name("teacher")
    keyboard = Inline.teachers_list(teacher_names_array)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    await UserStates.choice_name.set()
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def paging_teacher_list_state(callback: CallbackQuery) -> None:
    """Обработчик листания списка преподавателей для новых пользователей"""
    await paging_teacher_list(callback, add_back_button=False)


async def paging_teacher_list(callback: CallbackQuery,
                              last_ind: int = -2,
                              add_back_button: bool = True) -> None:
    """Обработчик листания списка преподавателей"""
    user_id = callback.message.chat.id
    last_callback_data = get_callback_values(callback, last_ind)[-1]
    start_ = int(callback.data.split()[-1])

    teacher_names_array = Select.teacher()

    text = AnswerText.choice_name("teacher")
    keyboard = Inline.teachers_list(teacher_names_array,
                                    start_=start_,
                                    add_back_button=add_back_button,
                                    last_callback_data=last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {start_}")


@rate_limit(1)
async def error_choice_type_name_message(message: Message) -> None:
    """Обработчик левых сообщений при выборе профиля"""
    user_id = message.chat.id
    bot_message = await message.answer(AnswerText.errors("choice_type_name"))
    logger.info(f"message {bot_message.message_id} {user_id}")


async def choice_group_(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработчик выбора группы для нового пользователя"""
    user_id = callback.message.chat.id
    type_name = "group_"
    group__id = str(callback.data.split()[-1])
    group__name = Select.name_by_id(type_name, group__id)

    Update.user_settings(user_id, "name_id", group__id)
    Update.user_settings_array(user_id, name_=type_name, value=group__id, remove_=None)
    Update.user_settings_array(user_id, name_="spam_group_", value=group__id, remove_=None)

    date_ = Select.fresh_ready_timetable_date(type_name=type_name,
                                              name_id=int(group__id),
                                              type_date='string')
    if date_ is None:
        """Если в БД нет данных о расписании"""
        text = AnswerText.not_exist_timetable(group__name)
    else:
        data_ready_timetable = Select.ready_timetable(type_name, date_, group__name)
        text = MessageTimetable(group__name,
                                date_,
                                data_ready_timetable,
                                view_time=True).get()

    keyboard = Reply.default()

    callback_text = AnswerCallback.new_user("choice_group__name_finish", group__name)
    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=callback_text,
                                             show_alert=False)

    await callback.message.delete()
    bot_message = await callback.message.answer(text, reply_markup=keyboard)
    user_state_data = await state.get_data()
    await state.finish()

    logger.info(f"callback {bot_message.message_id} {user_id} {group__name} {group__id}")

    if "send_help_message" in user_state_data:
        """Если нужно новый пользователь - выводим help-сообщение"""
        await asyncio.sleep(2)
        await help_message(callback.message)



async def choice_teacher(callback: CallbackQuery, state: FSMContext) -> None:
    """Выбор преподавателя для нового пользователя"""
    user_id = callback.message.chat.id
    type_name = "teacher"
    teacher_id = callback.data.split()[-1]
    teacher_name = Select.name_by_id(type_name, teacher_id)

    Update.user_settings(user_id, "name_id", teacher_id)
    Update.user_settings_array(user_id, name_=type_name, value=teacher_id, remove_=None)
    Update.user_settings_array(user_id, name_="spam_teacher", value=teacher_id, remove_=None)

    date_ = Select.fresh_ready_timetable_date(type_name=type_name,
                                              name_id=int(teacher_id),
                                              type_date='string')
    if date_ is None:
        """Если в БД нет данных о расписании"""
        text = AnswerText.not_exist_timetable(teacher_name)
    else:
        data_ready_timetable = Select.ready_timetable(type_name, date_, teacher_name)
        text = MessageTimetable(teacher_name,
                                date_,
                                data_ready_timetable,
                                view_time=True).get()

    keyboard = Reply.default()

    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=AnswerCallback.new_user("choice_teacher_name_finish", teacher_name),
                                             show_alert=False)

    await callback.message.delete()
    bot_message = await callback.message.answer(text, reply_markup=keyboard)
    user_state_data = await state.get_data()
    await state.finish()

    logger.info(f"callback {bot_message.message_id} {user_id} {teacher_name} {teacher_id}")

    if "send_help_message" in user_state_data:
        """Если нужно новый пользователь - выводим help-сообщение"""
        await asyncio.sleep(2)
        await help_message(callback.message)


@rate_limit(1)
async def error_choice_name_message(message: Message) -> None:
    """Обработчик левых сообщений при выборе группы/преподавателя"""
    user_id = message.chat.id
    bot_message = await message.answer(AnswerText.errors("choice_name"))
    logger.info(f"message {bot_message.message_id} {user_id}")


async def choice_type_name(message: Message, text: str = None) -> None:
    """Выбор типа профиля"""
    user_id = message.chat.id

    if text is None:
        text = AnswerText.choice_type_name()
    keyboard = Inline.type_names()

    bot_message = await message.answer(text, reply_markup=keyboard)
    await UserStates.choice_type_name.set()
    logger.info(f"message {bot_message.message_id} {user_id}")


@rate_limit(1)
async def timetable(message: Message,
                    callback: CallbackQuery = None,
                    last_callback_data: str = "",
                    paging: bool = False,
                    type_name: str = None,
                    name_id: int = None,
                    date_: str = None,
                    add_back_button: bool = False) -> Union[bool, None]:
    """Обработчик запроса на получение Расписания"""
    user_id = message.chat.id

    user_info = Select.user_info_by_column_names(user_id)

    if not paging:
        """Выводим обычное расписание расписание"""
        [type_name, name_id] = user_info[:2]

    [view_name,
     view_type_lesson_mark,
     view_week_day,
     view_add,
     view_time,
     view_dpo_info] = user_info[2:]

    if type_name is None or name_id is None:
        """У пользователя нет основной подписки"""
        text = AnswerText.no_main_subscription()
        bot_message = await message.answer(text)

        logger.info(f"message {bot_message.message_id} {user_id} {type_name} {name_id}")

    else:
        name_ = Select.name_by_id(type_name, name_id)

        dates_array = Select.dates_ready_timetable(type_name=type_name,
                                                   name_id=name_id,
                                                   type_date='string',
                                                   type_sort='ASC')

        if date_ == 'empty':
            """Если при листании упёрлись в конец списка, то выводим сообщение об отсутсвии расписания"""
            return await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                            text=AnswerCallback.not_timetable_paging(),
                                                            show_alert=False)
        elif date_ is None:
            """Если не указана дата, то берём самую актуальную"""
            date_ = Select.fresh_ready_timetable_date(type_name=type_name,
                                                      name_id=name_id,
                                                      type_date='string')

        if date_ is None:
            """Если в БД нет данных о расписании"""
            text = AnswerText.not_exist_timetable(name_)
            keyboard = Reply.default()
            bot_message = await message.answer(text, reply_markup=keyboard)

            logger.info(f"message {bot_message.message_id} {user_id} {name_} {name_id} {date_} {paging} {'date_ is None'}")

        else:
            week_day_id = get_week_day_id_by_date_(date_)

            data_ready_timetable = Select.ready_timetable(type_name, date_, name_)
            data_dpo = Select.dpo(type_name, name_, week_day_id)

            text = MessageTimetable(name_,
                                    date_,
                                    data_ready_timetable,
                                    data_dpo=data_dpo,
                                    view_name=view_name,
                                    view_type_lesson_mark=view_type_lesson_mark,
                                    view_week_day=view_week_day,
                                    view_add=view_add,
                                    view_time=view_time,
                                    view_dpo_info=view_dpo_info).get()
            keyboard = Inline.timetable_paging(type_name,
                                               name_id,
                                               dates_array,
                                               date_,
                                               last_callback_data,
                                               add_back_button=add_back_button)

            if paging:
                bot_message = await message.edit_text(text, reply_markup=keyboard)
            else:
                bot_message = await message.answer(text, reply_markup=keyboard)

            logger.info(f"message {bot_message.message_id} {user_id} {name_} {name_id} {date_} {paging}")


async def timetable_paging(callback: CallbackQuery, last_ind: int = -4) -> None:
    """Листание расписания"""
    add_back_button = False
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    if last_callback_data != "":
        """Если есть данные о прошлых шагах - добавляем кнопку  Назад"""
        add_back_button = True

    [type_name, name_id, date_] = callback_data_split[-3:]
    await timetable(callback.message,
                    callback=callback,
                    last_callback_data=last_callback_data,
                    paging=True,
                    type_name=type_name,
                    name_id=name_id,
                    date_=date_,
                    add_back_button=add_back_button)


@rate_limit(1)
async def command_timetable(message: Message) -> None:
    """Обработчик команды /timetable"""
    await timetable(message)


@rate_limit(1)
async def personal_area(message: Message,
                        callback: CallbackQuery = None,
                        edit_text: bool = False) -> None:
    """Обработчик запроса на получение Настроек пользователя"""
    user_id = message.chat.id
    user_settings_data = list(Select.user_info(user_id))
    table_name = user_settings_data[0]
    name_id = user_settings_data[2]

    if name_id is not None:
        name_ = Select.name_by_id(table_name, name_id)
        user_settings_data[1] = name_

    text = AnswerText.personal_area()
    keyboard = Inline.user_settings(user_settings_data)

    if edit_text:
        if callback is not None:
            bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
            await callback.bot.answer_callback_query(callback.id)
            logger.info(f"message {bot_message.message_id} {user_id}")
    else:
        bot_message = await message.answer(text, reply_markup=keyboard)
        logger.info(f"message {bot_message.message_id} {user_id}")


@rate_limit(1)
async def command_personal_area(message: Message) -> None:
    """Обработчик команды /personal_area"""
    await personal_area(message)


async def settings_callback(callback: CallbackQuery) -> None:
    """Обработчик CallbackQuery на возвращение к меню Настроек"""
    await personal_area(callback.message, callback, edit_text=True)


async def call_schedule(callback: CallbackQuery) -> None:
    """Обработчик CallbackQuery для просмотра расписания звонков"""
    user_id = callback.message.chat.id

    text = AnswerText.call_schedule()
    keyboard = Inline.get_back_button("s", return_keyboard=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def main_settings(callback: CallbackQuery) -> None:
    """Обработчик CallbackQuery на переход к окну основных настроек"""
    user_id = callback.message.chat.id
    user_settings_data = list(Select.user_info(user_id))

    text = AnswerText.main_settings()
    keyboard = Inline.main_settings(user_settings_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def settings_info(callback: CallbackQuery) -> None:
    """Обработчик CallbackQuery для получения информации при нажатии кнопки"""
    user_id = callback.message.chat.id
    settings_name = callback.data.split()[-1]
    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=AnswerCallback.settings_info(settings_name),
                                             show_alert=True)
    logger.info(f"callback {user_id} {settings_name}")


async def update_main_settings_bool(callback: CallbackQuery) -> None:
    """Обновление настроек True/False"""
    user_id = callback.message.chat.id
    settings_name = callback.data.split()[-1]

    result = Update.user_settings_bool(user_id, name_=settings_name)

    await main_settings(callback)
    logger.info(f"callback {user_id} {settings_name} {result}")


async def support(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Обработка нажатия кнопки support"""
    user_id = callback.message.chat.id
    last_callback_data = get_callback_values(callback, last_ind)[-1]

    # Select.config("rub_balance")

    text = AnswerText.support()
    keyboard = Inline.support(callback.data, last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def donate(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Вывести меню с вариантами донейшинов"""
    user_id = callback.message.chat.id
    last_callback_data = get_callback_values(callback, last_ind)[-1]

    text = AnswerText.donate()
    keyboard = Inline.donate(last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def future_updates(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Вывести сообщение о будущих апдейтах"""
    user_id = callback.message.chat.id
    last_callback_data = get_callback_values(callback, last_ind)[-1]

    text = Select.config("future_updates")

    '''    
    if text in (None, ''):
        """Ошибка"""
        return await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                        text=AnswerCallback.error["default"])
    '''

    keyboard = Inline.get_back_button(last_callback_data, return_keyboard=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def spam_or_subscribe_name_id(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Обновление настроек spamming и subscribe для карточек группы/преподавателя"""
    user_id = callback.message.chat.id
    [callback_data_split, callback.data] = get_callback_values(callback, last_ind)

    type_column_name = callback_data_split[-1]
    action_type = type_column_name.split('_')[0]
    short_type_name = type_column_name.split('_')[-1]
    name_id = callback_data_split[-2]

    result = Update.user_settings_array(user_id,
                                        name_=column_name_by_callback.get(type_column_name),
                                        value=name_id)

    # удалили подписку
    if type_column_name in ('sub_gr', 'sub_tch') and not result:

        # если это карточка с активной основной подпиской, то удаляем её
        if Update.user_settings_value(user_id, "name_id", name_id, remove_=True):
            Update.user_settings(user_id, "type_name", "NULL", convert_val_text=False)

        Update.user_settings_array(user_id,
                                   name_=column_name_by_callback.get(f"sp_{short_type_name}"),
                                   value=name_id,
                                   remove_=True)

    elif type_column_name in ("sp_gr", "sp_tch") and result:

        Update.user_settings_array(user_id,
                                   name_=column_name_by_callback.get(f"sub_{short_type_name}"),
                                   value=name_id,
                                   remove_=None)

    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=AnswerCallback.spam_or_subscribe_name_id(action_type, result),
                                             show_alert=False)

    logger.info(f"callback {user_id} {short_type_name} {action_type} {name_id} {result}")

    if short_type_name == "gr":
        await group__card(callback)

    elif short_type_name == "tch":
        await teacher_card(callback)


async def main_subscribe_name_id(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Обновление настроек main_subscribe для карточек группы/преподавателя"""
    user_id = callback.message.chat.id
    [callback_data_split, callback.data] = get_callback_values(callback, last_ind)
    type_column_name = callback_data_split[-1]
    name_id = callback_data_split[-2]

    result = Update.user_settings_value(user_id, "name_id", name_id)

    # если основная подписка добавлена
    if result:
        Update.user_settings(user_id, "type_name", type_column_name == "m_sub_gr", convert_val_text=True)
        Update.user_settings_array(user_id,
                                   name_=column_name_by_callback.get(type_column_name),
                                   value=name_id,
                                   remove_=None)
    else:
        Update.user_settings(user_id, "type_name", "NULL", convert_val_text=False)
        Update.user_settings(user_id, "name_id", "NULL", convert_val_text=False)

    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=AnswerCallback.main_subscribe_name_id(result),
                                             show_alert=False)

    logger.info(f"callback {user_id} {type_column_name} {name_id} {result}")

    if type_column_name == 'm_sub_gr':
        await group__card(callback)

    elif type_column_name == 'm_sub_tch':
        await teacher_card(callback)


async def group__card(callback: CallbackQuery, last_ind: int = -2) -> None:
    """Показать карточку группы"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    group__id = callback_data_split[-1]

    group__user_info = Select.user_info_name_card("group_", user_id, group__id)
    group__name = group__user_info[1]

    text = AnswerText.group__card()
    keyboard = Inline.group__card(group__user_info,
                                  callback_data=callback.data,
                                  last_callback_data=last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {group__name} {group__id}")


async def teacher_card(callback: CallbackQuery, last_ind: int = -2) -> None:
    """Показать карточку преподавателя"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    teacher_id = callback_data_split[-1]

    teacher_user_info = Select.user_info_name_card("teacher", user_id, teacher_id)
    teacher_name = teacher_user_info[1]

    text = AnswerText.teacher_card()
    keyboard = Inline.teacher_card(teacher_user_info,
                                   callback_data=callback.data,
                                   last_callback_data=last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {teacher_name} {teacher_id}")


async def lessons_list_by_teacher(callback: CallbackQuery, last_ind=-2) -> None:
    """Вывести список дисциплин, которые ведёт преподаватель"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    teacher_id = callback_data_split[-1]
    teacher_name = Select.name_by_id("teacher", teacher_id)

    lessons_list = Select.lessons_list_by_teacher(teacher_name)

    if not lessons_list:
        return await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                        text=AnswerCallback.not_lessons_list())

    text = AnswerText.lessons_list_by_teacher(teacher_name, lessons_list)
    keyboard = Inline.get_back_button(last_callback_data, return_keyboard=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {teacher_name} {teacher_id}")


async def week_days_main_timetable(callback: CallbackQuery, last_ind=-1) -> None:
    """Показать список дней недели для получения основного расписания"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    type_name = column_name_by_callback.get(callback_data_split[-3])
    name_id = int(callback_data_split[-2])

    week_days_id_main_timetable_array = Select.week_days_timetable(type_name, name_id, "main_timetable")

    if not week_days_id_main_timetable_array:
        await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                 text=AnswerCallback.not_week_days_main_timetable(),
                                                 show_alert=False)

    else:
        text = AnswerText.week_days_main_timetable()
        keyboard = Inline.week_days_main_timetable(week_days_id_main_timetable_array,
                                                   current_week_day_id=datetime.now().weekday(),
                                                   callback_data=callback.data,
                                                   last_callback_data=last_callback_data)

        bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.bot.answer_callback_query(callback.id)
        logger.info(f"callback {bot_message.message_id} {user_id}")


async def download_main_timetable(callback: CallbackQuery) -> None:
    """Скачать Основное расписание на неделю"""
    user_id = callback.message.chat.id
    callback_data_split = callback.data.split()

    type_name = column_name_by_callback.get(callback_data_split[-4])
    name_id = callback_data_split[-3]
    name_ = Select.name_by_id(type_name, name_id)

    text = f"{name_}\n\n"

    for week_day_id in range(6):
        week_day_name = get_week_day_name_by_id(week_day_id, bold=False)
        data_main_timetable = Select.view_main_timetable(type_name,
                                                         name_,
                                                         week_day_id=week_day_id,
                                                         lesson_type=None)
        data_dpo = Select.dpo(type_name, name_, week_day_id)
        main_timetable_message = MessageTimetable(name_,
                                                  week_day_name,
                                                  data_main_timetable,
                                                  data_dpo=data_dpo,
                                                  start_text="",
                                                  view_name=False,
                                                  type_format="txt",
                                                  format_timetable="only_date").get()
        text += f"{main_timetable_message}\n\n"

    file = StringIO(text)
    file.name = f"{name_} На неделю {callback.id[-4:]}.txt"

    await callback.bot.send_chat_action(user_id, 'upload_document')
    await asyncio.sleep(2)
    bot_message = await callback.bot.send_document(user_id, file)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {type_name} {name_} {name_id}")


async def get_main_timetable_by_week_day_id(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Получить основное расписание для дня недели"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)

    week_day_id = callback_data_split[-1]

    type_name = column_name_by_callback.get(callback_data_split[-4])
    name_id = callback_data_split[-3]
    name_ = Select.name_by_id(type_name, name_id)

    data_main_timetable = Select.view_main_timetable(type_name, name_,
                                                     week_day_id=week_day_id,
                                                     lesson_type=None)
    data_dpo = Select.dpo(type_name, name_, week_day_id)

    if not data_main_timetable:
        week_day = get_week_day_name_by_id(week_day_id, type_case="prepositional", bold=False)
        text = AnswerCallback.not_main_timetable_by_week_day(week_day)
        await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                 text=text)

    else:
        date_week_day = get_week_day_name_by_id(week_day_id, type_case='prepositional')
        text = MessageTimetable(name_,
                                date_week_day,
                                data_main_timetable,
                                data_dpo=data_dpo,
                                start_text="Основное расписание на ",
                                format_=True).get()
        keyboard = Inline.get_back_button(last_callback_data, return_keyboard=True)

        await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.bot.answer_callback_query(callback.id)

    logger.info(f"callback {user_id} {type_name} {name_} {week_day_id} {bool(data_main_timetable)}")


async def months_history_ready_timetable(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Вывести список с месяцами"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    type_name = column_name_by_callback.get(callback_data_split[-3])
    name_id = int(callback_data_split[-2])

    months_array = Select.months_ready_timetable(type_name=type_name, name_id=name_id)

    if not months_array:
        return await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                        text=AnswerCallback.not_months_history_ready_timetable())

    text = AnswerText.months_history_ready_timetable()
    keyboard = Inline.months_ready_timetable(months_array, callback.data, last_callback_data)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id}")


async def dates_ready_timetable(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Вывести список дат"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)
    type_name = column_name_by_callback.get(callback_data_split[-4])
    name_id = callback_data_split[-3]
    month = callback_data_split[-1]

    name_ = Select.name_by_id(type_name, name_id)

    dates_array = Select.dates_ready_timetable(month=month,
                                               type_name=type_name,
                                               name_id=name_id)
    if not dates_array:
        """Если нет расписания ни на одну дату"""
        text = AnswerCallback.not_ready_timetable_by_month(month_translate(month))
        await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                 text=text,
                                                 show_alert=False)

    else:
        text = AnswerText.dates_ready_timetable(name_, month_translate(month))
        keyboard = Inline.dates_ready_timetable(dates_array, callback.data, last_callback_data)

        bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
        await callback.bot.answer_callback_query(callback.id)
        logger.info(f"callback {bot_message.message_id} {user_id} {type_name} {name_} {name_id}")


async def download_ready_timetable_by_month(callback: CallbackQuery) -> None:
    """Скачать всё расписание на определённый месяц"""
    user_id = callback.message.chat.id
    callback_data_split = callback.data.split()

    type_name = column_name_by_callback.get(callback_data_split[-5])
    name_id = int(callback_data_split[-4])
    month = callback_data_split[-2]
    month_translate_text = month_translate(month)

    name_ = Select.name_by_id(type_name, name_id)

    text = f"{name_} {month_translate_text}\n\n"

    user_info = Select.user_info_by_column_names(user_id, column_names=['view_add',
                                                                        'view_type_lesson_mark',
                                                                        'view_week_day',
                                                                        'view_time',
                                                                        'view_dpo_info'])
    [view_add,
     view_type_lesson_mark,
     view_week_day,
     view_time,
     view_dpo_info] = user_info

    dates_array = Select.dates_ready_timetable(month=month,
                                               type_name=type_name,
                                               name_id=name_id,
                                               type_sort='ASC')

    for date_ in dates_array:
        week_day_id = get_week_day_id_by_date_(date_)

        data_ready_timetable = Select.ready_timetable(type_name, date_, name_)
        data_dpo = Select.dpo(type_name, name_, week_day_id)
        date_text = date_.strftime('%d.%m.%Y')

        if data_ready_timetable:
            ready_timetable_message = MessageTimetable(name_,
                                                       date_text,
                                                       data_ready_timetable,
                                                       data_dpo=data_dpo,
                                                       view_name=False,
                                                       view_type_lesson_mark=view_type_lesson_mark,
                                                       view_week_day=view_week_day,
                                                       view_add=view_add,
                                                       view_time=view_time,
                                                       view_dpo_info=view_dpo_info).get()
            text += f"{ready_timetable_message}\n\n"

    file = StringIO(text)
    file.name = f"{name_} {month_translate(month)} {callback.id[-4:]}.txt"

    await callback.bot.send_chat_action(user_id, 'upload_document')
    await asyncio.sleep(2)
    bot_message = await callback.bot.send_document(user_id, file)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {month} {type_name} {name_} {name_id}")


async def view_stat_ready_timetable_by_month(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Посмотреть статистику по распсианию за месяц"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)

    type_name = column_name_by_callback.get(callback_data_split[-5])
    name_id = int(callback_data_split[-4])
    month = callback_data_split[-2]
    month_translate_text = month_translate(month)

    name_ = Select.name_by_id(type_name, name_id)

    '''
        0. 🟠 - обычные пары (оранжевый)
        1. 🟢 - дистант (зелёный)
        2. 🔵 - лабы (синий)
        3. ⚪️ - экскурсия (белый)
        4. 🟡 - практика или п/з (желтый)
        5. 🟣 - консультация (фиолетовый)
        6. 🔴 - экзамен или к/р (красный)
    '''
    number_dates = len(Select.dates_ready_timetable(type_name=type_name,
                                                    name_id=name_id,
                                                    month=month))

    data_stat_ready_timetable = Select.stat_ready_timetable(type_name, name_id, month)

    [num_all_les,
     num_remote,
     num_lab,
     num_excursion,
     num_practice,
     num_consultation] = data_stat_ready_timetable

    data = [
        ['🟢', 'Дист', num_remote],
        ['🔵', 'л/р', num_lab],
        ['⚪️', 'Экскурсии', num_excursion],
        ['🟡', 'п/з', num_practice],
        ['🟣', 'Консультации', num_consultation],
        [' ', 'Всего пар', num_all_les],
        [' ', 'В среднем', round(num_all_les/number_dates, 2)]
    ]

    text = f"<b>{name_} {month_translate_text}</b>\n\n"

    for row in data:
        text += ' '.join(map(str, row)) + '\n'

    keyboard = Inline.get_back_button(last_callback_data, return_keyboard=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)

    logger.info(f"callback {bot_message.message_id} {user_id} {month} {type_name} {name_} {name_id}")


async def ready_timetable_by_date(callback: CallbackQuery) -> None:
    """Вывести расписание для определённой даты"""
    user_id = callback.message.chat.id
    callback_data_split = callback.data.split()
    type_name = column_name_by_callback.get(callback_data_split[-5])
    name_id = int(callback_data_split[-4])
    date_ = callback_data_split[-1]

    await view_ready_timetable(callback,
                               last_ind=-1,
                               type_name=type_name,
                               name_id=name_id,
                               date_=date_)
    logger.info(f"callback {user_id} {date_} {type_name} {name_id} name_id")


async def view_dpo_information(callback: CallbackQuery, last_ind: int = -1) -> None:
    """Получить информацию о ДПО"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)

    type_name = column_name_by_callback.get(callback_data_split[-3])
    name_id = callback_data_split[-2]
    name_ = Select.name_by_id(type_name, name_id)

    week_days_id_dpo_array = Select.week_days_timetable(type_name, name_id, "dpo")

    text = f"<b>{name_} (ДПО)</b>\n"
    for week_day_id in week_days_id_dpo_array:
        """Перебираем дни недели с ДПО"""
        data_dpo = Select.dpo(type_name, name_, week_day_id)
        week_day_name = get_week_day_name_by_id(week_day_id, type_case='default', bold=True)
        text += MessageTimetable(name_,
                                 week_day_name,
                                 data_dpo,
                                 start_text="",
                                 view_name=False,
                                 format_=True).get()
        text += '\n'

    keyboard = Inline.get_back_button(last_callback_data, return_keyboard=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {type_name} {name_} {name_id}")


async def view_ready_timetable(callback: CallbackQuery,
                               last_ind: int = -1,
                               type_name: str = None,
                               name_id: int = None,
                               date_: str = None) -> Union[bool, None]:
    """Показать текущее расписание"""
    user_id = callback.message.chat.id
    [callback_data_split, last_callback_data] = get_callback_values(callback, last_ind)

    if type_name is None:
        type_name = column_name_by_callback.get(callback_data_split[-1])

    if name_id is None:
        name_id = callback_data_split[-2]

    if date_ is None:
        date_ = Select.fresh_ready_timetable_date(type_name=type_name,
                                                  name_id=name_id,
                                                  type_date='string')

        if date_ is None:
            """Расписание полностью отсутствует"""
            text = AnswerCallback.not_ready_timetable()
            return await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                                            text=text,
                                                            show_alert=False)

    user_info = Select.user_info_by_column_names(user_id, column_names=['view_type_lesson_mark',
                                                                        'view_week_day',
                                                                        'view_add',
                                                                        'view_time',
                                                                        'view_dpo_info'])
    [view_type_lesson_mark,
     view_week_day,
     view_add,
     view_time,
     view_dpo_info] = user_info

    name_ = Select.name_by_id(type_name, name_id)
    week_day_id = get_week_day_id_by_date_(date_)

    data_ready_timetable = Select.ready_timetable(type_name, date_, name_)
    data_dpo = Select.dpo(type_name, name_, week_day_id)

    text = MessageTimetable(name_,
                            date_,
                            data_ready_timetable,
                            data_dpo=data_dpo,
                            view_type_lesson_mark=view_type_lesson_mark,
                            view_week_day=view_week_day,
                            view_add=view_add,
                            view_time=view_time,
                            view_dpo_info=view_dpo_info,
                            format_=True).get()
    dates_array = Select.dates_ready_timetable(type_name=type_name,
                                               name_id=name_id,
                                               type_date='string',
                                               type_sort='ASC')
    keyboard = Inline.timetable_paging(type_name,
                                       name_id,
                                       dates_array,
                                       date_,
                                       last_callback_data,
                                       add_back_button=True)

    bot_message = await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.bot.answer_callback_query(callback.id)
    logger.info(f"callback {bot_message.message_id} {user_id} {type_name} {name_} {name_id}")


async def view_callback(callback: CallbackQuery) -> None:
    """Обработчик нажатий на пустые кнопки"""
    user_id = callback.message.chat.id
    text = ' '.join(callback.data.split()[1:])

    await callback.bot.answer_callback_query(callback_query_id=callback.id,
                                             text=text,
                                             show_alert=True)
    logger.info(f"callback {user_id}")


async def close(callback: CallbackQuery) -> None:
    """Обработать запрос на удаление (закрытие) окна сообщения"""
    user_id = callback.message.chat.id
    await callback.message.delete()
    logger.info(f"callback {user_id}")


@rate_limit(1)
async def call_schedule_command(message: Message) -> None:
    """Расписание звонков"""
    user_id = message.chat.id
    text = AnswerText.call_schedule()
    bot_message = await message.answer(text)
    logger.info(f"callback {bot_message.message_id} {user_id}")


@rate_limit(1)
async def help_message(message: Message) -> None:
    """Вывести help-сообщение"""
    user_id = message.chat.id
    text = AnswerText.help_message()
    bot_message = await message.answer(text)
    logger.info(f"message {bot_message.message_id} {user_id}")


@rate_limit(1)
async def show_keyboard(message: Message) -> None:
    """Показать клавиатуру"""
    user_id = message.chat.id

    text = AnswerText.show_keyboard()
    keyboard = Reply.default()
    if user_id in ADMINS_TG:
        keyboard = Reply.default_admin()

    bot_message = await message.answer(text, reply_markup=keyboard)
    logger.info(f"message {bot_message.message_id} {user_id}")


@rate_limit(1)
async def other_messages(message: Message) -> None:
    """Обработчик сторонних сообщений"""
    user_id = message.chat.id
    if user_id > 0:
        """Функция работает только у юзеров (не в беседах)"""
        text = AnswerText.other_messages()
        bot_message = await message.answer(text)
        logger.info(f"message {bot_message.message_id} {user_id}")


'''
async def bot_blocked(update: types.Update, exception: MessageTextIsEmpty) -> None:
    pass
'''


def register_user_handlers(dp: Dispatcher) -> None:
    """register all user handlers"""

    dp.register_message_handler(new_user,
                                lambda msg: Select.user_info(user_id=msg.chat.id) is None,
                                content_types=['text'])

    dp.register_callback_query_handler(choice_group__name,
                                       lambda call: check_call(call, ['g_list']),
                                       state=UserStates.choice_type_name)

    dp.register_callback_query_handler(paging_group__list_state,
                                       lambda call: check_call(call, ['g_list'], ind=-2),
                                       state=UserStates.choice_name)

    dp.register_callback_query_handler(paging_group__list,
                                       lambda call: check_call(call, ['g_list'], ind=-2),
                                       state='*')

    dp.register_callback_query_handler(choice_teacher_name,
                                       lambda call: check_call(call, ['t_list']),
                                       state=UserStates.choice_type_name)

    dp.register_callback_query_handler(paging_teacher_list_state,
                                       lambda call: check_call(call, ['t_list'], ind=-2),
                                       state=UserStates.choice_name)

    dp.register_callback_query_handler(paging_teacher_list,
                                       lambda call: check_call(call, ['t_list'], ind=-2),
                                       state='*')

    dp.register_message_handler(error_choice_type_name_message, state=UserStates.choice_type_name)

    # dp.register_message_handler(error_choice_type_name_callback, state=UserStates.choice_type_name)

    dp.register_callback_query_handler(choice_group_,
                                       lambda call: check_call(call, ['gc'], ind=-2),
                                       state=UserStates.choice_name)

    dp.register_callback_query_handler(choice_teacher,
                                       lambda call: check_call(call, ['tc'], ind=-2),
                                       state=UserStates.choice_name)

    dp.register_message_handler(error_choice_name_message, state=UserStates.choice_name)

    # dp.register_message_handler(error_choice_name_callback, state=UserStates.choice_name)

    dp.register_message_handler(choice_type_name,
                                commands=['start'],
                                state='*')

    dp.register_message_handler(timetable, Text(equals=['Расписание'], ignore_case=True))

    dp.register_callback_query_handler(timetable_paging,
                                       lambda call: check_call(call, ['t_p'], ind=-4))

    dp.register_message_handler(command_timetable, commands=['timetable'])

    dp.register_message_handler(personal_area, Text(equals=['Личный кабинет', 'Настройки'], ignore_case=True))

    dp.register_message_handler(command_personal_area, commands=['personal_area'])

    dp.register_callback_query_handler(settings_callback,
                                       lambda call: check_call(call, ['s']))

    dp.register_callback_query_handler(call_schedule,
                                       lambda call: check_call(call, ['cs']))

    dp.register_callback_query_handler(main_settings,
                                       lambda call: check_call(call, ['ms']))

    dp.register_callback_query_handler(settings_info,
                                       lambda call: check_call(call, ['settings_info'], ind=-2))

    dp.register_callback_query_handler(update_main_settings_bool,
                                       lambda call: check_call(call, ['update_main_settings_bool'], ind=-2))

    dp.register_callback_query_handler(support,
                                       lambda call: check_call(call, ['support']))

    dp.register_callback_query_handler(donate,
                                       lambda call: check_call(call, ['donate']))

    dp.register_callback_query_handler(future_updates,
                                       lambda call: check_call(call, ['future_updates']))

    dp.register_callback_query_handler(spam_or_subscribe_name_id,
                                       lambda call: check_call(call, ['sp_gr', 'sub_gr', 'sp_tch', 'sub_tch']))

    dp.register_callback_query_handler(main_subscribe_name_id,
                                       lambda call: check_call(call, ['m_sub_gr', 'm_sub_tch']))

    dp.register_callback_query_handler(group__card,
                                       lambda call: check_call(call, ['gc'], ind=-2))

    dp.register_callback_query_handler(teacher_card,
                                       lambda call: check_call(call, ['tc'], ind=-2))

    dp.register_callback_query_handler(lessons_list_by_teacher,
                                       lambda call: check_call(call, ['lessons_list'], ind=-2))

    dp.register_callback_query_handler(week_days_main_timetable,
                                       lambda call: check_call(call, ['wdmt']))

    dp.register_callback_query_handler(download_main_timetable,
                                       lambda call: check_call(call, ['download_main_timetable']))

    dp.register_callback_query_handler(get_main_timetable_by_week_day_id,
                                       lambda call: check_call(call, ['wdmt'], ind=-2))

    dp.register_callback_query_handler(months_history_ready_timetable,
                                       lambda call: check_call(call, ['mhrt']))

    dp.register_callback_query_handler(dates_ready_timetable,
                                       lambda call: check_call(call, ['mhrt'], ind=-2))

    dp.register_callback_query_handler(download_ready_timetable_by_month,
                                       lambda call: check_call(call, ['download_rt_by_month']))

    dp.register_callback_query_handler(view_stat_ready_timetable_by_month,
                                       lambda call: check_call(call, ['view_stat_rt_by_month']))

    dp.register_callback_query_handler(ready_timetable_by_date,
                                       lambda call: check_call(call, ['mhrt'], ind=-3))

    dp.register_callback_query_handler(view_dpo_information,
                                       lambda call: check_call(call, ['dpo'], ind=-1))

    dp.register_callback_query_handler(view_ready_timetable,
                                       lambda call: check_call(call, ['g_rt', 't_rt']))

    dp.register_callback_query_handler(view_callback,
                                       lambda call: call.data.split()[0] == '*')

    dp.register_callback_query_handler(close,
                                       lambda call: call.data == 'close', state='*')

    dp.register_message_handler(call_schedule_command,
                                commands=['call_schedule'],
                                state='*')

    dp.register_message_handler(help_message,
                                commands=['help'],
                                state='*')

    dp.register_message_handler(show_keyboard,
                                commands=['show_keyboard'],
                                state='*')

    dp.register_message_handler(other_messages,
                                state='*')

    # dp.register_errors_handler(terminated_by_other_get_updates, exception=TerminatedByOtherGetUpdates)
