import requests
import telebot
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import io
from bs4 import BeautifulSoup
from telebot import types
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from fontTools.ttLib import TTFont
import google.generativeai as genai
import re
from token_1 import TOKEN

bot = telebot.TeleBot(TOKEN)

# Инициализация Google Generative AI
GENAI_API_KEY = "AIzaSyBbXnePF0epC0n4ozmNcPsJsaZxRUgRct0"
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

diff = {}   # Для хранения данных дифференцированного платежа
ann = {}    # Для хранения данных аннуитетного платежа
inf = {}    # Для хранения данных о вкладе
vigu = {}   # Для хранения данных о рассчёте выгоды
ipoteka = {}   # Для хранения данных об ипотеке
currency_rates_cache = {}  # Кэш курсов валют
currency_names_cache = {} # Кэш названий валют
count = 0   # Счётчик отправляемых сообщений


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, 'Здравствуйте, это телеграмм-бот, который может помочь Вам в подсчёте финансовых дел.')
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    button1 = KeyboardButton(text="Курс валют")
    button2 = KeyboardButton(text="Расчёт платежей по кредиту")
    button3 = KeyboardButton(text="Расчёт вклада с учётом инфляции") 
    button4 = KeyboardButton(text="Расчёт выгоды между вкладом и кредитом")
    button5 = KeyboardButton(text="Расчёт платежей по ипотеке")
    button6 = KeyboardButton(text="Вопрос консультанту")
    keyboard.add(button1)
    keyboard.add(button2)
    keyboard.add(button3)
    keyboard.add(button4)
    keyboard.add(button5)
    keyboard.add(button6)
    bot.send_message(message.chat.id, 'Выберите опцию:', reply_markup=keyboard)


@bot.message_handler(content_types=['text'])
def func(message):
    if message.text == "Курс валют":
        get_currency_options(message)
    elif message.text == "Расчёт платежей по кредиту":
        keyboard = telebot.types.InlineKeyboardMarkup()
        button_diff = telebot.types.InlineKeyboardButton(text="Дифференцированные платежи", callback_data='difference')
        button_ann = telebot.types.InlineKeyboardButton(text="Аннуитетные платежи", callback_data='annuent')
        keyboard.add(button_diff)
        keyboard.add(button_ann)
        bot.send_message(message.chat.id, 'Выберите платёж:', reply_markup=keyboard)
    elif message.text == "Расчёт вклада с учётом инфляции":
        bot.send_message(message.chat.id, 'Введите начальную сумму вклада:')
        bot.register_next_step_handler(message, getValue) 
    elif message.text == "Расчёт выгоды между вкладом и кредитом":
        bot.send_message(message.chat.id, "Введите целевую сумму:")
        bot.register_next_step_handler(message, get_target_amount)
    elif message.text == "Расчёт платежей по ипотеке":
        bot.send_message(message.chat.id, 'Введите общую сумму ипотеки:')
        bot.register_next_step_handler(message, getipoteka) 
    elif message.text == "Вопрос консультанту":  # Обработка нажатия на кнопку
        bot.send_message(message.chat.id, "Вы можете задать любой вопрос:")
        bot.register_next_step_handler(message, handle_consultation)


#Разговор с сотрудником
def handle_consultation(message):
    try:
        user_input = message.text
        response = model.generate_content(user_input)
        generated_text = response.text
        # Удаление Markdown-разметки
        plain_text = re.sub(r'[*_`]', '', generated_text)
        bot.reply_to(message, plain_text)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {str(e)}")

