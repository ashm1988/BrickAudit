#!/usr/bin/python

__version__ = '1.0'

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
sftp_script = 'zip_audits.py'  # Name of SFTP Script
scripts_loc = '/opt/ot/scripts'  # Where on the remote server to put the Script
sftp_script_loc = r'/opt/ot/scripts/zip_audits.py'  # Lazy location naming for the script to run on the remote server
client_zip_location = r'C:\Users\amcfarlane\Documents\temp\audits'  # Base location of where to save/process the audits
# A2C_loc = '/opt/ot/scripts/AuditToCsv'
A2C_loc = r'C:\Users\amcfarlane\Documents'  # location of the FR Admin Tools
####################


class ZipFiles(object):
    def __init__(self, instance, tmp_loc):
        # Set date for the zip name
        if instance['Date'] == 'today':
            fdate = datetime.date.today().strftime("%Y%m%d")
        elif instance['Date'] == 'yesterday':
            fdate = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
        elif instance['Date'] == 'all':
            fdate = datetime.date.today().strftime("%Y%m%d")+'_All'

        # Set zippath/zipname and instance vars
        self.instance = instance
        self.zip_path = os.path.join(client_zip_location, self.instance['Recipient'], self.instance['Exchange'], self.instance['Instance'], 'Processing')
        self.log_path = os.path.join(self.zip_path, '../', 'Logs')
        self.archive_path = os.path.join(self.zip_path, '../', 'Archive')
        self.zip_name = '%s_%s_AuditTrail_%s_%s_%s.zip' % (self.instance['Client'], self.instance['Exchange'], self.instance['Instance'], self.instance['SessionID'], fdate)

        # Create directory's
        if not os.path.exists(self.zip_path):
            logging.info('Creating %s, %s and %s', self.zip_path, self.log_path, self.archive_path)
            # Processing
            os.makedirs(self.zip_path)
            # Logs
            os.makedirs(self.log_path)
            # Archive
            os.makedirs(self.archive_path)

        # Get logger for the individual instance
        fh = logging.FileHandler(os.path.join(self.log_path, self.zip_name[:-4]+'.log'))
        fh.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(message)s')
        fh.setFormatter(formatter)
        logging.getLogger('').addHandler(fh)

        self.fdate = instance['Date']
        self.tmp_loc = tmp_loc
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
        logging.info('Pushing zip_audits script to %s', self.instance['Host'])
        self.sftp.put(sftp_script, sftp_script_loc)

        # Change the script permissions and owner so it can be run
        logging.info('Changing SFTP Script permissions')
        self.sftp.chmod(sftp_script_loc, 0755)
        self.sftp.chown(sftp_script_loc, 0, int(uid))

    def run_zipit(self):
        """
        Runs the zip_audit script with the credentials taken from the JSON config file
        """
        # Get the UID of the ot user to set in the push_zip_script()
        stdin, stdout, stderr = self.ssh.exec_command('id -u ot')
        uid = stdout.read()
        # Run the push_zip_script
        self.push_zip_script(uid)
        # run the sftp script
        logging.info('Running SFTP Script on remote server')
        stdin, stdout, stderr = self.ssh.exec_command('sudo python %s -d %s -t %s -a %s'
                                                      % (sftp_script_loc, self.fdate, self.tmp_loc, self.audit_loc))

        logging.info(stderr.read())
        # logging.info(stdout.read())
        # for l in stderr:
        #     stderrout = l
        #     print l
        #     if re.search(r'could not be found', l) or re.search(r'could not be found', l):
        #         sys.exit()

        # Run pull audits
        self.pull_audits()

    def pull_audits(self):
        """
        Pulls the zipped up audits back from the server and places it in the relevant directory
        """
        # Pull back the created zips in their respective folders
        new_zip = self.sftp.listdir(self.tmp_loc)
        if not new_zip:
            logging.error('Files files to pull back')
            sys.exit()
        else:
            for z in new_zip:
                logging.info('Pulling %s back to %s', self.zip_name, self.zip_path)
                self.sftp.get(os.path.join(self.tmp_loc, z).replace('\\', '/'), os.path.join(self.zip_path, self.zip_name))

            # Tidy up old zips and directory on remote server
            for z in new_zip:
                logging.debug('pull audits: Deleting %s', z)
                self.sftp.remove(os.path.join(self.tmp_loc, z).replace('\\', '/'))
            logging.debug('pull audits: Deleting %s', self.tmp_loc)
            self.sftp.rmdir(self.tmp_loc)

            # Run upzip()
            self.unzip()

    def unzip(self):
        """
        Unzips the received audits and deletes the old zip file
        """
        # Unzip the files in their relevant directory
        for z in os.listdir(self.zip_path):
            if z.endswith('.zip'):
                logging.info("Unzipping %s to %s", z, self.zip_path)
                zf = zipfile.ZipFile(os.path.join(self.zip_path, z), 'r')
                zf.extractall(self.zip_path)
                zf.close()

        # Delete the zip folder after it hsa been pulled back
        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                logging.info('Deleting %s', os.path.join(self.zip_path, f))
                os.remove(os.path.join(self.zip_path, f))


