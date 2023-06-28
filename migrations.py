from peewee import *
from playhouse.migrate import *
from models import User, Server, Invoice, Promocode, db

#db = SqliteDatabase('vk.db')
#migrator = SqliteMigrator(db)
migrator = PostgresqlMigrator(db)

#token = IntegerField(default=3)
trial_avalible = BooleanField(default=True)
promo = BooleanField(default=False)

with db.atomic():
    #db.drop_tables([User, Server, Invoice, Promocode])
    db.create_tables([Promocode])
    #db.create_tables([Promocode])
    migrate(
        migrator.add_column('user', 'trial_avalible', trial_avalible))
    migrate(
        migrator.add_column('user', 'promo', promo))
    