#общий график
def plot_payment_histogram(chat_id, payments, title):
    num_payments = len(payments)
    width = max(10, num_payments * 0.3)
    height = 18
    plt.figure(figsize=(width, height))
    plt.bar(range(1, num_payments + 1), payments, color='blue', width=0.5)
    plt.title(title, fontsize=16)
    plt.xlabel('Месяц', fontsize=14)
    plt.ylabel('Платеж (руб.)', fontsize=10)
    plt.xticks(range(1, num_payments + 1), fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig(f"{title}.png")
    plt.close()
    bot.send_photo(chat_id, open(f"{title}.png", 'rb'))

# Курс валют
def get_currency_rates():
    url = "https://www.cbr.ru/currency_base/daily/"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    currency_rates = {}
    currency_names = {}

    for row in soup.find_all('tr')[1:]:
        cells = row.find_all('td')
        if len(cells) > 1:
            currency_code = cells[1].text.strip()
            currency_name = cells[3].text.strip()
            rate = float(cells[4].text.replace(',', '.'))
            currency_rates[currency_code] = rate
            currency_names[currency_code] = currency_name

    return currency_rates, currency_names


def get_currency_options(message):
    global currency_rates_cache, currency_names_cache
    currency_rates_cache, currency_names_cache = get_currency_rates()
    markup = types.InlineKeyboardMarkup()
    buttons = [
        types.InlineKeyboardButton(text=currency, callback_data=currency) 
        for currency in currency_rates_cache.keys()
    ]
    rows = [buttons[i:i + 5] for i in range(0, len(buttons), 5)]
    for row in rows:
        markup.row(*row)
    bot.send_message(message.chat.id, "Доступные курсы валют:", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in currency_rates_cache.keys())
def get_currency_rate(call):
    currency_code = call.data
    rate = currency_rates_cache[currency_code]
    currency_name = currency_names_cache[currency_code]
    bot.send_message(call.message.chat.id, f"Вы выбрали {currency_name} ({currency_code}).")
    bot.send_message(call.message.chat.id, f"Курс {currency_code} к рублю: {rate:.2f} руб.")
    bot.send_message(call.message.chat.id, "Введите количество выбранной валюты:")
    bot.register_next_step_handler(call.message, calculate_cost, currency_code)


def calculate_cost(message, currency_code):
    chat_id = message.chat.id
    try:
        amount = float(message.text)
        rate = currency_rates_cache.get(currency_code)
        if rate:
            total_cost = amount * rate
            bot.send_message(chat_id, f"Чтобы купить {amount:.2f} единиц {currency_code}, вам потребуется {total_cost:.2f} рублей.")
        else:
            bot.send_message(chat_id, "Некорректный код валюты.")
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат ввода. Пожалуйста, введите число.')

#дифференцированный платёж
@bot.callback_query_handler(func=lambda call: call.data == 'difference')
def difer(call):
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "Введите сумму кредита:")
    bot.register_next_step_handler(call.message, get_credit_amount)


def get_credit_amount(message):
    chat_id = message.chat.id
    try:
        diff[chat_id] = {'amount': float(message.text)}
        bot.send_message(chat_id, 'Введите срок кредита (в годах):')
        bot.register_next_step_handler(message, get_credit_term)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат суммы кредита. Пожалуйста, введите число.')


def get_credit_term(message):
    chat_id = message.chat.id
    try:
        diff[chat_id]['term'] = float(message.text)
        bot.send_message(chat_id, 'Введите годовую процентную ставку (%):')
        bot.register_next_step_handler(message, get_interest_rate)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат срока кредита. Пожалуйста, введите число.')


def get_interest_rate(message):
    chat_id = message.chat.id
    try:
        diff[chat_id]['rate'] = float(message.text)
        calculate_payments(chat_id)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат процентной ставки. Пожалуйста, введите число.')


def draw_watermark(c, text): 
    c.saveState() 
    c.setFont("Helvetica", 40)
    c.setFillColorRGB(0.2, 0.2, 0.2, alpha=0.1) 
    width, height = letter 
    positions = [(x, y) for x in range(0, int(width), 200)  
                  for y in range(0, int(height), 150)] 
     
    for x, y in positions: 
        c.translate(x, y) 
        c.rotate(45) 
        c.drawString(-100, 0, text)
        c.resetTransforms()

    c.restoreState() 

def calculate_payments(chat_id):  
    amount = diff[chat_id]['amount']  
    term = diff[chat_id]['term']  
    rate = diff[chat_id]['rate'] / 100  
  
    payments = []  
    monthly_payment = amount / (term * 12)  
    total_interest = 0  
  
    data = [["Month", "Payment", "Interest", "Main Debt", "Remaining Debt"]]  
    remaining_amount = amount  
  
    for i in range(int(term * 12)):  
        interest = remaining_amount * (rate / 12)  
        total_interest += interest  
        payment = monthly_payment + interest  
        payments.append(round(payment, 2))  
        remaining_amount -= monthly_payment  
        data.append([i + 1, round(payment, 2), round(interest, 2), round(monthly_payment, 2), round(remaining_amount, 2)])

    plot_payment_histogram(chat_id, payments, "Дифференцированные платежи")

    total_payment = round(sum(payments), 2)  
    pdf_file = "ДифференцированныеПлатежи.pdf" 
    document = SimpleDocTemplate(pdf_file, pagesize=letter)  
    table = Table(data)  

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))  

    elements = [table]
    document.build(elements, onFirstPage=lambda c, doc: draw_watermark(c, "MIS-Bank"), 
                        onLaterPages=lambda c, doc: draw_watermark(c, "MIS-Bank")) 

    payment_details = f"Общая сумма платежей: {total_payment}\nОбщая сумма процентов: {round(total_interest, 2)}"
    bot.send_message(chat_id, payment_details)
    bot.send_document(chat_id, open(pdf_file, 'rb'))

