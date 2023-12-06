from aiogram import Bot, Dispatcher, types
from aiogram.types.message import ContentType
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext

from yookassa import Payment
from config import shop_id, secret_key

from prices import VPN30, VPN90, VPN180
from models import User, Server, Invoice, Promocode, SS_config
from vds_api import create_order, get_orders
import paramiko
import string
import random
import uuid
import json
import requests
import config
import logging
import base64
from time import sleep
from celery import Celery
from celery.schedules import crontab
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta

logging.basicConfig(level=logging.DEBUG, filename='vpn_bot.log')

client = Celery('break_vpn', broker=config.CELERY_BROKER_URL)
client.conf.result_backend = config.CELERY_RESULT_BACKEND
client.conf.timezone = 'Europe/Moscow'

my_id = '182149382'

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

def generate_password(length):
    # Define the characters that can be used in the password
    characters = string.ascii_letters + string.digits
    
    # Generate a random password of given length
    password = ''.join(random.choice(characters) for _ in range(length))
    return password

def ssh_conect_to_server(server_ip, login, password):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(server_ip, '3333', login, password, look_for_keys=False)
    return ssh_client

def get_ss_string(server_ip, user_id):    
    ss_configs = SS_config.select().where(SS_config.server_ip == server_ip)
    #invoices = Invoice.select().join(User).where(Invoice.user == user.id)
    for ss_config in ss_configs:
        if ss_config.is_avalible:
            ss_string = '{cipher}:{password}@{ip}:{port}'.format(
                cipher = ss_config.cipher,
                password = ss_config.password,
                ip = ss_config.server_ip,
                port = ss_config.port
            )
            ss_config.user = User.get(user_id = user_id)
            ss_config.is_avalible = False
            ss_config.save()
            encoded = 'ss://' + str(base64.b64encode(ss_string.encode("utf-8")).decode('utf-8'))
            return encoded

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
            try:
                revoke_vpn(user.user_id)
            except: pass
            user.is_active = False
            if user.order_type == 'shadowsocks':
                ss_conf = SS_config.get(user = user.id)
                ss_conf.password = str(generate_password(6))
                ss_conf.is_avalible = True
                ss_conf.save()
    ss_configs = SS_config.select().where(SS_config.is_avalible == True)
    for conf in ss_configs:
        conf.password = generate_password(6)
        conf.save()
    ss_servers = Server.select().where(Server.server_type == 'shadowsocks')
    ss_dict = {
    "server": "0.0.0.0",
    "port_password": {
        "8381": "foobar1"
},
    "method": "chacha20-ietf-poly1305"
}
    for server in ss_servers:
        ss_configs = SS_config.select().where(SS_config.server_ip == server.server_ip)
        
        for conf in ss_configs:    
            ss_dict['port_password'][conf.port] = conf.password
        with open('server-multi-passwd.json', 'w') as file:
            json.dump(ss_dict, file, indent=4)
        ssh_client = ssh_conect_to_server(server.server_ip, server.server_login, server.server_password)
        stdin, stdout, stderr = ssh_client.exec_command('rm -rf server-multi-passwd.json')
        with ssh_client.open_sftp() as sftp:
            sftp.put('server-multi-passwd.json','server-multi-passwd.json')
        stdin, stdout, stderr = ssh_client.exec_command('ss-manager --manager-address /var/run/shadowsocks-manager.sock -c server-multi-passwd.json')
        
        
    
            
@client.task()
def check_avalible_servers():
    avalible_clients = 0
    servers = Server.select()
    for server in servers:
        avalible_clients += 10 - int(server.clients)
    if avalible_clients < 5:
        #order = create_order()
        send_msg('182149382', 'Нужно больше серверов')

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
    
def get_avalible_order_id(server_type):
    servers = Server.select()
    for server in servers:
        if server.clients < 10 and server.server_type == server_type:
            return server.order_id
    send_msg('182149382', 'Нет доступных серверов')
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
        order_id = get_avalible_order_id('openvpn') #Ищем доступный сервер
        while order_id == 'Not avalible':
            sleep(60)
            order_id = get_avalible_order_id('openvpn') #Ищем доступный сервер
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
    
