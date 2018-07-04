import sys
import logging
import datetime
import os
import re
import subprocess
import shutil
import zipfile
import paramiko
import json
import gnupg

#  Logging
# logging.basicConfig(format='%(asctime)s: %(levelname)s: %(funcName)s: %(message)s', level=logging.DEBUG)
# fh = logging.FileHandler('filehandler.log')
# fh.setLevel(logging.DEBUG)
# formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(message)s')
# fh.setFormatter(formatter)
# logging.getLogger('').addHandler(fh)

####################
# for this script ##
sftp_script = 'zip_audits.py'
scripts_loc = '/opt/ot/scripts'
client_zip_location = r'C:\Users\amcfarlane\Documents\temp\audits'
# A2C_loc = '/opt/ot/scripts/AuditToCsv'
A2C_loc = r'C:\Users\amcfarlane\Documents'
####################

sftp_script_loc = r'/opt/ot/scripts/zip_audits.py'


class ZipFiles(object):
    def __init__(self, instance, tmp_loc):
        self.instance = instance
        self.fdate = instance['Date']
        self.tmp_loc = tmp_loc
        self.zip_path = os.path.join(client_zip_location, self.instance['Client'], self.instance['Exchange'], self.instance['Instance'])
        self.zip_name = '%s_%s_AuditTrail_%s_%s.zip' % (self.instance['Client'], self.instance['Exchange'], self.instance['Instance'], self.instance['SessionID'])
        self.audit_loc = instance['Audit_Location']
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(instance['Host'], username='root', key_filename=r'C:\cygwin64\home\amcfarlane\.ssh\id_rsa', port=22)
        self.sftp = self.ssh.open_sftp()

    def push_zip_script(self, uid):
        """
        Push the zip_audits script to the server if it don't already exist
        :param uid: uid for the ot user on the server
        :return:
        """

        # Push the scrip to the server
        # if sftp_script not in self.sftp.listdir(scripts_loc):
        logging.debug('push zip: Pushing zip_audits script to %s', self.instance['Host'])
        self.sftp.put(sftp_script, sftp_script_loc)

        # Change the script permissions and owner so it can be run
        self.sftp.chmod(sftp_script_loc, 0755)
        self.sftp.chown(sftp_script_loc, 0, int(uid))

    def run_zipit(self):
        """
        Runs the zip_audit script with the credentials taken from the JSON config file
        """
        stdin, stdout, stderr = self.ssh.exec_command('id -u ot')
        uid = stdout.read()
        self.push_zip_script(uid)
        stdin, stdout, stderr = self.ssh.exec_command('sudo python %s -d %s -t %s -a %s'
                                                      % (sftp_script_loc, self.fdate, self.tmp_loc, self.audit_loc))
        logging.info(stderr.read())
        logging.info(stdout.read())

        self.pull_audits()

    def pull_audits(self):
        """
        Pulls the zipped up audits back from the server and places it in the relevant directory
        """
        new_zip = self.sftp.listdir(self.tmp_loc)
        if not os.path.exists(self.zip_path):
            os.makedirs(self.zip_path)
        for z in new_zip:
            logging.info('pull audits: Pulling %s back to %s', self.zip_name, self.zip_path)
            self.sftp.get(os.path.join(self.tmp_loc, z).replace('\\', '/'), os.path.join(self.zip_path, self.zip_name))

        # Tidy up old zips and directory
        for zip in new_zip:
            logging.debug('pull audits: Deleting %s', zip)
            self.sftp.remove(os.path.join(self.tmp_loc, zip).replace('\\', '/'))
        logging.debug('pull audits: Deleting %s', self.tmp_loc)
        self.sftp.rmdir(self.tmp_loc)

        self.unzip()

    def unzip(self):
        """
        Unzips the received audits
        :return:
        """
        for z in os.listdir(self.zip_path):
            if z.endswith('.zip'):
                logging.debug("unzip: Unzipping %s", z)
                zf = zipfile.ZipFile(os.path.join(self.zip_path, z), 'r')
                zf.extractall(self.zip_path)
                zf.close()

        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                os.remove(os.path.join(self.zip_path, f))


class DecodeAudits(object):
    def __init__(self, zipfile):
        self.zip_name = zipfile.zip_name
        self.zip_path = zipfile.zip_path

    def decode(self):
        for f in os.listdir(self.zip_path):
            if re.search('Audit.*.log', f):
                output_name = f[:-4]
                logging.debug('decode: Decoding %s', f)
                result = subprocess.call(os.path.join(A2C_loc, 'AuditToCSV.exe --override -a ' +
                                                      os.path.join(A2C_loc, 'Versions') + ' -i ') +
                                         os.path.join(self.zip_path, f) +
                                         ' -o ' + os.path.join(self.zip_path, '%s.csv' % output_name), shell=True)
                if result == 0:
                    logging.debug("Decode Audits: %s decoded" % f)

        self.zip_decoded()

    def zip_decoded(self):

        if os.listdir(self.zip_path):
            zf = zipfile.ZipFile(os.path.join(self.zip_path, self.zip_name), mode='w')
            for f in os.listdir(self.zip_path):
                if not f.endswith('.zip'):
                    zf.write(os.path.join(self.zip_path, f), f, compress_type=zipfile.ZIP_DEFLATED)

            zf.close()

        # Delete the left over files
        for f in os.listdir(self.zip_path):
            if not f.endswith('.zip'):
                os.remove(os.path.join(self.zip_path, f))


class EncryptZIPs(object):
    def __init__(self, zipaud):
        self.zip_path = zipaud.zip_path
        self.client = zipaud.instance['Client']
        self.gpgbin = r'C:\Program Files (x86)\GnuPG\bin\gpg.exe'
        self.gpghome = r'C:\Users\amcfarlane\AppData\Roaming\gnupg'

    def encrypt(self):
        gpg = gnupg.GPG(gpgbinary=self.gpgbin, gnupghome=self.gpghome)
        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                output_name = f+'.gpg'
                stream = open(os.path.join(self.zip_path, f), 'rb')
                result = gpg.encrypt_file(stream, 'Client '+self.client, output=os.path.join(self.zip_path, output_name))
                if not result.ok:
                    logging.error('encrypt: %s failed to encrypt: %s', f, result.status)
                else:
                    logging.info('encrypt: %s encrypted successfully', output_name)


def main():
    logging.basicConfig(format='%(asctime)s: %(levelname)s: %(funcName)s: %(message)s', level=logging.DEBUG)
    fh = logging.FileHandler('filehandler.log')
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(message)s')
    fh.setFormatter(formatter)
    logging.getLogger('').addHandler(fh)

    config_file = 'jsontest.json'
    tmp_loc = '/home/ot/audits'
    try:
        parsed_json = json.loads(open(config_file).read())
    except ValueError as err:
        logging.error('Syntax error in %s', config_file)
        sys.exit()
    except IOError as err:
        logging.error('Cannot find %s', config_file)
        sys.exit()

    for host in parsed_json.values():
        for instance in host:
            zipaud = ZipFiles(instance, tmp_loc)
            zipaud.run_zipit()
            decode = DecodeAudits(zipaud)
            decode.decode()
            encrypt = EncryptZIPs(zipaud)
            encrypt.encrypt()


if __name__ == '__main__':
    main()
