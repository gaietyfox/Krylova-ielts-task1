# При выполнении проектной деятельности я пользовалась материалами курса,
# консультировалась с преподавателями и с ChatGPT


""" IELTS Writing Task 1 — Телеграм-бот - корпусный помощник

Бот разработан на основе корпусного анализа текстов IELTS Writing Task 1
На текущем этапе реализован базовый функционал:

1) Проверка пользовательского текста (КНОПКА "✍️ Проверить мой текст"):
   - Подсчёт слов (по Word-подобной логике)
   - Проверка соответствия минимуму 150 слов
   - Определение типа задания по ключевым словам
     (pie chart, bar chart, line graph, table, map, process)
   - Вывод средней длины текста по корпусу для данного типа
   - Поиск коллокаций типа «глагол + наречие» из корпуса

2) Ручной выбор типа задания:(КНОПКИ в соответствии с названиями на русском):
   - Карта
   - Круговая диаграмма
   - Линейный график
   - Описание процесса
   - Смешанный тип
   - Столбчатая диаграмма
   - Таблица

Проект может быть расширен:
   - улучшением определения смешанных типов,
   - расширением корпуса,
   - добавлением более глубокого лексического анализа
   - более расширенным комментарием в ответ на текст потенциального сдающего

Бот служит демонстрацией практического применения корпусного анализа :)"""


import asyncio
import json
import re
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

TOKEN = "8176400018:AAHHyfnIKbnu9gmOJdBkBSaJkl6_oNRdcHM"

bot = Bot(token=TOKEN)
dp = Dispatcher()

with open("pairs.json", encoding="utf-8") as f:
    pairs_data = json.load(f)

with open("lengths.json", encoding="utf-8") as f:
    lengths_data = json.load(f)

# Словарь, который хранит состояние каждого пользователя
# (и будет сброшен при перезапуске бота)
user_state = {}


SHOW_VADV_MATCHES = True  # показывать найденные V+Adv в тексте


# Нормализация типа графика:
# приводит строку к единому формату (нижний регистр, "_" вместо пробелов и дефисов),
# чтобы избежать ошибок при сравнении типов в коде и JSON


# Хоть и в моём корпусе уже есть очищенная версия, но
# чат посоветовал мне оставить данный блок, так как:
# - планируется расширение корпуса
# - добавление нового источника
# - пользователю даётся вводить тип вручную


# Безопасное преобразование значения в целое число.
# Поддерживает int, float и строки вида "123" или "123.45".
# В остальных случаях возвращает 0
def safe_to_int(x):
    if isinstance(x, int):
        return x

    if isinstance(x, float):
        return int(x)

    if isinstance(x, str):
        s = x.strip()

        # Проверка: только целое число
        if s.isdigit():
            return int(s)

        # Проверка: число с точкой (например 12.5)
        if re.fullmatch(r"\d+(\.\d+)?", s):
            return int(float(s))

    return 0

def normalize_chart_type(s):
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = s.replace("-", "_")
    s = s.replace(" ", "_")
    return s

def normalize_spaces(text):
    return " ".join(text.split())

def tokenize_words_word_like(text):
    # Word-подобный подсчёт: считаем и слова, и числа
    # (Люди считают слова приближенно иди так же, как в Ворде)
    tokens = re.findall(
        r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:[.,]\d+)*(?:-\d+(?:[.,]\d+)*)?",
        text
    )
    return tokens

def detect_chart_type_from_text(user_text):
    # Определяем тип только по ключевым словам
    # (Но при большем к-ве текстов в корпусе можно добавить и другие слова, не только по прямому названию типа графика)
    t = user_text.lower()

    if "line graph" in t or "line chart" in t:
        return "line_graph"
    if "bar chart" in t or "bar graph" in t:
        return "bar_chart"
    if "pie chart" in t:
        return "pie_chart"
    if "process" in t:
        return "process_diagram"
    if "table" in t:
        return "table"
    if "map" in t or "maps" in t:
        return "map"

    return None


# Получение уникальных русскоязычных типов графиков из корпуса
# Функция проходит по lengths_data, собирает все значения chart_type_rus,
# удаляет дубликаты и возвращает отсортированный список
def get_unique_types_rus_sorted():
    types = []
    for item in lengths_data:
        t = item.get("chart_type_rus", "")
        if t and t not in types:
            types.append(t)
    types.sort()
    return types


# Поиск английского типа графика по его русскому названию
# Используется при выборе типа пользователем кнопкой (на русском языке)
def find_chart_type_by_rus(rus_type):
    for item in lengths_data:
        if item.get("chart_type_rus") == rus_type:
            return item.get("chart_type")
    return None


