import logging
import argparse
import datetime
import os
import re
import subprocess
import shutil
import zipfile
logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.DEBUG)
# yesterday = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y%m%d")  # current_date = 20180501
# today = datetime.date.today().strftime("%Y%m%d")  # current_date = 20180501
today = 20180501
logging.debug("current date %s", today)

#############################################################################################################
#  Script: Decodes the Audit logs and send them to the Edge Server                                          #
#  Version: 1.0                                                                                             #
#  Author: Ash                                                                                              #
#############################################################################################################

#############################################################################################################
#  Changeable parameters below                                                                              #
#############################################################################################################
fr_install = r'C:\Users\amcfarlane\Documents\Scripts\python\BrickAudit'  # normally /opt/ot
audit_directory = r'ft4asx1\releases\fronttradeasx_4_1_2_18-4_1_2_5_rhel6_x64\LogFiles'  # normally ft4asx1/current
audit_pattern = r'Audit.*.log'
csv_directory = os.path.join(fr_install, audit_directory, 'audit_csv')
#############################################################################################################

#  Find Audit location
audit_path = os.path.join(fr_install, audit_directory)
logging.debug(audit_path)


def run_date(date):
    """Gets audit by date and passes it to decode_audit"""
    audit = "Audit.%s.log" % date
    decode_audit(audit)


def run_against_all():
    """Runs the decode Audit against all Audit logs in the logfiles directory"""
    files = os.listdir(audit_path)
    logging.debug("Available files: %s", files)
    for audit in files:
        if re.search(audit_pattern, audit):
            decode_audit(audit)


def decode_audit(audit):
    """Decodes Audits passed from the Audit finders"""
    if not os.path.exists(csv_directory):
        os.makedirs(csv_directory)
    output_name = audit[:-4]
    shutil.copy2(os.path.join(audit_path, audit), csv_directory)
    result = subprocess.call(os.path.join(os.path.dirname(audit_path), 'AuditToCsv.exe --override -i') +
                             os.path.join(csv_directory, audit) + ' -o' +
                             os.path.join(csv_directory, '%s.csv' % output_name), shell=True)
    if result == 0:
        logging.debug("%s decoded" % audit)


def zip_audits():
    zf = zipfile.ZipFile(os.path.join(csv_directory, 'audit.zip'), mode='a')
    files = os.listdir(csv_directory)
    print files
    for file in files:
        print os.path.join(csv_directory, file)
        # zf.write(os.path.join(csv_directory, file))
    zf.close()



def main():

    if os.path.exists(audit_path):
        run_against_all()
        # run_date(today)
        zip_audits()
    else:
        logging.warning("%s does not exist", audit_path)


if __name__ == '__main__':
    main()