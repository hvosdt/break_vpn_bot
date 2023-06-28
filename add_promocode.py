from models import *

prompt = input('Введи промокод: ')
promocode, is_new = Promocode.get_or_create(
    promocode = prompt.lower()
)
promocode.save()

promos = Promocode.select()
for promo in promos:
    print(promo.promocode)
    