#ануентный платёж
@bot.callback_query_handler(func=lambda call: call.data == 'annuent')
def annye(call):
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    bot.send_message(chat_id, "Введите сумму кредита:")
    bot.register_next_step_handler(call.message, get_credit_amount1)


def get_credit_amount1(message):
    chat_id = message.chat.id
    try:
        ann[chat_id] = {'amount': float(message.text)}
        bot.send_message(chat_id, 'Введите срок кредита (в годах):')
        bot.register_next_step_handler(message, get_credit_term1)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат суммы кредита. Пожалуйста, введите число.')


def get_credit_term1(message):
    chat_id = message.chat.id
    try:
        ann[chat_id]['term'] = float(message.text)
        bot.send_message(chat_id, 'Введите годовую процентную ставку (%):')
        bot.register_next_step_handler(message, get_interest_rate1)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат срока кредита. Пожалуйста, введите число.')


def get_interest_rate1(message):
    chat_id = message.chat.id
    try:
        ann[chat_id]['rate'] = float(message.text)
        calculate_annuity_payments(chat_id)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат процентной ставки. Пожалуйста, введите число.')


def draw_watermark(c, text): 
    c.saveState() 
    c.setFont("Helvetica", 30)
    c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.2) 
    width, height = letter 
    positions = [(x, y) for x in range(0, int(width), 150)  
                  for y in range(0, int(height), 100)] 
     
    for x, y in positions: 
        c.translate(x, y) 
        c.rotate(45) 
        c.drawString(-50, 0, text)
        c.resetTransforms()
         
    c.restoreState() 


def calculate_annuity_payments(chat_id):
    data = ann[chat_id]
    amount = data['amount']
    term = data['term']
    rate = data['rate'] / 100


    monthly_payment = (amount * (rate / 12)) / (1 - (1 + rate / 12) ** (-term * 12))
    total_payment = monthly_payment * (term * 12)
    total_interest = total_payment - amount

    payments = [round(monthly_payment, 2)] * int(term * 12)
    plot_payment_histogram(chat_id, payments, "Аннуитетные платежи")

    payment_data = [["Month", "Payment", "Interest", "Principal", "Remaining Debt"]]
    remaining_amount = amount

    for i in range(int(term * 12)):
        interest = remaining_amount * (rate / 12)
        principal = monthly_payment - interest
        if remaining_amount < principal:
            principal = remaining_amount
        remaining_amount -= principal

        payment_data.append([i + 1, round(monthly_payment, 2), round(interest, 2), round(principal, 2), round(remaining_amount, 2)])


    pdf_file = "АннуитетныеПлатежи.pdf"
    document = SimpleDocTemplate(pdf_file, pagesize=letter)  
    table = Table(payment_data)  
    table.setStyle(TableStyle([  
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  
        ('GRID', (0, 0), (-1, -1), 1, colors.black)  
    ]))  
    
    # Сохранение документа с таблицей 
    elements = [table] 
    document.build(elements, onFirstPage=lambda c, doc: draw_watermark(c, "MIS-Bank"), onLaterPages=lambda c, doc: draw_watermark(c, "MIS-Bank")) 

    bot.send_message(chat_id, f"Общая сумма платежей: {round(total_payment, 2)}\nОбщая сумма процентов: {round(total_interest, 2)}")
    bot.send_document(chat_id, open(pdf_file, 'rb'))

#Расчёт выгоды вклада    Ежемесячные платежи:\n{', '.join(map(str, payments))}\n  Ежемесячный платеж: {round(monthly_payment, 2)}\n\n
url = "https://www.cbr.ru/hd_base/infl/" 

response = requests.get(url) 
response.raise_for_status() 

soup = BeautifulSoup(response.text, 'html.parser') 

