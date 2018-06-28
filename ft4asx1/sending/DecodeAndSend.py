import logging
import optparse
import datetime
import os
import re
import subprocess
import shutil
import zipfile
import pysftp

logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.DEBUG)
# yesterday = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y%m%d")  # current_date = 20180501
# today = datetime.date.today().strftime("%Y%m%d")  # current_date = 20180501
today = 20180501
logging.debug("current date %s", today)

#############################################################################################################
#  Script: Pulls the Audits from the server and decodes them                                                #
#  Version: 1.0                                                                                             #
#  Author: Ash                                                                                              #
#############################################################################################################

#############################################################################################################
#  Changeable parameters below                                                                              #
#############################################################################################################
fr_install = r'C:\Users\amcfarlane\Documents\Scripts\python\BrickAudit'  # normally /opt/ot/ft4asx1
audit_directory = r'ft4asx1\releases\fronttradeasx_4_1_2_18-4_1_2_5_rhel6_x64\LogFiles'  # normally current/LogFiles
audit_pattern = r'Audit.*.log'
csv_directory = os.path.join(fr_install, audit_directory, 'audit_csv')
client_name = 'ClientName'
exchange = 'CME'
session_ID = 'sessionID'
sftp_host = '192.168.105.99'
sftp_home = '/home/ashtest'
#############################################################################################################

#  Find Audit location
audit_path = os.path.join(fr_install, audit_directory)
logging.debug(audit_path)
if os.name == 'nt':
    AuditToCSV = 'AuditToCsv.exe'
else:
    AuditToCSV = 'AuditToCsv'


def run_date(date):
    """Gets audit by date and passes it to decode_audit"""
    audit = ["Audit.%s.log" % date]
    decode_audit(audit, date)


def run_against_all():
    """Runs the decode Audit against all Audit logs in the logfiles directory"""
    to_decode = []
    files = os.listdir(audit_path)
    logging.debug("Run for all: Available files: %s", files)
    for audit in files:
        if re.search(audit_pattern, audit):
            to_decode.append(audit)

    logging.debug("Run for all: passing %s", to_decode)
    decode_audit(to_decode, "All_%s" % today)


def decode_audit(decode, date):
    """Decodes Audits passed from the Audit finders"""
    to_zip = []
    for audit in decode:
        if not os.path.exists(csv_directory):
            os.makedirs(csv_directory)
        output_name = audit[:-4]
        shutil.copy2(os.path.join(audit_path, audit), csv_directory)
        result = subprocess.call(os.path.join(os.path.dirname(audit_path), AuditToCSV + ' --override -i') +
                                 os.path.join(csv_directory, audit) + ' -o' +
                                 os.path.join(csv_directory, '%s.csv' % output_name), shell=True)
        if result == 0:
            logging.debug("Decode Audits: %s decoded" % audit)

    files = os.listdir(csv_directory)
    for file in files:
        to_zip.append(os.path.join(csv_directory, file))

    zip_audits(date, to_zip)
    # test(to_zip)


def zip_audits(date, files):
    output_name = '%s_%s_AuditTrail_%s_%s.zip' % (client_name, exchange, session_ID, date)
    zf = zipfile.ZipFile(os.path.join(csv_directory, output_name), mode='a')

    for file in files:
        if not file.endswith('.zip'):
            zf.write(file, os.path.basename(file), compress_type=zipfile.ZIP_DEFLATED)
            logging.info("Zipfile: Adding %s to %s", os.path.basename(file), os.path.basename(output_name))
            os.remove(file)
            logging.info("Zipfile: Deleting %s from %s", os.path.basename(file), os.path.basename(output_name))

    zf.close()
    sftp_to_edge(os.path.join(csv_directory, output_name))


def sftp_to_edge(filename):
    """Send files to the edge sftp server"""
    srv = pysftp.Connection(host=sftp_host, username='root', password='0tsupp0rt')
    with srv.cd(sftp_home):
        srv.put(filename)
        data = srv.listdir()
        print data
    srv.close()


def main():

    if os.path.exists(audit_path):
        run_against_all()
        # run_date(today)
    else:
        logging.warning("Main: %s does not exist", audit_path)
    # sftp_to_edge()


if __name__ == '__main__':
    main()
