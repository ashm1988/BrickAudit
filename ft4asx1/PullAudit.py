import logging
import optparse
import datetime
import os
import re
import subprocess
import shutil
import zipfile
import pysftp
import paramiko
import time
import stat


logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.DEBUG)

sftp_host = '10.234.100.30'
# For zip sftp #####
fdate = 'today'
audit_loc = r'/home/ot'
tmp_loc = '/home/ot/audits'
####################
# for this script ##
sftp_script = 'zip_audits.py'
sftp_script_loc = r'/opt/ot/scripts/zip_audits.py'
scripts_loc = '/opt/ot/scripts'
client_zip_location = r'C:\Users\amcfarlane\Documents\temp'
# A2C_loc = '/opt/ot/scripts/AuditToCsv'
A2C_loc = r'"C:\Users\amcfarlane\Documents\Object Trading\FR Admin Tools 4.1.3.9 Windows x64\AuditToCsv"'
####################


class ZipFiles(object):
    # def __init__(self):
    #     self.ssh = paramiko.SSHClient()
    #     self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    #     self.ssh.connect(sftp_host, username='root', key_filename=r'C:\cygwin64\home\amcfarlane\.ssh\id_rsa', port=22)
    #     self.sftp = self.ssh.open_sftp()

    def push_zip_script(self, uid):
        if sftp_script not in self.sftp.listdir(scripts_loc):
            logging.debug('push zip: Pushing zip_audits script to server')
            self.sftp.put(sftp_script, sftp_script_loc)

        self.sftp.chmod(sftp_script_loc, 0755)
        self.sftp.chown(sftp_script_loc, 0, int(uid))

    def run_zipit(self):
        stdin, stdout, stderr = self.ssh.exec_command('id -u ot')
        uid = stdout.read()
        self.push_zip_script(uid)
        stdin, stdout, stderr = self.ssh.exec_command('sudo python %s -d %s -t %s -a %s'
                                                      % (sftp_script_loc, fdate, tmp_loc, audit_loc))
        logging.error(stderr.read())
        logging.info(stdout.read())

        self.pull_audits()

    def pull_audits(self):
        new_zip = self.sftp.listdir(tmp_loc)
        for z in new_zip:
            logging.info('pull audits: Pulling %s back to %s', z, client_zip_location)
            self.sftp.get(tmp_loc + '/%s' % z, client_zip_location + '/%s' % z)

        self.unzip()

    def unzip(self):
        for z in os.listdir(client_zip_location):
            if z.endswith('.zip'):
                zf = zipfile.ZipFile(os.path.join(client_zip_location, z), 'r')
                zf.extractall(client_zip_location)


class DecodeAudits(object):
    def __init__(self):
        pass

    def decode(self):
        for f in os.listdir(client_zip_location):
            output_name = f[:-4]
            if re.search('Audit.*.log', f):
                result = subprocess.call(os.path.join(A2C_loc, 'Versions', '2.9', 'AuditToCSV.exe --override -i') +
                                         os.path.join(client_zip_location, f) +
                                         ' -o' + os.path.join(client_zip_location, '%s.csv' % output_name), shell=True)
                # print result

    def decode_audit(self, decode, date):
        """Decodes Audits passed from the Audit finders"""
        to_zip = []
        for audit in decode:
            if not os.path.exists(client_zip_location):
                os.makedirs(client_zip_location)
            output_name = audit[:-4]
            shutil.copy2(os.path.join(audit_path, audit), client_zip_location)
            result = subprocess.call(os.path.join(os.path.dirname(audit_path), AuditToCSV + ' --override -i') +
                                     os.path.join(client_zip_location, audit) + ' -o' +
                                     os.path.join(client_zip_location, '%s.csv' % output_name), shell=True)
            if result == 0:
                logging.debug("Decode Audits: %s decoded" % audit)

        files = os.listdir(client_zip_location)
        for file in files:
            to_zip.append(os.path.join(client_zip_location, file))

        # zip_audits(date, to_zip)


def main():
    # audit = PullAudit()
    # audit.pull_audit()
    # audit.directorycheck()
    zipaud = ZipFiles()
    # zipaud.run_zipit()
    # zipaud.unzip()
    decode = DecodeAudits()
    decode.decode()

if __name__ == '__main__':
    main()