table = soup.find('table', class_='data') 

first_row = table.find_all('tr')[2] 
columns = first_row.find_all('td') 
inflation_value = columns[2].text.strip() 


def getValue(message):
    try:
        inf[message.chat.id] = {'principal': float(message.text)}
        bot.send_message(message.chat.id, 'Введите годовую процентную ставку:')
        bot.register_next_step_handler(message, get_credit)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат суммы вклада. Пожалуйста, введите число.')

def get_credit(message):
    try:
        inf[message.chat.id].update({'rate': float(message.text)})
        bot.send_message(message.chat.id, 'Введите количество месяцев:')
        bot.register_next_step_handler(message, monto)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат годовой ставки по вкладу. Пожалуйста, введите число.')

def monto(message):
    try:
        inf[message.chat.id].update({'months': int(message.text)})
        calculate_investment(message)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат срока вклада. Пожалуйста, введите число.')

def draw_watermark(c, text):
    c.saveState()
    c.setFont("Helvetica", 30)
    c.setFillColorRGB(0.5, 0.5, 0.5, alpha=0.2)
    width, height = letter
    positions = [(x, y) for x in range(0, int(width), 150) for y in range(0, int(height), 100)]
    
    for x, y in positions:
        c.translate(x, y)
        c.rotate(45)
        c.drawString(-50, 0, text)
        c.resetTransforms()
        
    c.restoreState()

def calculate_investment(message):
    data = inf[message.chat.id]
    principal = data['principal']
    rate = data['rate']
    months = data['months']

    table_data = [["Month", "Income per Month", "Total Amount"]]
    monthly_rate = rate / 100 / 12
    final_amount = principal
    total_income = []

    for i in range(int(months)):
        earned_amount = final_amount * monthly_rate
        final_amount += earned_amount
        table_data.append([i + 1, round(earned_amount, 2), round(final_amount, 2)])
        total_income.append(round(final_amount, 2))


    pdf_file = "Вклад.pdf"
    document = SimpleDocTemplate(pdf_file, pagesize=letter)
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements = [table]
    document.build(elements, onFirstPage=lambda c, doc: draw_watermark(c, "MIS-Bank"), onLaterPages=lambda c, doc: draw_watermark(c, "MIS-Bank"))

    inflation_value_num = float(inflation_value.replace(',', '.')) if inflation_value else 0
    inflation_procent = rate - inflation_value_num

    bot.send_message(message.chat.id, f"Итоговая сумма через {months} месяцев составит: {final_amount:.2f} руб.")

    if inflation_procent <= 0:
        bot.send_message(message.chat.id, f"Вклад делать не выгодно: инфляция больше чем вклад на: {inflation_procent:.2f}%")
    else:
        bot.send_message(message.chat.id, f"Выгодное вложение, инфляция ниже процентной ставки на: {inflation_procent:.2f}%")
    
    bot.send_document(message.chat.id, open(pdf_file, 'rb'))

    plot_income_histogram(message.chat.id, total_income)

def plot_income_histogram(chat_id, total_income):
    plt.figure(figsize=(30, 15))
    plt.bar(range(1, len(total_income) + 1), total_income, color='blue', width=0.5)
    plt.title("Доход по вкладу", fontsize=16)
    plt.xlabel('Месяц', fontsize=14)
    plt.ylabel('Сумма (руб.)', fontsize=10)
    plt.xticks(range(1, len(total_income) + 1), fontsize=10)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.savefig("Доход_по_вкладу.png")
    plt.close()

    with open("Доход_по_вкладу.png", 'rb') as img_file:
        bot.send_photo(chat_id, img_file)
        
# Сравнение вклада и кредита
def get_target_amount(message):
    chat_id = message.chat.id
    try:
        vigu[chat_id] = {'target_amount': float(message.text)}
        bot.send_message(chat_id, "Введите годовую процентную ставку по кредиту (%):")
        bot.register_next_step_handler(message, get_credit_interest_rate)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат суммы. Пожалуйста, введите число.')


def get_credit_interest_rate(message):
    chat_id = message.chat.id
    try:
        vigu[chat_id]['credit_interest_rate'] = float(message.text)
        bot.send_message(chat_id, "Введите срок кредита (в месяцах):")
        bot.register_next_step_handler(message, get_credit_term3)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат ставки. Пожалуйста, введите число.')


