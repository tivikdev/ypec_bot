import configparser

from bot.database import Delete
from bot.database import Insert
from bot.database import Select
from bot.database import Table

from bot.functions import get_day_text
from bot.functions import get_week_day_id_by_date_

from bot.parse.functions import combine_teacher_names_and_audience_arrays
from bot.parse.functions import convert_timetable_to_dict
from bot.parse.functions import convert_lesson_name
from bot.parse.functions import check_practice

from bot.parse import MainTimetable
from bot.parse import Replacements


def _get_type_lesson_array(lesson_name: str, audience: str) -> list:
    """Добавляем смайлик-маркировку
        0. ⚪ - обычные пары (оранжевый)
        1. 🟢 - дистант (зелёный)
        2. 🔵 - лабы (синий)
        3. 🟣 - экскурсия (белый)
        4. 🟡 - практика или п/з(желтый)
        5. 🟠 - консультация (фиолетовый)
        6. 🔴 - экзамен или к/р (красный)
    день подготовки к экзамену*
    """
    type_lesson_mark_array = []
    default_lesson_name = lesson_name
    lesson_name = str(lesson_name).lower()
    audience = str(audience).lower()

    if 'экзам' in lesson_name or 'к/р' in lesson_name:
        """Если экзамен или к/р"""
        type_lesson_mark_array.append(6)

    if 'консу' in lesson_name:
        """Если консультация"""
        type_lesson_mark_array.append(5)

    if 'п/з' in lesson_name or check_practice(default_lesson_name):
        """Если п/з или практика"""
        type_lesson_mark_array.append(4)

    if 'экс' in audience or 'каток' in audience:
        """Если экскурсия"""
        type_lesson_mark_array.append(3)

    if 'л/р' in lesson_name:
        """Если лабы"""
        type_lesson_mark_array.append(2)

    if 'дист' in audience:
        """Если дистант"""
        type_lesson_mark_array.append(1)

    if not type_lesson_mark_array:
        type_lesson_mark_array.append(0)

    return type_lesson_mark_array


