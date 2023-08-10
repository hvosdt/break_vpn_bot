from peewee import *
import config
import datetime

db = PostgresqlDatabase(config.DB_NAME, user=config.DB_USERNAME, password=config.DB_PASSWORD)
#db = SqliteDatabase('vpn_bot.db')

class BaseModel(Model):
    class Meta:
        database = db
    
class Server(BaseModel):
    order_id = TextField(default='0', null=False) 
    server_type = TextField(default='micro', null=False)
    server_plan = TextField(default='10', null=False)
    server_login = TextField(default='login', null=False)
    server_password = TextField(default='password', null=False)
    server_ip = TextField(default='localhost', null=False)
    clients = IntegerField(default=0, null=False)
    
class User(BaseModel):
    user_id = TextField(unique=True)
    expire_in = DateTimeField(default=datetime.datetime.now())
    node = TextField(default='Node1')
    is_active = BooleanField(default=False)
    is_freemium = BooleanField(default=False)
    order_id = TextField(default='0')
    plan = TextField(default='10')
    trial_avalible = BooleanField(default=True)
    promo = BooleanField(default=False)
    order_type = TextField(default='shadowsocks')
    
class SS_config(BaseModel):
    cipher = TextField(default='chacha20-ietf-poly1305')
    server_ip = TextField(default='0.0.0.0')
    password = TextField(default='pass')
    port = TextField(default='8300')
    user = ForeignKeyField(User, backref='ss_config', null = True)
    is_avalible = BooleanField(default='True')

    
class Invoice(BaseModel):
    date = DateTimeField(default=datetime.datetime.now())
    currency = TextField(default='RUB')
    total_amount = IntegerField()
    invoice_payload = TextField()
    telegram_payment_charge_id = TextField()
    provider_payment_charge_id = TextField()
    user = ForeignKeyField(User, backref='invoices')
    
class Promocode(BaseModel):
    promocode = TextField(unique=True)
    is_avalible = BooleanField(default=True)
    used = IntegerField(default=0)