def get_credit_term3(message):
    chat_id = message.chat.id
    try:
        vigu[chat_id]['credit_term3'] = int(message.text)
        bot.send_message(chat_id, "Введите начальную сумму вклада:")
        bot.register_next_step_handler(message, get_initial_deposit)
    except ValueError:
        bot.send_message(chat_id, 'Некорректный формат срока. Пожалуйста, введите число.')


def get_initial_deposit(message):
    chat_id = message.chat.id
    try:
        vigu[chat_id]['initial_deposit'] = float(message.text)
        bot.send_message(chat_id, "Введите ежемесячный взнос на вклад:")
        bot.register_next_step_handler(message, get_monthly_contribution)
    except ValueError:
        bot.send_message(chat_id, 'Некорректная сумма вклада. Пожалуйста, введите число.')


def get_monthly_contribution(message):
    chat_id = message.chat.id
    try:
        vigu[chat_id]['monthly_contribution'] = float(message.text)
        bot.send_message(chat_id, "Введите годовую процентную ставку по вкладу (%):")
        bot.register_next_step_handler(message, calculate_benefit,
            vigu[chat_id]['target_amount'],
            vigu[chat_id]['credit_interest_rate'],
            vigu[chat_id]['credit_term3'],
            vigu[chat_id]['initial_deposit'],
            vigu[chat_id]['monthly_contribution'])
    except:
        bot.send_message(chat_id, 'Некорректный формат взноса. Пожалуйста, введите число.')


def calculate_credit(loan_amount, annual_interest_rate, months):
    monthly_rate = annual_interest_rate / 12 / 100
    monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    total_payment = monthly_payment * months
    overpayment = total_payment - loan_amount
    return monthly_payment, overpayment


def calculate_deposit(initial_amount, monthly_contribution, annual_interest_rate, target_amount):
    months = 0
    current_amount = initial_amount
    monthly_rate = annual_interest_rate / 12 / 100

    while current_amount < target_amount:
        current_amount += current_amount * monthly_rate
        current_amount += monthly_contribution
        months += 1
    return months, current_amount


def create_comparison_image(chat_id, loan_amount, monthly_payment, overpayment, deposit_time, final_amount):
    # Создание изображения
    img_width = 1200
    img_height = 600
    background_color = (255, 255, 255)  # белый фон
    img = Image.new('RGB', (img_width, img_height), background_color)

    # Создание объекта для рисования
    draw = ImageDraw.Draw(img)

    # Использование шрифта, поддерживающего кириллицу
    font_path = "DejaVuSans.ttf"  # путь к вашему файлу шрифта
    font = ImageFont.truetype(font_path, 20)

    # Плюсы и минусы кредита по сравнению со вкладом
    credits_pros = [
        "Плюсы кредита:",
        f" - Деньги выдают сразу",
        f" - Ежемесячный платеж: {monthly_payment:.2f} руб.",
    ]

    deposit_pros = [
        "Минусы кредита:",
        f" - Нужно платить ежемесячно.",
        f" - Переплата по кредиту: {overpayment:.2f} руб.",
    ]

    deposit_cons = [
        "Плюсы вклада:",
        f" - Итоговая сумма: {final_amount:.2f} руб.",
        f" - Достижение цели: {deposit_time} месяцев.",
    ]

    credits_cons = [
        "Минусы вклада:",
        f" - Время ожидания до конкретной суммы.",
        f" - Возможный быстрый прирост инфляции."
    ]

    # Запись текста на изображение
    y_offset_left = 60  # Начальная позиция для левого столбца (кредит)
    y_offset_right = 60  # Начальная позиция для правого столбца (вклад)

    # Константы для отступов
    line_height = 30  # Высота строки

    # Рисуем плюс вверху слева
    draw.text((70, 20), "+", fill=(0, 255, 0), font=font)

    for line in credits_pros:
        draw.text((50, y_offset_left), line, fill=(0, 0, 0), font=font)
        y_offset_left += line_height  # Увеличиваем позицию

    # Разделительная линия по центру
    draw.line((600, 0, 600, img_height), fill=(0, 0, 0), width=2)

    # Рисуем минус вверху справа
    draw.text((630, 20), "-", fill=(255, 0, 0), font=font)

    # Расположение минусов
    for line in deposit_pros:
        draw.text((650, y_offset_right), line, fill=(0, 0, 0), font=font)
        y_offset_right += line_height  # Увеличиваем позицию

    # Дополнительный отступ перед плюсом вклада
    y_offset_right += 20

    # Плюсы вклада с равными отступами
    for line in deposit_cons:
        draw.text((50, y_offset_right), line, fill=(0, 0, 0), font=font)
        y_offset_right += line_height  # Увеличиваем позицию

    y_offset_right += 10  # Дополнительный отступ перед минусами

    # Минусы вклада остаются справа
    for line in credits_cons:
        draw.text((650, y_offset_right), line, fill=(0, 0, 0), font=font)
        y_offset_right += line_height  # Увеличиваем позицию

    # Сохранение изображения в буфер
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)  # Возвращаемся в начало буфера

    # Отправка изображения через Telegram-бота
    bot.send_photo(chat_id, img_byte_arr)

