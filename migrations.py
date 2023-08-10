from peewee import *
from playhouse.migrate import *
from models import User, Server, Invoice, Promocode, SS_config, db

#db = SqliteDatabase('vk.db')
#migrator = SqliteMigrator(db)
#migrator = PostgresqlMigrator(db)

#token = IntegerField(default=3)
order_type = TextField(default='shadowsocks')

with db.atomic():
    #db.create_tables([User, Server, Invoice, Promocode, SS_config])
    db.create_tables([SS_config])
    #db.create_tables([Promocode])
    migrate(
        migrator.add_column('user', 'order_type', order_type))
        
    

