import config
import paramiko
from vds_api import get_balance, get_orders, create_order

ip = '193.104.57.130'
login = 'root'
password = 'Z84seCQ3Bi'

def ssh_conect_to_server(server_ip, login, password):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(server_ip, '22', login, password)
    return ssh_client  

ssh_client = ssh_conect_to_server(user.server.server_ip, user.server_login, user.server_password)
command = './revoke_user.sh {name}'.format(name=user.user_id)
stdin, stdout, stderr = ssh_client.exec_command(command)
mes = 'Ваша подписка прекращена. Для возобновления работы, нажмите /start и купите новую подписку.'
send_msg(user.user_id, mes)  

#order = create_order()
#ssh_client = ssh_conect_to_server(ip, login, password)
#with ssh_client.open_sftp() as sftp:
#        sftp.put('add_user.sh','add_user.sh')
#stdin, stdout, stderr = ssh_client.exec_command('chmod +x add_user.sh')
orders = get_orders()
print(str(orders))
    

    


