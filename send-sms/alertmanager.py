import json as JSON
from flask import Flask, request
from gevent.pywsgi import WSGIServer
from kavenegar import *
import re, yaml, socket, os



app = Flask(__name__)

########################################################################

def Contacts_Creator(response):
    if 'team' in response['commonLabels']:
        team = response['commonLabels']['team']
    else:
        team = 'admin'
    receptor = ''
    with open("./contacts.yml", 'r') as contact_info:
        out = yaml.load(contact_info, Loader=yaml.FullLoader)

    temp_contact_list = []
    for key, val in out.items():
        team_name = key
        key = [list(ph.values()) for ph in val]
        if team == str(team_name):
            receptor = re.sub("[\\[-\\]]", "", ','.join(str(e) for e in key))
            break
        if team == 'all' or 'ALL' or 'All':
            temp_contact_list = temp_contact_list + key
            receptor = re.sub("[\\[-\\]]", "", ','.join(str(e) for e in temp_contact_list))

    receptor = re.sub("\\'", "", receptor)
    return receptor
################################################################3

def Message_Creator(response):
    status = response['alerts'][0]['status']
    labels = response['alerts'][0]['labels']
    init_time = response['alerts'][0]['startsAt'].replace("T", " ")
    init_time = re.sub("\\..*", "", init_time)
    severity = labels['severity']
    alertname = labels['alertname']
    summary = response['alerts'][0]['annotations']['description']

    if status == "resolved":
        severity = "ok"
        init_time = response['alerts'][0]['endsAt'].replace("T", " ")
        init_time = re.sub("\\..*", "", init_time)

    message = (
            alertname +
            "\n----------------------------\n" +
            status.upper() + " -- " + "\n" +
            "***  ! " + severity.upper() + " !  ***\n" +
            init_time + "\n" +
            summary
            
    )
    return message

#####################################################

def Kavenegar_send_sms(message, receptor):
    key = 'SMS_API_KEY'
    sender = 'SENDER'
    SMS_API_KEY = os.getenv(key)
    SENDER = os.getenv(sender)
    print(f"message:\n {message}")
    try:
        api = KavenegarAPI(SMS_API_KEY)
        params = {
            'sender': SENDER,
            'receptor': receptor,
            'message': message
        }
        response = api.sms_send(params)
    except APIException as e:
        print(e)
    except HTTPException as e:
        print(e)


#############################################

@app.route('/alerting', methods=['POST'])
def webhook():
    prometheus_data = JSON.loads(request.data)
    prometheus_data_pretty = JSON.dumps(prometheus_data, indent=2)
    if prometheus_data['alerts'][0]['labels']['severity'] == "critical":    
        receptor = Contacts_Creator(prometheus_data)
        message = Message_Creator(prometheus_data)
        if 'sms_enable' in prometheus_data['commonLabels'] and prometheus_data['commonLabels']['sms_enable'] == 'true' or 'TRUE' or 'True':
            Kavenegar_send_sms(message=message, receptor=receptor)
    else:
        pass
    return prometheus_data


if __name__ == '__main__':
    hostname = socket.gethostname()
    IP = socket.gethostbyname(hostname)
    PORT = 5000
    print("Webhook is available on http://{0}:{1}/alerting\n".format(IP, PORT))
    WSGIServer(('0.0.0.0', PORT), app).serve_forever()


