from peewee import *
from playhouse.migrate import *
from models import User, Server, db

#db = SqliteDatabase('vk.db')
#migrator = SqliteMigrator(db)
#migrator = PostgresqlMigrator(db)

#token = IntegerField(default=3)

with db.atomic():
    db.drop_tables([User, Server])
    db.create_tables([Server, User])
    #migrate(
    #    migrator.add_column('user', 'target_sex', token))