# Поиск русскоязычного названия типа по английскому коду
# Применяется после автоматического определения типа по ключевым словам
# Использует нормализацию для устойчивого сравнения
def find_rus_by_chart_type(chart_type):
    target = normalize_chart_type(chart_type)
    for item in lengths_data:
        ct = normalize_chart_type(item.get("chart_type", ""))
        if ct == target:
            return item.get("chart_type_rus")
    return None


# Вычисление средней длины текста по выбранному русскому типу графика
# Функция проходит по корпусу (lengths_data),
# суммирует количество слов (wc_custom) для заданного типа
# и возвращает среднее значение
def compute_avg_length_for_rus_type(rus_type):
    total = 0
    count = 0
    for item in lengths_data:
        if item.get("chart_type_rus") == rus_type:
            total += safe_to_int(item.get("wc_custom", 0))
            count += 1
    # Если в корпусе нет текстов данного типа
    if count == 0:
        return 0
    # Округление до 1 знака после запятой
    return round(total / count, 1)


# Получение топа наиболее частотных коллокаций (глагол + наречие)
# из корпуса (pairs.json)
# Функция автоматически определяет, какие ключи используются
# в JSON (phrase / pair / collocation и count / freq и др.),
# сортирует данные по частоте и возвращает список фраз
def get_top_pairs_global(top_n):
    # Если корпус пустой — возвращаем пустой список
    if len(pairs_data) == 0:
        return []

    sample = pairs_data[0]

    # Определяем название поля с самой коллокацией
    phrase_key = None
    if "phrase" in sample:
        phrase_key = "phrase"
    elif "pair" in sample:
        phrase_key = "pair"
    elif "collocation" in sample:
        phrase_key = "collocation"

    # Определение поля, содержащего частоту употребления коллокации.
    # Поскольку структура JSON может различаться (count / freq / frequency / n),
    # функция проверяет доступные ключи и выбирает подходящий
    count_key = None
    if "count" in sample:
        count_key = "count"
    elif "freq" in sample:
        count_key = "freq"
    elif "frequency" in sample:
        count_key = "frequency"
    elif "n" in sample:
        count_key = "n"

    # Если не удалось определить ключ фразы или частоты,
    # возвращаем пустой список для предотвращения ошибки выполнения
    if phrase_key is None or count_key is None:
        return []

    # Создание копии списка коллокаций для последующей сортировки
    arr = pairs_data.copy()

    # Вспомогательная функция для извлечения числового значения частоты
    # Используется безопасное преобразование в целое число
    def get_value(item):
        return safe_to_int(item.get(count_key, 0))

    # Сортировка коллокаций по убыванию частоты
    arr.sort(key=get_value, reverse=True)

    # Формирование списка топ-N наиболее частотных коллокаций
    top = []
    i = 0
    while i < len(arr) and len(top) < top_n:
        phrase = str(arr[i].get(phrase_key, "")).strip()
        if phrase:
            top.append(phrase)
        i += 1

    return top


# Клавиатуры