# Альтернативно в функции calculate_benefit добавьте вызов:
def calculate_benefit(message, target_amount, credit_interest_rate, credit_term3, initial_deposit, monthly_contribution):
    chat_id = message.chat.id
    try:
        deposit_interest_rate = float(message.text)
        monthly_payment, overpayment = calculate_credit(target_amount, credit_interest_rate, credit_term3)
        months_to_reach, final_amount = calculate_deposit(initial_deposit, monthly_contribution, deposit_interest_rate, target_amount)

        # Формирование сообщения с результатами
        result_message = (
            f"1. Если взять кредит на {target_amount:.2f} руб.:\n"
            f"   - Ежемесячный платеж: {monthly_payment:.2f} руб.\n"
            f"   - Переплата по кредиту: {overpayment:.2f} руб.\n"
            f"   - Срок кредита: {credit_term3} месяцев.\n\n"
            f"2. Если копить на вкладе с ежемесячным взносом {monthly_contribution:.2f} руб.:\n"
            f"   - Целевая сумма будет достигнута через {months_to_reach} месяцев.\n"
            f"   - Итоговая сумма на вкладе: {final_amount:.2f} руб."
        )
        bot.send_message(chat_id, result_message)

        # Создаем и отправляем изображение с плюсами и минусами
        create_comparison_image(chat_id, target_amount, monthly_payment, overpayment, months_to_reach, final_amount)

    except ValueError:
        bot.send_message(chat_id, 'Некорректная годовая процентная ставка. Пожалуйста, введите число.')

#Расчёт ипотечных платежей
def getipoteka(message):
    chat_id = message.chat.id
    try:
        ipoteka[chat_id] = {'summ': float(message.text)}
        bot.send_message(chat_id, 'Введите первоначальный взнос:')
        bot.register_next_step_handler(message, get_vznos)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат суммы ипотеки. Пожалуйста, введите число.')


def get_vznos(message):
    chat_id = message.chat.id
    try:
        ipoteka[chat_id]['vznos'] = float(message.text)
        bot.send_message(chat_id, 'Введите годовой процент ставки по ипотеке:')
        bot.register_next_step_handler(message, get_procent)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат первоначального взноса. Пожалуйста, введите число.')


def get_procent(message):
    chat_id = message.chat.id
    try:
        ipoteka[chat_id]['proc'] = float(message.text)
        bot.send_message(chat_id, 'Введите срок ипотеки в годах:')
        bot.register_next_step_handler(message, get_crok)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат ставки по ипотеке. Пожалуйста, введите число.')


def get_crok(message):
    chat_id = message.chat.id
    try:
        ipoteka[chat_id]['srok'] = float(message.text) * 12
        keyboard = telebot.types.InlineKeyboardMarkup()
        button_diff1 = telebot.types.InlineKeyboardButton(text="Дифференцированные платежи", callback_data='differ')
        button_ann1 = telebot.types.InlineKeyboardButton(text="Аннуитетные платежи", callback_data='annu')
        keyboard.add(button_diff1)
        keyboard.add(button_ann1)
        bot.send_message(message.chat.id, 'Выберите вид платежа:', reply_markup=keyboard)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат срока. Пожалуйста, введите число.')


def draw_watermark(c, text): 
    c.saveState() 
    c.setFont("Helvetica", 40)
    c.setFillColorRGB(0.2, 0.2, 0.2, alpha=0.1) 
    width, height = letter 
    positions = [(x, y) for x in range(0, int(width), 200)  
                  for y in range(0, int(height), 150)] 
     
    for x, y in positions: 
        c.translate(x, y) 
        c.rotate(45) 
        c.drawString(-100, 0, text)
        c.resetTransforms()

    c.restoreState() 