@client.task()
def create_shadow(data):
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
    '''invoice, new_invoice = Invoice.get_or_create(
        total_amount = data['total_amount'],
        invoice_payload = data['invoice_payload'],
        telegram_payment_charge_id = data['telegram_payment_charge_id'],
        provider_payment_charge_id = data['provider_payment_charge_id'],
        user = data['user']
    )
    
    if not new_invoice:
        logging.info('Платеж с ID {payid} уже существует.'.format(
            payid = data['telegram_payment_charge_id']
        ))'''
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
        order_id = get_avalible_order_id('shadowsocks') #Ищем доступный сервер
        while order_id == 'Not avalible':
            sleep(60)
            order_id = get_avalible_order_id('shadowsocks') #Ищем доступный сервер
        server = Server.get(order_id=order_id)
        #ssh_client = ssh_conect_to_server(server.server_ip, server.server_login, server.server_password)
        
        current_clients = server.clients
        server.clients = int(current_clients) + 1
        server.save()
        
        data = {'expire_in': date.today() + timedelta(expire),
                'is_active': True,
                'is_freemium': False,
                'order_id': server.order_id,
                'order_type': 'shadowsocks'
                }
        query = User.update(data).where(User.user_id==user_id)
        query.execute()
        
        logging.info('Создан пользователь {user_id}'.format(
            user_id = user_id
        ))
        
        msg_instruction = 'Инструкция по использованию:\n\nСкачайте приложение\nДля Айфона: https://apps.apple.com/ru/app/streisand/id6450534064\nДля Андроида: https://play.google.com/store/apps/details?id=com.github.shadowsocks\nСледуйте инструкции\nДля айфона https://www.youtube.com/shorts/mA-vyXmBw0A\nДля андроида https://youtube.com/shorts/EWwxu6BVAuo\n\nСтрока для подключения:\n'
        send_msg(user_id, msg_instruction)
        ss_string =get_ss_string(server.server_ip, user_id)
        send_msg(user_id, ss_string)
        send_msg('182149382', 'Куплена новая подписка!')
        return 200

@client.task()
def create_shadow_trial(data):
    user_id = data['user_id']
    expire = int(data['expire_in'])
    entry, is_new = User.get_or_create(
            user_id = user_id
        )
    data['user'] = entry
    
    order_id = get_avalible_order_id('shadowsocks') #Ищем доступный сервер
    print(order_id)
    while order_id == 'Not avalible':
        sleep(60)
        order_id = get_avalible_order_id('shadowsocks') #Ищем доступный сервер
    server = Server.get(order_id=order_id)
    #ssh_client = ssh_conect_to_server(server.server_ip, server.server_login, server.server_password)
    
    current_clients = server.clients
    server.clients = int(current_clients) + 1
    server.save()
    
    data = {'expire_in': date.today() + timedelta(expire),
            'is_active': True,
            'is_freemium': True,
            'order_id': server.order_id,
            'order_type': 'shadowsocks'
            }
    query = User.update(data).where(User.user_id==user_id)
    query.execute()
    
    logging.info('Создан пользователь {user_id}'.format(
        user_id = user_id
    ))
    msg_instruction = 'Вы активировали 7 дней бесплатного периода. Инструкция по использованию:\n\nСкачайте приложение\nДля Айфона: https://apps.apple.com/ru/app/streisand/id6450534064\nДля Андроида: https://play.google.com/store/apps/details?id=com.github.shadowsocks\nСледуйте инструкции\nДля айфона https://www.youtube.com/shorts/mA-vyXmBw0A\nДля андроида https://youtube.com/shorts/EWwxu6BVAuo\n\nСтрока для подключения:\n'
    send_msg(user_id, msg_instruction)
    ss_string =get_ss_string(server.server_ip, user_id)
    send_msg(user_id, ss_string)
    send_msg('182149382', 'Активирована пробная подписка')
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
inline_btn_trial = InlineKeyboardButton('ТестДрайв', callback_data='vpn_btn_trial')
start_kb1 = InlineKeyboardMarkup().add(inline_btn_30, inline_btn_90, inline_btn_180, inline_btn_trial, inline_btn_promo)