# Формирование основной клавиатуры с типами заданий
# В верхней части добавляется кнопка «✍️ Проверить мой текст»,
# далее — кнопки с типами графиков, полученными из корпуса
def types_keyboard():
    types = get_unique_types_rus_sorted()
    buttons = []
    # Кнопка проверки текста
    buttons.append([KeyboardButton(text="✍️ Проверить мой текст")])
    # Кнопки типов заданий
    for t in types:
        buttons.append([KeyboardButton(text=t)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def actions_keyboard():
    buttons = [
        [KeyboardButton(text="📏 Средняя длина текста (корпус)")],
        [KeyboardButton(text="⬅ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def back_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="⬅ Назад")]], resize_keyboard=True)

# Обработчик команды /start
# Инициализирует состояние пользователя
# и выводит главное меню с типами заданий

@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id

    # При запуске сбрасываем состояние в обычный режим
    user_state[user_id] = {"mode": "normal"}
    # Отправка приветственного сообщения и основной клавиатуры
    await message.answer(
        "📊 IELTS Writing Task 1 — корпусный помощник\n\n"
        "Выберите тип задания кнопкой (или нажмите «✍️ Проверить мой текст»):",
        reply_markup=types_keyboard()
    )


# Основной обработчик сообщений
# Определяет режим работы пользователя
# и выполняет соответствующую логику

@dp.message()
async def handle_message(message: Message):
    text = message.text
    user_id = message.from_user.id

    if user_id not in user_state:
        user_state[user_id] = {"mode": "normal"}

    mode = user_state[user_id].get("mode", "normal")

    # Обработка кнопки «Проверить мой текст»
    # Переводит пользователя в режим ожидания текста для анализа
    if text == "✍️ Проверить мой текст":
        user_state[user_id] = {"mode": "analyze_wait_text"}
        await message.answer(
            "✍️ Отправьте ваш текст одним сообщением.\n\n"
            "Я определю тип по ключевым словам (pie chart / bar chart / line graph / table / map / process).",
            reply_markup=back_keyboard()
        )
        return

    # Возврат в главное меню и сброс режима
    if text == "⬅ Назад":
        user_state[user_id] = {"mode": "normal"}
        await message.answer(
            "Выберите тип задания (или нажмите «Проверить мой текст»):",
            reply_markup=types_keyboard()
        )
        return


    # Ручной выбор типа задания пользователем
    # Сохраняем выбранный тип в состоянии пользователя
    all_types = get_unique_types_rus_sorted()
    if text in all_types:
        rus_type = text
        chart_type = find_chart_type_by_rus(rus_type)
        user_state[user_id] = {
            "mode": "normal",
            "chart_type_rus": rus_type,
            "chart_type": chart_type
        }
        await message.answer("Тип выбран: " + rus_type + "\nВыберите действие:", reply_markup=actions_keyboard())
        return

    #  Анализ пользовательского текста
    # Выполняется только если бот ожидает текст
    if mode == "analyze_wait_text":
        user_text_clean = normalize_spaces(text)

        wc_user = len(tokenize_words_word_like(user_text_clean))

        detected_chart_type = detect_chart_type_from_text(user_text_clean)
        if detected_chart_type is None:
            await message.answer(
                "❓ Не понял тип текста.\n\n"
                "Я определяю тип только по ключевым словам:\n"
                "- process\n- pie chart\n- bar chart / bar graph\n- line graph / line chart\n- table\n- map / maps\n\n"
                "Можете выбрать тип вручную кнопкой ниже и повторить проверку.",
                reply_markup=types_keyboard()
            )
            user_state[user_id] = {"mode": "normal"}
            return

        detected_rus = find_rus_by_chart_type(detected_chart_type)
        if detected_rus is None:
            detected_rus = "Неизвестный тип"

        avg_length = 0
        if detected_rus != "Неизвестный тип":
            avg_length = compute_avg_length_for_rus_type(detected_rus)

        # Проверка минимального требования IELTS — 150 слов
        if wc_user < 150:
            length_warning = "❗ Внимание: меньше 150 слов (IELTS требует минимум 150).\n"
            length_comment = "📌 Текст заметно короче и не соответствует требованию 150 слов."
        else:
            length_warning = "✅ Длина ≥ 150 слов.\n"
            length_comment = "✅ Отлично: требование 150 слов выполнено."

        # Поиск совпадений коллокаций (глагол + наречие)
        # из сформированного корпуса проекта
        vadv_block = ""
        if SHOW_VADV_MATCHES:
            top_pairs = get_top_pairs_global(40)
            t_low = user_text_clean.lower()

            found = []
            for phrase in top_pairs:
                ph = phrase.lower()
                if ph and ph in t_low and ph not in found:
                    found.append(ph)

            if len(found) == 0:
                vadv_block = "🔗 V+Adv из корпуса, которые нашлись в вашем тексте:\n—\n\n"
            else:
                vadv_block = "🔗 V+Adv из корпуса, которые нашлись в вашем тексте:\n" + "\n".join(found[:7]) + "\n\n"

        response = (
            "✍️ Проверка текста (по корпусу)\n\n"
            "Тип (определён по ключевым словам): " + detected_rus + "\n\n"
            "📏 Длина вашего текста: " + str(wc_user) + " слов\n"
            + length_warning +
            ("📊 Средняя по корпусу: " + str(avg_length) + " слов\n" if avg_length > 0 else "") +
            (length_comment + "\n\n") +
            vadv_block +
            "📌 Подсказка: главное — минимум 150 слов и чёткая структура описания данных."
        )

        await message.answer(response, reply_markup=types_keyboard())
        user_state[user_id] = {"mode": "normal"}
        return

    # Вывод средней длины текста по корпусу (после выбора типа)
    if text == "📏 Средняя длина текста (корпус)":
        rus_type = user_state[user_id].get("chart_type_rus", None)
        if rus_type is None:
            await message.answer("Сначала выберите тип.", reply_markup=types_keyboard())
            return

        avg_length = compute_avg_length_for_rus_type(rus_type)
        await message.answer(
            "📏 Тип: " + rus_type + "\n"
            "Средняя длина по корпусу: " + str(avg_length) + " слов",
            reply_markup=actions_keyboard()
        )
        return

    await message.answer("Выберите действие кнопкой или начните с /start.", reply_markup=types_keyboard())


# Запуск Telegram-бота

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())