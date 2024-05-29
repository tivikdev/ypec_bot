from datetime import datetime

# My Modules
from bot.functions import get_time_for_timetable
from bot.functions import get_paired_num_lesson
from bot.functions import get_joined_text_by_list
from bot.functions import get_week_day_name_by_id


class MessageTimetable:
    def __init__(self,
                 name_: str,
                 date_str: str,
                 data_ready_timetable: list,
                 data_dpo: list = False,
                 start_text: str = "Расписание на ",
                 view_name: bool = True,
                 view_type_lesson_mark: bool = False,
                 view_week_day: bool = False,
                 view_add: bool = True,
                 view_time: bool = False,
                 view_dpo_info: bool = False,
                 mode: str = "telegram",
                 format_: bool = True,
                 type_format: str = "message",
                 format_timetable: str = "default"):
        self.name_ = name_
        self.date_str = date_str
        self.data_ready_timetable = data_ready_timetable
        self.data_dpo = data_dpo
        self.start_text = start_text

        # персональные настройки отображения сообщения
        self.view_name = view_name
        self.view_type_lesson_mark = view_type_lesson_mark
        self.view_week_day = view_week_day
        self.view_add = view_add
        self.view_time = view_time
        self.view_dpo_info = view_dpo_info

        self.mode = mode  # мод - телеграм или вконтакте
        self.format_ = format_  # добавляем html-теги
        self.type_format = type_format  # message и txt - определяет вид форматирования числ. и знам.
        self.format_timetable_empty = format_timetable  # формат для пустого сообщения

        self.message = ''
        self.num_lesson_array = []
        self.type_lesson_mark_array = set()

    def check_view_name(self) -> str:
        """Если необходимо отображать name_"""
        if self.view_name:
            if self.format_ and self.mode == "telegram":
                return f"<b>{self.name_}</b>"
            else:
                return f"{self.name_}"
        return ''

    def check_view_week_day(self) -> str:
        """Если необходимо отображать день недели"""
        if self.view_week_day:
            week_day_id = datetime.strptime(self.date_str, '%d.%m.%Y').isoweekday() - 1
            bold = self.type_format == 'txt'
            return f" ({get_week_day_name_by_id(week_day_id, type_case='short_view', bold=bold)})"
        return ""

    def first_string_format(self) -> str:
        """Форматирование первой строки"""
        if self.format_timetable_empty == "default":
            # Стартовое сообщение + дата + день недели при необходимости
            return f"{self.start_text}{self.date_str}{self.check_view_week_day()}\n"

        elif self.format_timetable_empty == "only_date":
            return self.date_str + '\n'

        return ''

    def create_d_lessons(self, data: list) -> dict:
        """Создаём словарь, в котором ключ - номер пары, а значение - массив массивов пар"""
        d_lessons = {}
        for one_line in data:
            num_lesson = one_line[0]
            last_num = None
            num_array = []

            for num in num_lesson:
                """Перебираем номера пар"""
                self.num_lesson_array.append(num)

                if last_num is None or int(num)-1 == int(last_num):
                    num_array.append(num)

                else:
                    new_num_lesson = get_paired_num_lesson(num_array)
                    if new_num_lesson not in d_lessons:
                        d_lessons[new_num_lesson] = []
                    d_lessons[new_num_lesson].append(one_line[1:])
                    num_array = [num]

                if num == num_lesson[-1]:
                    new_num_lesson = get_paired_num_lesson(num_array)
                    if new_num_lesson not in d_lessons:
                        d_lessons[new_num_lesson] = []
                    d_lessons[new_num_lesson].append(one_line[1:])

                last_num = num

        return d_lessons

    def formatting_line_text(self,
                             one_line: list,
                             line_text: str) -> str:
        """Получаем линию-строку для одной пары"""
        if not self.format_ or one_line[2][0] is None:
            """Если не включено форматирование текста или типы пары - обычный"""
            return line_text
        else:
            lesson_type = one_line[2][0]
            if lesson_type:
                """Если числитель"""
                if self.type_format == "message":
                    return f"◽ {line_text}"

                elif self.type_format == "txt":
                    return f"Числитель {line_text}"

            else:
                """Если знаменатель"""
                if self.type_format == "message":
                    return f"◾ {line_text}"

                elif self.type_format == "txt":
                    return f"Знаменатель {line_text}"

    def get_message_lessons(self, data: list) -> str:
        """Получаем текст, составленный из data"""
        """Создаём словарь спаренных пар (1-2 и тд)"""
        if not data:
            return 'ОТСУТСТВУЕТ\n'

        lessons_message = ''
        d_lessons = self.create_d_lessons(data)

        for num_lesson, one_line_array in sorted(d_lessons.items()):
            """Перебираем массивы пар"""

            for one_line in one_line_array:
                """Перебираем конкретные пары"""
                lesson_text = one_line[0][0]
                json_group_or_teacher_name_and_audience = one_line[1]
                type_lesson_mark_array = one_line[3]
                [self.type_lesson_mark_array.add(x) for x in type_lesson_mark_array]

                group_or_teacher_name = json_group_or_teacher_name_and_audience.keys()
                audience = json_group_or_teacher_name_and_audience.values()

                """Составляем строку"""
                num_text = "" if num_lesson == '' else f"{num_lesson})"
                group_or_teacher_name_text = get_joined_text_by_list(group_or_teacher_name)
                audience_text = get_joined_text_by_list(audience)

                add_group_or_teacher_name_text = f"({group_or_teacher_name_text})" if self.view_add else ""

                line_text = f"{num_text} {lesson_text} {audience_text} {add_group_or_teacher_name_text}\n"

                lessons_message += self.formatting_line_text(one_line, line_text)

        return lessons_message

    def check_view_time(self) -> str:
        """Добавляем время начала и окончания занятий при необходимости"""
        if self.view_time:
            return get_time_for_timetable(self.date_str, self.num_lesson_array)
        return ''

    def check_type_lesson(self) -> str:
        """Добавляем смайлик-маркировку"""
        '''
            0. ⚪ - обычные пары (оранжевый)
            1. 🟢 - дистант (зелёный)
            2. 🔵 - лабы (синий)
            3. 🟣 - экскурсия (белый)
            4. 🟡 - практика или п/з(желтый)
            5. 🟠 - консультация (фиолетовый)
            6. 🔴 - экзамен или к/р (красный)
        '''
        smile_type_lesson = {0: '⚪',
                             1: '🟢',
                             2: '🔵',
                             3: '🟣',
                             4: '🟡',
                             5: '🟠',
                             6: '🔴'}
        type_lesson_mark_message = ''
        if self.view_type_lesson_mark and self.type_lesson_mark_array and None not in self.type_lesson_mark_array:
            for ind_type_lesson in sorted(self.type_lesson_mark_array, reverse=True):
                type_lesson_mark_message += smile_type_lesson.get(ind_type_lesson, '')
        return type_lesson_mark_message

    def get(self) -> str:
        """Получаем текстовое представление расписания по заданным параметрам"""

        """Добавляем name_ группы при необходимости"""
        view_name_message = self.check_view_name()

        """Добавляем стартовое сообщение, дату и день недели при необходимости"""
        first_string_message = self.first_string_format()

        """Добавляем само расписание"""
        lessons_message = self.get_message_lessons(self.data_ready_timetable)

        """Добавляем время начала и окончания при необходимости"""
        view_time_message = self.check_view_time()

        """Определяем маркировку"""
        type_lesson_mark_message = self.check_type_lesson()

        """Добавляем информацию о ДПО"""
        dpo_message = ''
        if self.view_dpo_info and self.data_dpo:
            dpo_message += '\nДПО:\n'
            dpo_message += self.get_message_lessons(self.data_dpo)

        """Составляем сообщение из кусков"""
        self.message = f"{view_name_message} {type_lesson_mark_message}\n" \
                       f"{first_string_message}" \
                       f"{lessons_message}" \
                       f"{view_time_message}" \
                       f"{dpo_message}"

        return self.message
