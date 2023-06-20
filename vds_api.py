import requests
import paramiko
import config
from models import Server

def ssh_conect_to_server(server_ip, login, password):
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(server_ip, '3333', login, password)
    return ssh_client    


def get_balance():
    response = requests.get(
        '{api_uri}command={command}&login={api_login}&pass={api_pass}&json=1'.format(
        command = 'getBalance',
        api_uri = config.VDS_API_URL, 
        api_login = config.VDS_API_LOGIN,
        api_pass = config.VDS_API_PASSWORD)).json()
    return response

def get_orders():
    response = requests.get(
        '{api_uri}command={command}&login={api_login}&pass={api_pass}&json=1'.format(
        command = 'getOrders',
        api_uri = config.VDS_API_URL, 
        api_login = config.VDS_API_LOGIN,
        api_pass = config.VDS_API_PASSWORD)).json()
    return response

def create_order():
    response = requests.get(
        '{api_uri}command={command}&login={api_login}&pass={api_pass}&json=1&tarifid={tarifid}&period={period}&addons={addons}&locationid=104&remark=Node2'.format(
        command = 'createOrder',
        api_uri = config.VDS_API_URL, 
        api_login = config.VDS_API_LOGIN,
        api_pass = config.VDS_API_PASSWORD,
        tarifid='193',
        period='1',
        addons='119,98')
        ).json()
    new_server = {
        'orderid': str(response['orderid']),
        'serverlogin': str(response['serverlogin']),
        'serverpassword': str(response['serverpassword']),
        'serverip': 'localhost'}
    orders = get_orders()  
    for order in orders['orders']:
        if order['orderid'] == new_server['orderid']:
            new_server['serverip'] = str(order['serverip'])  
    server, is_new = Server.get_or_create(
        order_id = new_server['orderid'],
        server_login = new_server['serverlogin'],
        server_password = new_server['serverpassword'],
        server_ip = new_server['serverip']
    )
    ssh_client = ssh_conect_to_server(new_server['serverip'], new_server['serverlogin'], new_server['serverpassword'])
    with ssh_client.open_sftp() as sftp:
        sftp.put('add_user.sh','add_user.sh')
        sftp.put('revoke_user.sh','revoke_user.sh')
    stdin, stdout, stderr = ssh_client.exec_command('chmod +x add_user.sh')
    stdin, stdout, stderr = ssh_client.exec_command('chmod +x revoke_user.sh')
    return new_server


def get_tarifs():
    response = requests.get(
        '{api_uri}command={command}&login={api_login}&pass={api_pass}&json=1'.format(
        command = 'getTarifs',
        api_uri = config.VDS_API_URL, 
        api_login = config.VDS_API_LOGIN,
        api_pass = config.VDS_API_PASSWORD)).json()
    return response


