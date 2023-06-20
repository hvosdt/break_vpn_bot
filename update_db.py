from models import User, Server

server, is_new = Server.get_or_create(
    order_id = '115046'
)

server.server_login = 'root'
server.server_password = 'rQpC90BWgI2V'
server.server_ip = '91.215.152.218'
clients = 1
server.save()

print(server.server_login)
print(server.server_password)
print(server.server_ip)

