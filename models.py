from peewee import *
import config
import datetime

#db = PostgresqlDatabase(config.DB_NAME, user=config.DB_USERNAME, password=config.DB_PASSWORD)
db = SqliteDatabase('vpn_bot.db')

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