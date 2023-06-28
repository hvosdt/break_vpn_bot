from aiogram import Bot, Dispatcher, types
from aiogram.types.message import ContentType
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from prices import VPN30, VPN90, VPN180
from models import User, Server, Invoice, Promocode
from vds_api import create_order, get_orders

import paramiko
import requests
import config
import logging
from time import sleep
from celery import Celery
from celery.schedules import crontab
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta


logging.basicConfig(level=logging.DEBUG, filename='vpn_bot.log')

client = Celery('break_vpn', broker=config.CELERY_BROKER_URL)
client.conf.result_backend = config.CELERY_RESULT_BACKEND
client.conf.timezone = 'Europe/Moscow'


client.conf.beat_schedule = {
    'check_subscription': {
        'task': 'handlers.check_subscription',
        'schedule': crontab(hour=config.CHECK_HOUR, minute=config.CHECK_MINUTE)
    },
    'check_avalible_servers': {
        'task': 'handlers.check_avalible_servers',
        'schedule': 1800.0
    }
}

bot = Bot(token=config.TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

def ssh_conect_to_server(server_ip, login, password):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(server_ip, '3333', login, password, look_for_keys=False)
    return ssh_client

@client.task()
def check_subscription():
    users = User.select()
    for user in users:
        expire = user.expire_in.strftime('%Y-%m-%d') 
        check = date.today() + timedelta(3)
        
        if str(expire) == str(check):
            msg = 'До окончания вашей подписки осталось 3 дня. Для проделния, нажмите /start и оплатите подписку.'
            send_msg(user.user_id, msg)
        if str(expire) == str(date.today()):
            revoke_vpn(user.user_id)
            
@client.task()
def check_avalible_servers():
    avalible_clients = 0
    servers = Server.select()
    for server in servers:
        avalible_clients += (int(server.server_plan) - int(server.clients))
    if avalible_clients < 10:
        order = create_order()

def revoke_vpn(user_id):
    user = User.get(user_id = user_id)
    server = Server.get(order_id = user.order_id)
    ssh_client = ssh_conect_to_server(server.server_ip, server.server_login, server.server_password)
    command = './revoke_user.sh {name}'.format(name=user.user_id)
    stdin, stdout, stderr = ssh_client.exec_command(command)
    mes = 'Ваша подписка прекращена. Для возобновления работы, нажмите /start и купите новую подписку.'
    send_msg(user.user_id, mes)
            

def send_msg(chat_id, text):
    response = requests.post('https://api.telegram.org/bot{token}/sendMessage?chat_id={chat_id}&text={text}&disable_web_page_preview=True'.format(
        token = config.TELEGRAM_TOKEN,
        chat_id = chat_id,
        text = text
    ))
    
def send_document(chat_id, doc):
    '''
    response = requests.post('https://api.telegram.org/bot{token}/sendDocument?chat_id={chat_id}&document={doc}'.format(
        token = config.TELEGRAM_TOKEN,
        chat_id = chat_id,
        doc = '{name}.ovpn'.format(name=chat_id)
    ))
    '''
    url = 'https://api.telegram.org/bot{token}/sendDocument'.format(token=config.TELEGRAM_TOKEN)
    resp = requests.post(url, data={'chat_id': chat_id}, files={'document': doc})

    print(resp.json())
    
def get_avalible_order_id():
    servers = Server.select()
    for server in servers:
        if server.clients < 10:
            return server.order_id
    return 'Not avalible'

def get_order_by_id(id):
    orders = get_orders()
    for order in orders['orders']:
        if order['orderid'] == id:
            return order

@client.task()
def create_vpn(data):
    user_id = data['user_id']
    expire = int(data['expire_in'])
    entry, is_new = User.get_or_create(
            user_id = user_id
        )
    if entry.promo:
        expire += 30
        entry.promo = False
        entry.save()
    data['user'] = entry
    invoice, new_invoice = Invoice.get_or_create(
        total_amount = data['total_amount'],
        invoice_payload = data['invoice_payload'],
        telegram_payment_charge_id = data['telegram_payment_charge_id'],
        provider_payment_charge_id = data['provider_payment_charge_id'],
        user = data['user']
    )
    
    if not new_invoice:
        logging.info('Платеж с ID {payid} уже существует.'.format(
            payid = data['telegram_payment_charge_id']
        ))
    if entry.is_active == True:
            data = {'expire_in': entry.expire_in + timedelta(expire),
                'is_active': True,
                'is_freemium': False
                }
            query = User.update(data).where(User.user_id==user_id)
            query.execute()
            send_msg(user_id, 'Ваша подписка продлена!')
            logging.info('Подписка для пользователя {user_id} продлена {days}на дней'.format(
                user_id = user_id,
                days = expire
            ))
            return 100
    else:
        order_id = get_avalible_order_id() #Ищем доступный сервер
        while order_id == 'Not avalible':
            sleep(60)
            order_id = get_avalible_order_id() #Ищем доступный сервер
        server = Server.get(order_id=order_id)
        ssh_client = ssh_conect_to_server(server.server_ip, server.server_login, server.server_password)
        
        current_clients = server.clients
        server.clients = int(current_clients) + 1
        server.save()
        
        data = {'expire_in': date.today() + timedelta(expire),
                'is_active': True,
                'is_freemium': False,
                'order_id': server.order_id
                }
        query = User.update(data).where(User.user_id==user_id)
        query.execute()
        
        command = './add_user.sh {name}'.format(name=user_id)
        logging.info('Создан пользователь {user_id}'.format(
            user_id = user_id
        ))
        
        stdin, stdout, stderr = ssh_client.exec_command(command)
        sleep(20)
        
        msg_instruction = 'Инструкция по использованию:\n\n1. Скачай приложение OpenVPN Connect\n\n✔️ Для Айфона:\nhttps://apps.apple.com/ru/app/openvpn-connect-openvpn-app/id590379981\n\n✔️ Для Андроида:\nhttps://play.google.com/store/apps/details?id=net.openvpn.openvpn\n'
        send_msg(user_id, msg_instruction)
        
        with ssh_client.open_sftp() as sftp:
            name = user_id
            sftp.get('{name}.ovpn'.format(name=name), 'ovpn/{name}.ovpn'.format(name=name))
        sleep(20)
        doc = open('ovpn/{name}.ovpn'.format(name=name), 'rb')
        send_document(user_id, doc)
        msg = '2. Открой файл ⬆️ в приложении OpenVPN Connect и нажми ADD.\n\n3. Включи VPN и радуйся жизни!\nЗа 3 дня до истечения срока подписки, я тебе об этом напомню.'.format(
            name=user_id
        )
        sleep(5)
        send_msg(user_id, msg)
        return 200
     
@dp.message_handler(commands=['check'])
async def check(message: types.message):
    users = User.select()
    for user in users:
        
        expire = user.expire_in.strftime('%Y-%m-%d')
        print(expire)
        check = date.today() + timedelta(3)
        print(check)
        if str(expire) == str(check):
            print('asd')

inline_btn_30 = InlineKeyboardButton('1 месяц', callback_data='vpn_btn_30')
inline_btn_90 = InlineKeyboardButton('3 месяца', callback_data='vpn_btn_90')
inline_btn_180 = InlineKeyboardButton('6 месяцев', callback_data='vpn_btn_180')
inline_btn_promo =InlineKeyboardButton('Промокод', callback_data='btn_promocode')
start_kb1 = InlineKeyboardMarkup().add(inline_btn_30, inline_btn_90, inline_btn_180, inline_btn_promo)

@dp.message_handler(commands=['start'])
async def start(message: types.message):
    user, is_new = User.get_or_create(
            user_id = message.from_user.id
        )
    await message.answer('Привет {name}!\nЗдесь ты можешь приобрести подписку на VPN\n1 месяц - 200р\n3 месяца (-10%) - 540р\n6 месяцев 9 (-20%) - 960р\n\nУ нас лишь одно правило - НЕ КАЧАТЬ И НЕ РАЗДАВАТЬ ТОРРЕНТЫ!\nЗа нарушение - бан навсегда без возврата денег.\n\nЕсли возникли проблемы, то напиши на vpn@prvms.ru и укажи в теме свой ID {id}'.format(
        name=message.from_user.first_name,
        id = message.from_user.id
    ), reply_markup=start_kb1)
    
class PromoForm(StatesGroup):
    promocode = State()
    
@dp.callback_query_handler(lambda c: c.data == 'btn_promocode')
async def process_promocode_btn(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    await PromoForm.promocode.set()
    await bot.send_message(chat_id = user_id, text="Напишите промокод")

# Сюда приходит ответ с appid
@dp.message_handler(state=PromoForm.promocode)
async def process_app_id(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        user_text = message.text.lower()
        
        try:
            promo = Promocode.get(promocode = user_text)
            if user_text == promo.promocode:
                promo.used += 1
                promo.save()
                
                user = User.get(user_id = message.from_user.id)
                
                if user.trial_avalible == True:    
                    user.promo = True
                    user.trial_avalible = False
                    user.save()
                    await message.answer('Принято! Вам в подарок дополнительный месяц подписки!')
                else:
                    await message.answer('Вы уже активировали дополнительный месяц подписки.')    
            else:
                logging.info('промокод не найден')
                await message.answer('Промокод не найден!')
        except:
            logging.warning('Ошибка получения промо')
            await message.answer('Промокод не найден!')
        
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_30')
async def process_callback_button1(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    await bot.send_invoice(
        user_id,
        title = 'Подписка на VPN',
        description = 'на 1 месяц',
        provider_token = config.PAYMENTS_TOKEN,
        currency = 'rub',
        #photo_url="https://milalink.ru/uploads/posts/2018-02/1518206226_selfi-zhizn-napokaz.jpg",
        #photo_width=416,
        #photo_height=234,
        #photo_size=416,
        is_flexible=False,
        prices=[VPN30],
        start_parameter="vpn-subscription",
        payload="30")

@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_90')
async def process_callback_button1(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    await bot.send_invoice(
        user_id,
        title = 'Подписка на VPN',
        description = 'на 3 месяца',
        provider_token = config.PAYMENTS_TOKEN,
        currency = 'rub',
        #photo_url="https://milalink.ru/uploads/posts/2018-02/1518206226_selfi-zhizn-napokaz.jpg",
        #photo_width=416,
        #photo_height=234,
        #photo_size=416,
        is_flexible=False,
        prices=[VPN90],
        start_parameter="vpn-subscription",
        payload="90")
    
@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_180')
async def process_callback_button1(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    await bot.send_invoice(
        user_id,
        title = 'Подписка на VPN',
        description = 'на 6 месяцев',
        provider_token = config.PAYMENTS_TOKEN,
        currency = 'rub',
        #photo_url="https://milalink.ru/uploads/posts/2018-02/1518206226_selfi-zhizn-napokaz.jpg",
        #photo_width=416,
        #photo_height=234,
        #photo_size=416,
        is_flexible=False,
        prices=[VPN180],
        start_parameter="vpn-subscription",
        payload="180")
    
# pre checkout  (must be answered in 10 seconds)
@dp.pre_checkout_query_handler(lambda query: True)
async def pre_checkout_query(pre_checkout_q: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# successful payment
@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: types.Message):
    payment_info = message.successful_payment.to_python()
    
    #for k, v in payment_info.items():
    #    print(f"{k} = {v}")
    #    data = {str(k): str(v)}
 
    payment_info['user_id'] = message.chat.id
    payment_info['expire_in'] = payment_info['invoice_payload']
    #print(data)
    logging.info('Платеж от {userid} на сумму {amount} прошел успешно. ID платежа: {payid}'.format(
        userid = payment_info['user_id'],
        amount = payment_info['total_amount'],
        payid = payment_info['telegram_payment_charge_id']
    ))
    create_vpn.apply_async(args=[payment_info])
    return await message.answer('Платеж прошел успешно! Обработаю информацию, это не займет много времени.')