@bot.callback_query_handler(func=lambda call: call.data == 'differ')
def diferr(call):
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    
    total_sum = ipoteka[chat_id]['summ']
    vznos = ipoteka[chat_id]['vznos']
    proc = ipoteka[chat_id]['proc'] / 100 / 12
    srok = ipoteka[chat_id]['srok']
    
    loan_amount = total_sum - vznos  
    if loan_amount <= 0:
        bot.send_message(chat_id, 'Первоначальный взнос не должен превышать сумму кредита.')
        return

    payments = []  
    total_payment = 0  
    data = [["Month", "Payment", "Interest", "Main Debt", "Remaining Debt"]]  
    remaining_amount = loan_amount  

    for month in range(1, int(srok) + 1):  
        interest = remaining_amount * proc  
        body_payment = loan_amount / srok  
        monthly_payment = body_payment + interest  
        total_payment += monthly_payment  
        
        payments.append(round(monthly_payment, 2))  
        remaining_amount -= body_payment  
        
        data.append([month, round(monthly_payment, 2), round(interest, 2), round(body_payment, 2), round(remaining_amount, 2)])

    create_pdf(chat_id, data, total_payment, "Платежи по ипотеке")


@bot.callback_query_handler(func=lambda call: call.data == 'annu')
def annu(call):
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
    
    total_sum = ipoteka[chat_id]['summ']
    vznos = ipoteka[chat_id]['vznos']
    proc = ipoteka[chat_id]['proc'] / 100 / 12
    srok = ipoteka[chat_id]['srok']
    
    loan_amount = total_sum - vznos  
    if loan_amount <= 0:
        bot.send_message(chat_id, 'Первоначальный взнос не должен превышать сумму кредита.')
        return

    monthly_payment = (loan_amount * proc * (1 + proc) ** srok) / ((1 + proc) ** srok - 1)
    total_payment = monthly_payment * srok
    
    data = [["Month", "Payment", "Interest", "Main Debt", "Remaining Debt"]]  
    remaining_amount = loan_amount

    for month in range(1, int(srok) + 1):
        interest = remaining_amount * proc
        body_payment = monthly_payment - interest  # Основной долг = Ежемесячный платеж - Процент
        remaining_amount -= body_payment
        data.append([month, round(monthly_payment, 2), round(interest, 2), round(body_payment, 2), round(remaining_amount, 2)])

    create_pdf(chat_id, data, total_payment, "Платежи по ипотеке")

def create_pdf(chat_id, data, total_payment, payment_type):
    pdf_file = f"{payment_type}.pdf" 
    document = SimpleDocTemplate(pdf_file, pagesize=letter)

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ])) 

    elements = [table]
    document.build(elements, 
                   onFirstPage=lambda c, doc: draw_watermark(c, "MIS-Bank"), 
                   onLaterPages=lambda c, doc: draw_watermark(c, "MIS-Bank")) 

    payment_details = f"Общая сумма платежей: {total_payment:.2f}"
    bot.send_message(chat_id, payment_details)
    bot.send_document(chat_id, open(pdf_file, 'rb'))


if __name__ == '__main__':
    bot.infinity_polling()


# def create_pdf(file_name, table_data, watermark_text):
#    document = SimpleDocTemplate(file_name, pagesize=letter)
#    table = Table(table_data)
#    table.setStyle(TableStyle([
#        ('BACKGROUND', (0, 0), (-1, 0), colors.darkorange),
#        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#        ('FONTSIZE', (0, 0), (-1, 0), 12),
#        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#        ('GRID', (0, 0), (-1, -1), 1, colors.black),
#        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
#        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
#        ('FONTSIZE', (0, 1), (-1, -1), 10)
#    ]))
#    def add_watermark(canvas, doc):
#        canvas.saveState()
#        canvas.setFont("Helvetica", 40)
#        canvas.setFillColorRGB(0.2, 0.2, 0.2, alpha=0.1)
#        width, height = letter
#        for x in range(0, int(width), 200):
#            for y in range(0, int(height), 150):
#                canvas.drawString(x, y, watermark_text)
#        canvas.restoreState()
#    elements = [table]
#    document.build(elements, onFirstPage=add_watermark, onLaterPages=add_watermark)