@dp.message_handler(commands=['start'])
async def start(message: types.message):
    user, is_new = User.get_or_create(
            user_id = message.from_user.id
        )
    send_msg(my_id, 'Нажали старт')
    await message.answer('Привет {name}!\nЗдесь ты можешь приобрести подписку на VPN\n1 месяц - 200р\n3 месяца (-10%) - 540р\n6 месяцев 9 (-20%) - 960р\nТестДрайв - пробный период на 7 дней БЕСПЛАТНО!\n\nУ нас лишь одно правило - НЕ КАЧАТЬ И НЕ РАЗДАВАТЬ ТОРРЕНТЫ!\nЗа нарушение - бан навсегда без возврата денег.\n\nЕсли возникли проблемы, то напиши на vpn@prvms.ru и укажи в теме свой ID {id}'.format(
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

def init_payment(user_id, amount):
    idempotence_key = str(uuid.uuid4())
    url = 'https://api.yookassa.ru/v3/payments'
    
    newheaders = {
    'Idempotence-Key': idempotence_key,
    'Content-Type': 'application/json'
    }
    
    data = {
                "amount": {
                "value": str(amount),
                "currency": "RUB"
                },
                "confirmation": {
                "type": "embedded"
                },
                "capture": True
        }
    
    resp = requests.post(url, auth=(shop_id, secret_key), json=data, headers=newheaders).json()
    confirmation_token = resp['confirmation']['confirmation_token']
    payment_id = resp['id']
    with open('index.html', 'r') as file:
        payment_html = file.read().replace('toreplace', str(confirmation_token))
    return payment_id, payment_html

@client.task()
def check_payment(payment_id, user_id, expire_in): 
       
    idempotence_key = str(uuid.uuid4())
    url = f'https://api.yookassa.ru/v3/payments/{payment_id}'
    
    newheaders = {
    'Idempotence-Key': idempotence_key,
    'Content-Type': 'application/json'
    }
    payment_info = {}
    timeout = 600
    while timeout > 0:
        try:
            resp = requests.get(url, auth=(shop_id, secret_key), headers=newheaders).json()
            if resp['status'] == 'succeeded':
                payment_info['user_id'] = str(user_id)
                payment_info['expire_in'] = str(expire_in)
                send_msg(user_id, 'Платеж прошел успешно! Обработаю информацию, это займет немного времени.')
                create_shadow.apply_async(args=[payment_info])
                return 'Done'
        except:
            send_msg(user_id, 'Ошибка обработки платежа. Обратитесь в поддержку на vpn@prvms.ru или повторите позже.')
            return 'Error response'
        sleep(1)
        timeout -= 1
    return 'Timeout'

@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_30')
async def process_callback_button_30(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    user_id = callback_query.from_user.id
    payment_id, payment_html = init_payment(user_id, 200)
    
    url = f'https://yoomoney.ru/checkout/payments/v2/contract?orderId={payment_id}'
    
    pay_btn = InlineKeyboardButton('Оплатить', url=url)
    pay_markup = InlineKeyboardMarkup().add(pay_btn)
    
    check_payment.apply_async(args=[payment_id, user_id, '30'])
    await bot.send_message(chat_id=user_id, text='К оплате 200 рублей', reply_markup=pay_markup)
    


@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_90')
async def process_callback_button_90(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    user_id = callback_query.from_user.id
    payment_id, payment_html = init_payment(user_id, 540)
    
    url = f'https://yoomoney.ru/checkout/payments/v2/contract?orderId={payment_id}'
    
    pay_btn = InlineKeyboardButton('Оплатить', url=url)
    pay_markup = InlineKeyboardMarkup().add(pay_btn)
    
    check_payment.apply_async(payment_id, user_id, '90')
    await bot.send_message(chat_id=user_id, text='К оплате 540 рублей', reply_markup=pay_markup)
    
@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_180')
async def process_callback_button_180(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    user_id = callback_query.from_user.id
    payment_id, payment_html = init_payment(user_id, 960)
    
    url = f'https://yoomoney.ru/checkout/payments/v2/contract?orderId={payment_id}'
    
    pay_btn = InlineKeyboardButton('Оплатить', url=url)
    pay_markup = InlineKeyboardMarkup().add(pay_btn)
    
    check_payment.apply_async(payment_id, user_id, '180')
    await bot.send_message(chat_id=user_id, text='К оплате 960 рублей', reply_markup=pay_markup)
    
@dp.callback_query_handler(lambda c: c.data == 'vpn_btn_trial')
async def process_callback_trial(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_id = callback_query.from_user.id
    
    user = User.get(user_id = user_id)
    
    #print(user.trial_avalible)            
    if user.trial_avalible == True:    
        user.trial_avalible = False
        user.save()        
        data = {}
        data['user_id'] = user_id
        data['expire_in'] = '7'
    
        create_shadow_trial.apply_async(args=[data])
        send_msg(my_id, 'Создаю новый триал')
    else:
        send_msg(user_id, 'Вы уже активировали пробный период')
          
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
    create_shadow.apply_async(args=[payment_info])
    return await message.answer('Платеж прошел успешно! Обработаю информацию, это займет немного времени.')