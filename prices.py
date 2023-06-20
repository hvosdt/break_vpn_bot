from aiogram import types

MARAPHON = types.LabeledPrice(
    label = 'Марафон Больше чем селфи',
    amount = 590*100
)

VPN30 = types.LabeledPrice(
    label = 'Подписка на VPN (1 месяц)',
    amount = 200*100
)

VPN90 = types.LabeledPrice(
    label = 'Подписка на VPN (3 месяц)',
    amount = 540*100
)

VPN180 = types.LabeledPrice(
    label = 'Подписка на VPN (6 месяц)',
    amount = 960*100
)
