import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders
import os

failed = [
    "FME's FME_EUR_AuditTrail_ft4asx1_GHFE1_20180806_All: Unable to encrypt: invalid recipient",
    "RJO's FME_ASX_AuditTrail_ft4asx2_GHFE2_20180806_All: Unable to encrypt: invalid recipient",
    "FME's FME_ASX_AuditTrail_ft4asx3_GHFE3_20180805: Requested files not found on the remote server"
]


def sendMail(to, fro, subject, text, files=[],server="localhost"):
    assert type(to)==list
    assert type(files)==list

    textmsg = ''
    for servers in text:
        textmsg += server

    msg = MIMEMultipart()
    msg['From'] = fro
    msg['To'] = COMMASPACE.join(to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject

    msg.attach(MIMEText(textmsg))

    for file in files:
        part = MIMEBase('application', "octet-stream")
        part.set_payload( open(file,"rb").read() )
        Encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"'
                       % os.path.basename(file))
        msg.attach(part)

    smtp = smtplib.SMTP(server)
    smtp.sendmail(fro, to, msg.as_string() )
    smtp.close()


# Example:
sendMail(['amcfarlane@tradevela.com'],'AuditReport@PaaSMgtVM.com','PaaSMgtVM Audit Report', failed)
