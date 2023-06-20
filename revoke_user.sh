if [[ -e /etc/debian_version ]]; then
	os="debian"
	group_name="nogroup"
elif [[ -e /etc/centos-release || -e /etc/redhat-release ]]; then
	os="centos"
	group_name="nobody"
else
	echo "Looks like you aren't running this installer on Debian, Ubuntu or CentOS"
	exit
fi


cd /etc/openvpn/server/easy-rsa/
./easyrsa --batch revoke "$1"
EASYRSA_CRL_DAYS=3650 ./easyrsa gen-crl
rm -f pki/reqs/"$1".req
rm -f pki/private/"$1".key
rm -f pki/issued/"$1".crt
rm -f /etc/openvpn/server/crl.pem
cp /etc/openvpn/server/easy-rsa/pki/crl.pem /etc/openvpn/server/crl.pem
# CRL is read with each client connection, when OpenVPN is dropped to nobody
chown nobody:"$group_name" /etc/openvpn/server/crl.pem