class TimetableHandler:
    """Класс-обработчик

        Атрибуты
        --------
        mt : class
            class MainTimetable
        rep : class
            class Replacement
        ready_timetable_data : list
            массив со строчками с готовым расписанием
        date_replacement : str
            завтрашняя дата
        week_lesson_type : int
            id завтрашнего дня недели
        group__names : list
            кортеж групп
        teacher_names : set
            кортеж преподавателей

        """

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read("config.ini")

        self.ready_timetable_data = []
        self.date_replacement = get_day_text(days=1)  # по дефолту берём завтрашнюю дату (исключая вс)
        self.week_lesson_type = None  # get_week_day_id_by_date_(self.date_replacement)

        self.mt = MainTimetable()
        self.rep = Replacements()

        self.group__names = Select.all_info("group_", column_name="group__name")
        if not self.group__names:
            self.actualization_group__and_teacher_names(group_check=True)

        self.teacher_names = Select.all_info("teacher", column_name="teacher_name")
        if not self.teacher_names:
            self.actualization_group__and_teacher_names(teacher_check=True)

        self.lesson_names = set()

        self.method = self.config['PARSE']['main_method']
        self.parse_table_replacement_mode = self.config['PARSE']['table_replacement_mode']

    def actualization_group__and_teacher_names(self, group_check: bool = False, teacher_check: bool = False):
        """Актуализируем список групп и преподавателей"""
        if group_check:
            self.group__names = self.mt.get_array_names_by_type_name('group_')
            Insert.group_(self.mt.group__names)

        if teacher_check:
            self.teacher_names = self.mt.get_array_names_by_type_name('teacher')
            Insert.teacher(self.mt.teacher_names)

    async def get_main_timetable(self,
                                 type_name: str = None,
                                 names: list = None) -> None:
        """Получаем основное расписание"""
        if names is None:
            names = []

        #self.mt.group__names = self.group__names
        #self.mt.teacher_names = self.teacher_names

        self.actualization_group__and_teacher_names(group_check=True, teacher_check=True)

        self.mt.data.clear()

        await self.mt.parse(type_name=type_name, names=names)

        Insert.lesson(self.mt.lesson_names)
        Insert.audience(self.mt.audience_names)

        for name_ in names:
            name_id = Select.id_by_name(type_name, name_)
            Delete.main_timetable(type_name, name_id)
        Insert.main_timetable(self.mt.data)

    async def get_replacement(self, day: str = "tomorrow") -> str:
        """Получаем замены"""
        self.rep.group__names = self.group__names

        self.rep.data.clear()

        if not Select.check_filling_table('replacement'):
            """Если появились замены, то актуализируем данные о группах и преподавателях"""
            self.actualization_group__and_teacher_names(group_check=True, teacher_check=True)

        await self.rep.parse(day=day)
        self.date_replacement = self.rep.date
        self.week_lesson_type = self.rep.week_lesson_type
        
        fresh_date_ready_timetable = Select.fresh_ready_timetable_date(type_date="string")

        # если замен нет или в БД ещё нет расписания на дату, полученную с сайта
        if not self.rep.data:
            Table.delete('replacement')
            Table.delete('replacement_temp')
            return "NO"

        elif self.date_replacement != fresh_date_ready_timetable:
            Table.delete('replacement')
            Table.delete('replacement_temp')

        Insert.lesson(self.rep.lesson_names)
        Insert.practice(self.rep.data_practice)
        Insert.teacher(self.rep.teacher_names)
        Insert.audience(self.rep.audience_names)

        # если есть замены, но таблица с ними пуста
        if not Select.check_filling_table('replacement'):
            Insert.replacement(self.rep.data)
            return "NEW"

        # если замены есть, то перезаписываем их
        Table.delete('replacement')
        Insert.replacement(self.rep.data)

        return "UPDATE"

    def get_ready_timetable(self,
                            date_: str = None,
                            type_name: str = 'group_',
                            names_array: list = None,
                            lesson_type: bool = True) -> None:
        """Получаем готовое расписание
        :param date_: дата, для которой будет составлено расписание
        :param type_name: тип профиля
        :param names_array: массив наименований групп/преподавателей
        :param lesson_type: тип недели (числитель/знаменатель)
        :return: None
        """

        if names_array is None:
            names_array = []

        if date_ is None:
            date_ = self.date_replacement

        #names_rep_diff_group_ = Select.names_rep_different('group_', date_)
        #names_rep_diff_teacher = Select.names_rep_different('teacher', date_)

        #if names_rep_diff_group_ or names_rep_diff_teacher:
            #"""Если есть изменения в заменах"""

        week_day_id = get_week_day_id_by_date_(date_)

        self.ready_timetable_data.clear()

        self.replacements_join_timetable(date_=date_,
                                         type_name=type_name,
                                         names_array=names_array,
                                         week_day_id=week_day_id,
                                         lesson_type=lesson_type)

        # Delete.ready_timetable_by_date(self.date_replacement)
        """
        Необходимо удалять только определённые строки по дате, типу профиля и id, а не всё по одной дате
        """
        Insert.ready_timetable(self.ready_timetable_data)

    def get_names_array_by_type_name(self, type_name: str) -> list:
        """Получить массив наименований по пиру профиля"""
        if type_name == 'group_':
            return self.group__names

        elif type_name == 'teacher':
            return self.teacher_names

        return []

    def replacements_join_timetable(self,
                                    date_: str = None,
                                    type_name: str = 'group_',
                                    names_array: list = None,
                                    week_day_id: int = 0,
                                    lesson_type: bool = True) -> None:
        """
        Соединяем замены с основным расписанием
        :param date_: дата, для которой будет составлено расписание
        :param type_name: тип профиля
        :param names_array: массив наименований групп/преподавателей
        :param week_day_id: id дня недели
        :param lesson_type: тип недели (числитель/знаменатель)
        :return: None
        """
        query_names_in_practice = """SELECT {0}_name 
                                     FROM practice_info 
                                     WHERE '{1}' >= start_date AND '{1}' <= stop_date""".format(type_name, date_)
        names_in_practice = Select.query_(query_names_in_practice)

        if names_array is None:
            names_array = []

        if not names_array:
            names_array = self.get_names_array_by_type_name(type_name)

        for name_ in names_array:
            print("name_", name_)
            timetable = {}

            if (name_,) not in names_in_practice:
                timetable = Select.main_timetable(type_name=type_name,
                                                  name_=name_,
                                                  week_day_id=week_day_id,
                                                  lesson_type=lesson_type,
                                                  check_practice=False,
                                                  date_=date_)

            replacement = Select.replacement(type_name, name_)

            timetable_dict = convert_timetable_to_dict(timetable)

            if self.parse_table_replacement_mode == "only_rep":
                timetable_dict.clear()

            last_num_lesson = None

            for rep_val in replacement:
                """Перебираем строчки с заменами"""

                num_lesson = rep_val[0]
                lesson_by_main_timetable = rep_val[1][0]
                replace_for_lesson = rep_val[2][0]
                rep_name = rep_val[3][0]
                rep_audience_array = rep_val[4]

                if num_lesson in timetable_dict:
                    """Если номер замены есть в основном расписании"""

                    """Перебираем все пары для определённого номера пары"""
                    for les in timetable_dict[num_lesson]:

                        """Индекс пары в массиве пар"""
                        ind = timetable_dict[num_lesson].index(les)
                        name_array = les[-2]

                        if 'по расписанию' in replace_for_lesson.lower():
                            """Обработчик ---по расписанию---"""
                            # учесть ситуацию, когда в основном расписании нет преподов, но он указан в заменах

                            if rep_name in name_array:
                                """Если есть совпадение с преподавателем"""
                                teacher_ind = name_array.index(rep_name)

                                additional_info = replace_for_lesson.lower().split('по расписанию')[-1]
                                timetable_dict[num_lesson][ind][-3] += ' ' + convert_lesson_name(additional_info)
                                timetable_dict[num_lesson][ind][-1][teacher_ind] = rep_audience_array[0]

                            elif rep_name is None:
                                """Если в заменах не указан преподаватель"""
                                timetable_dict[num_lesson][ind][-1] = rep_audience_array

                            else:
                                """Если прошли все условия, то добавляем пару как есть"""

                                if last_num_lesson == num_lesson:
                                    """Если уже редактировали пару с таким же номером"""

                                    if None in name_array:
                                        """Удаляем учителя None и еду аудиторию при наличии"""
                                        ind_none = timetable_dict[num_lesson][ind][-2].index(None)
                                        try:
                                            timetable_dict[num_lesson][ind][-2].pop(ind_none)
                                            timetable_dict[num_lesson][ind][-1].pop(ind_none)
                                        except IndexError:
                                            pass

                                    for rep_audience in rep_audience_array:
                                        """Перебираем аудитории и добавляем инфу об учителе"""
                                        timetable_dict[num_lesson][ind][-2].append(rep_name)
                                        timetable_dict[num_lesson][ind][-1].append(rep_audience)
                                else:

                                    if len(timetable_dict[num_lesson]) == 1:
                                        """Если изменился преподаватель у пары и она одна, то обновляем инфу о новом учителе и кабинете"""
                                        timetable_dict[num_lesson][ind][-2] = [rep_name]
                                        timetable_dict[num_lesson][ind][-1] = rep_audience_array
                                    else:
                                        pass

                        elif replace_for_lesson.strip().lower() == 'нет':
                            """Обработчик ---нет---"""

                            if (len(name_array) == 1 or rep_name is None) and last_num_lesson != num_lesson:
                                """(Если пару ведёт один преподаватель или в заменах не указан преподаватель) и номер в прошлой итерации не равен текущему номеру пары"""
                                del timetable_dict[num_lesson]
                                break

                            else:
                                '''
                                это развилка для ситуаций, когда в заменах одна пара по расписанию, а другая отменяется
                                проблема моего костыля в том, что при малейшей ошибке - код не сработает :(
                                '''

                                if lesson_by_main_timetable in timetable_dict[num_lesson][ind][-3].lower():
                                    del timetable_dict[num_lesson][ind]

                        else:
                            """Обработчик ---остальные случаи---"""

                            if self.parse_table_replacement_mode == "only_rep":
                                replace_for_lesson = lesson_by_main_timetable

                            new_lesson_info = [replace_for_lesson, [rep_name], rep_audience_array]

                            if last_num_lesson == num_lesson:
                                """Если номер в прошлой итерации равен текущему номеру пары"""
                                timetable_dict[num_lesson].append(new_lesson_info)

                            else:
                                timetable_dict[num_lesson] = [new_lesson_info]

                            break

                else:
                    # бывают случаи, когда в основном расписании только одна пара, а в заменах "по расписанию"
                    # указаны 2 пары

                    # НУЖНО УЧЕСТЬ, ВОЗМОЖНОСТЬ НЕКОРРЕКТНОЙ РАБОТЫ МОДУЛЯ ОБРАБОТКИ "нет"
                    if replace_for_lesson.strip().lower() != 'нет':
                        """Если пара не отменяется, то добавляем её как новую"""

                        if (num_lesson == '' or '/' in num_lesson) and num_lesson != last_num_lesson:
                            """Если нет номера пары (практика и тд), то удаляем все пары и заносим только замены"""
                            timetable_dict = {}

                        timetable_dict[num_lesson] = [[replace_for_lesson, [rep_name], rep_audience_array]]

                last_num_lesson = num_lesson

            self.filling_ready_timetable_data(date_, name_, timetable_dict)

    def filling_ready_timetable_data(self,
                                     date_: str,
                                     name_: str,
                                     timetable_dict: dict) -> None:
        """Заполняем массив self.ready_timetable_data и кортеж lesson_names"""
        for num_lesson, lessons_array in timetable_dict.items():

            for one_lesson in lessons_array:
                lesson_name = one_lesson[0]
                teacher_names_array = one_lesson[1]
                audience_array = one_lesson[2]

                [teacher_names_array, audience_array] = combine_teacher_names_and_audience_arrays(teacher_names_array, audience_array)

                ind = 0
                for teacher_name in teacher_names_array:
                    audience = audience_array[ind]
                    type_lesson_mark_array = _get_type_lesson_array(lesson_name, audience)

                    data_one_lesson = (date_, name_, num_lesson, lesson_name, teacher_name, audience, type_lesson_mark_array)

                    self.lesson_names.add(lesson_name)
                    self.ready_timetable_data.append(data_one_lesson)

                    ind += 1