class DecodeAudits(object):
    def __init__(self, zipaud):
        self.zip_name = zipaud.zip_name
        self.zip_path = zipaud.zip_path
        if sys.platform == 'linux' or sys.platform == 'linux2':
            self.Audit2csv = 'AuditToCSV'
        else:
            self.Audit2csv = 'AuditToCSV.exe'

    def decode(self):
        for f in os.listdir(self.zip_path):
            if re.search('Audit.*.log', f):
                output_name = f[:-4]
                logging.info('Decoding %s', os.path.join(self.zip_path, f))
                result = subprocess.call(os.path.join(A2C_loc, self.Audit2csv + ' --override -a ' +
                                                      os.path.join(A2C_loc, 'Versions') + ' -i ') +
                                         os.path.join(self.zip_path, f) +
                                         ' -o ' + os.path.join(self.zip_path, '%s.csv' % output_name), shell=True)
                if result == 0:
                    logging.info("%s decoded", f)
                else:
                    logging.error('%s failed to decode: %s', f, result)

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
        self.recipient = zipaud.instance['Recipient']
        self.gpgbin = r'C:\Program Files (x86)\GnuPG\bin\gpg.exe'
        self.gpghome = r'C:\Users\amcfarlane\AppData\Roaming\gnupg'

    def encrypt(self):
        gpg = gnupg.GPG(gpgbinary=self.gpgbin, gnupghome=self.gpghome)
        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                logging.info('Encrypting %s', f)
                output_name = f+'.gpg'
                stream = open(os.path.join(self.zip_path, f), 'rb')
                result = gpg.encrypt_file(stream, 'Client '+self.recipient, output=os.path.join(self.zip_path, output_name))
                if not result.ok:
                    logging.error('%s failed to encrypt: %s', f, result.status)
                else:
                    logging.info('%s encrypted successfully', output_name)


class BrickFTP(object):
    def __init__(self, zipaud):
        logging.info('Connecting to Brick')
        self.enc_loc = zipaud.instance['Recipient']
        self.zip_path = zipaud.zip_path
        self.archive_path = zipaud.archive_path
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect('paas.brickftp.com', username='a.mcfarlane', key_filename=r'C:\cygwin64\home\amcfarlane\.ssh\id_rsa', port=22)
        self.sftp = self.ssh.open_sftp()


    def push_to_brick(self):
        enc_files = os.listdir(self.zip_path)
        # Push the gpg to Brick
        for f in enc_files:
            if f.endswith('.gpg'):
                logging.info('Pushing %s to %s on the Brick server', f, self.enc_loc)
                self.sftp.put(os.path.join(self.zip_path, f), os.path.join(self.enc_loc, f))

        # Copy zip to Archive
        for f in enc_files:
            if f.endswith('.zip'):
                logging.info('Archive %s to %s', f, self.archive_path)
                shutil.move(os.path.join(self.zip_path, f), os.path.join(self.archive_path, f))

        # Delete the uploaded gpg
        for f in enc_files:
            if f.endswith('.gpg'):
                os.remove(os.path.join(self.zip_path, f))


def main():
    # Set logging
    logging.basicConfig(format='%(asctime)s: %(levelname)s: %(funcName)s: %(message)s', level=logging.INFO)
    fh = logging.FileHandler('filehandler.log')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(message)s')
    fh.setFormatter(formatter)
    logging.getLogger('').addHandler(fh)

    complete = 0
    failed = 0

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
            # Set date for the zip name
            if instance['Date'] == 'today':
                fdate = datetime.date.today().strftime("%Y%m%d")
            elif instance['Date'] == 'yesterday':
                fdate = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
            elif instance['Date'] == 'all':
                fdate = datetime.date.today().strftime("%Y%m%d") + '_All'

            try:
                logging.info("Trying %s's %s_%s_AuditTrail_%s_%s_%s", instance['Recipient'], instance['Client'],
                             instance['Exchange'], instance['Instance'], instance['SessionID'], fdate)
                zipaud = ZipFiles(instance, tmp_loc)
                zipaud.run_zipit()
                decode = DecodeAudits(zipaud)
                decode.decode()
                encrypt = EncryptZIPs(zipaud)
                encrypt.encrypt()
                brick = BrickFTP(zipaud)
                brick.push_to_brick()
                complete += 1
            except:
                logging.error("%s 's %s_%s_AuditTrail_%s_%s_%s Failed to complete", instance['Recipient'],
                              instance['Client'], instance['Exchange'], instance['Instance'], instance['SessionID'],
                              fdate)
                failed += 1

    logging.info('%s Completed\n'
                 '%s Failed', complete, failed)

if __name__ == '__main__':
    main()
