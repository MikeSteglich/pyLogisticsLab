
from datetime import datetime 
import json
import smtplib
import time

import osm_data as osm


def readOptions():
    options = {}
    try:
        f = open('checkServer.opt')
        ostring = f.read()
        options = json.loads(ostring)
        f.close()
    except Exception as e:
        print(f'Error while reading option file: {e}')

    return options

def sendMail( options, mailToAdr, mailSubject, mailMessage):
    try:  
        server = smtplib.SMTP(options['smtpServer'], options['smtpPort'])
        server.starttls()
        server.login(options['mailUser'], options['mailPwd'])

        message = f"Subject: {mailSubject}\n\n{mailMessage}"

        server.sendmail(options['mailFromAdr'], mailToAdr, message)
    except Exception as e:
        print(f'Error while sending e-mail: {e}')
    finally:
        server.quit()
 

def serviceLoop(options):
    reportSent=False

    while True:
        
        conf = osm.Config()                              # confs/logisticsLab.yml
        isMainServer = conf.getConf()['isMainServer']

        for m in ['matrix', 'routing', 'geocoding']: 
            if not isMainServer[m]:
                mailSubject = f"LogisticsLab  server error for {m}"
                mailMessage = f"Server {m}, {conf.getConf()['servers']['matrix'][0]['url']} is not running "
                #sendMail(options, options['errorMailToAdr'], mailSubject, mailMessage)
                break
            

        actTime = datetime.now().strftime("%H:%M:%S")
 
        if actTime>=options['reportTime']:
            if not reportSent:
                mailSubject = f"LogisticsLab server report"
                mailMessage = ""
                for m in ['matrix', 'routing', 'geocoding']: 
                    mailMessage += f"Server {m}, {conf.getConf()['servers']['matrix'][0]['url']}: { 'running' if isMainServer[m] else 'error'}\n"
                #sendMail(options, options['reportMailToAdr'], mailSubject, mailMessage)
                reportSent=True
        else:
            reportSent=False
    
        del conf
        time.sleep(options['serviceIntervall'])



opts = readOptions()   
serviceLoop(opts)


