#!/usr/bin/python

__version__ = '1.1'

import sys
import logging
import datetime
import os
import re
import subprocess
import zipfile
import paramiko
import json
import gnupg
import pysftp
import smtplib
import argparse
from socket import gethostname
from email.MIMEMultipart import MIMEMultipart
from email.MIMEBase import MIMEBase
from email.MIMEText import MIMEText
from email.Utils import COMMASPACE, formatdate
from email import Encoders

####################
# for this script ##
current_dir = os.path.dirname(os.path.abspath(__file__))
sftp_script = 'zip_audits.py'  # Name of SFTP Script
scripts_loc = '/opt/ot/scripts'  # Where on the remote server to put the Script
sftp_script_loc = r'/opt/ot/scripts/zip_audits.py'  # Lazy location naming for the script to run on the remote server
client_zip_location = r'C:\Users\amcfarlane\Documents\temp\audits'  # Base location of where to save/process the audits
A2C_loc = r'C:\Users\amcfarlane\Documents'  # location of the FR Admin Tools
ssh_key_loc = r'C:\cygwin64\home\amcfarlane\.ssh'  # ssh key location
gpg_loc = r'C:\Program Files (x86)\GnuPG\bin\gpg.exe'
gpg_home = r'C:\Users\amcfarlane\AppData\Roaming\gnupg'
####################


class ZipFiles(object):
    def __init__(self, instance, tmp_loc, fdate):
        # Set date for the zip name
        fdate = fdate

        # Set zippath/zipname and instance vars
        self.instance = instance
        self.zip_path = os.path.join(client_zip_location, self.instance['Recipient'], self.instance['Exchange'],
                                     self.instance['Instance'], 'Processing')
        self.log_path = os.path.join(self.zip_path, '../', 'Logs')
        # Currently not used as not archiving on the internal server
        self.archive_path = os.path.join(self.zip_path, '../', 'Archive')
        self.zip_name = '%s_%s_AuditTrail_%s_%s_%s.zip' % (self.instance['Client'],
                                                           self.instance['Exchange'], self.instance['Instance'],
                                                           self.instance['SessionID'], fdate)

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
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(message)s')
        fh.setFormatter(formatter)
        logging.getLogger('').addHandler(fh)

        self.fdate = instance['Date'].lower()
        self.tmp_loc = tmp_loc
        self.audit_loc = instance['Audit_Location']
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect(instance['Host'], username='root', key_filename=os.path.join(ssh_key_loc, 'id_rsa'), port=22)
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
        self.sftp.put(os.path.join(current_dir, sftp_script), sftp_script_loc)

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

        # Run pull audits
        self.pull_audits()

    def pull_audits(self):
        """
        Pulls the zipped up audits back from the server and places it in the relevant directory
        """
        # Pull back the created zips in their respective folders
        new_zip = self.sftp.listdir(self.tmp_loc)
        if not new_zip:
            # logging.error('No files to pull back')
            raise Exception('Requested files not found on the remote server')
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
        self.instance = zipaud.instance
        self.zip_name = zipaud.zip_name
        self.zip_path = zipaud.zip_path
        if sys.platform == 'linux' or sys.platform == 'linux2':
            self.Audit2csv = 'AuditToCsv'
        else:
            self.Audit2csv = 'AuditToCsv.exe'

    def get_mode(self):
        globex = ['CME', 'NYM', 'CBT', 'GBX', 'MSGW']
        cfe = ['CFE']
        mifid = ['EUR', 'CURVE', 'EUNX', 'IDME', 'LME', 'NORD', 'Nordic', 'ICEUK', 'ICEEU', 'ICEUS', 'MEFF', 'OMX']

        exchange = self.instance['Exchange'].upper()
        if exchange in globex:
            mode = '--mode Globex'
        elif exchange in cfe:
            mode = '--mode CFE'
        elif exchange in mifid:
            mode = '--mode MiFID'
        else:
            mode = '--mode FrontRunner'

        logging.debug("Applying AuditToCsv %s for %s", mode, self.instance['Exchange'])

        return mode

    def decode(self):
        mode = self.get_mode()
        A2C_path = os.path.join(A2C_loc, self.Audit2csv)
        A2C_opt = ' --override --excel ' + mode
        A2C_ver = ' -a ' + os.path.join(A2C_loc, 'Versions')

        for f in os.listdir(self.zip_path):
            if re.search('Audit.*.log', f):
                output_name = f[:-4]
                A2C_in = ' -i ' + os.path.join(self.zip_path, f)
                A2C_out = ' -o ' + os.path.join(self.zip_path, '%s.csv' % output_name)
                logging.info('Decoding %s', os.path.join(self.zip_path, f))
                result = subprocess.call(A2C_path + A2C_opt + A2C_ver + A2C_in + A2C_out, shell=True)
                if result == 0:
                    logging.info("%s successfully decoded", f)
                else:
                    logging.error('%s failed to decode: %s', f, result)
                    raise Exception('Unable to decode %s' % f)

        self.zip_decoded()

    def zip_decoded(self):

        if os.listdir(self.zip_path):
            zf = zipfile.ZipFile(os.path.join(self.zip_path, self.zip_name), mode='w')
            for f in os.listdir(self.zip_path):
                if not f.endswith('.zip'):
                    logging.info('Adding %s to %s', f, self.zip_name)
                    zf.write(os.path.join(self.zip_path, f), f, compress_type=zipfile.ZIP_DEFLATED)

            zf.close()

        # Delete the left over files
        for f in os.listdir(self.zip_path):
            if not f.endswith('.zip'):
                logging.info('Deleting zipped: %s', f)
                os.remove(os.path.join(self.zip_path, f))


class EncryptZIPs(object):
    def __init__(self, zipaud):
        self.zip_path = zipaud.zip_path
        self.recipient = zipaud.instance['Recipient']
        self.gpgbin = gpg_loc
        self.gpghome = gpg_home

    def encrypt(self):
        gpg = gnupg.GPG(gpgbinary=self.gpgbin, gnupghome=self.gpghome)
        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                logging.info('Encrypting %s', f)
                output_name = f+'.gpg'
                stream = open(os.path.join(self.zip_path, f), 'rb')
                result = gpg.encrypt_file(stream, 'Recipient ' + self.recipient, output=os.path.join(self.zip_path, output_name))
                if not result.ok:
                    logging.error('%s failed to encrypt: %s', f, result.status)
                    raise Exception('Unable to encrypt: %s' % result.status)
                else:
                    logging.info('%s encrypted successfully', output_name)

        # Delete the zips that have been encrypted
        for f in os.listdir(self.zip_path):
            if f.endswith('.zip'):
                logging.info('Deleting encrypted zip: %s', f)
                os.remove(os.path.join(self.zip_path, f))


class BrickFTP(object):
    def __init__(self, zipaud):
        logging.info('Connecting to Brick')
        self.enc_loc = zipaud.instance['Recipient']
        self.zip_path = zipaud.zip_path
        self.archive_path = zipaud.archive_path
        self.brick_loc = os.path.join('PaaS', zipaud.instance['Recipient'])  # zipaud.instance['Exchange'], zipaud.instance['Instance'])
        self.brick_loc_archive = os.path.join('PaaS', 'Archive', zipaud.instance['Recipient'])

        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh.connect('paas.tradevela.com', username='a.mcfarlane', key_filename=os.path.join(ssh_key_loc, 'id_rsa'), port=22)
        self.sftp = self.ssh.open_sftp()
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        self.pysftp = pysftp.Connection('paas.tradevela.com', username='a.mcfarlane', cnopts=cnopts, private_key=os.path.join(ssh_key_loc, 'id_rsa'), port=22)

    def push_to_brick(self):
        enc_files = os.listdir(self.zip_path)
        # Create folder structure on Brick
        if not self.pysftp.exists(self.brick_loc):
            logging.info('Creating %s on Brick server', self.brick_loc)
            self.pysftp.makedirs(self.brick_loc)
        if not self.pysftp.exists(self.brick_loc_archive):
            logging.info('Creating %s on Brick server', self.brick_loc_archive)
            self.pysftp.makedirs(self.brick_loc_archive)

        # Push the gpg to Brick
        for f in enc_files:
            if f.endswith('.gpg'):
                logging.info('Pushing %s to %s on the Brick server', f, self.brick_loc)
                self.sftp.put(os.path.join(self.zip_path, f), os.path.join(self.brick_loc, f))

        # Delete the uploaded gpg
        for f in enc_files:
            if f.endswith('.gpg'):
                os.remove(os.path.join(self.zip_path, f))


class EmailResult(object):
    def __init__(self):
        pass

    def sendMail(self, to, fro, subject, text, files=[], server="localhost"):
        assert type(to) == list
        assert type(files) == list

        textmsg = ''
        if len(text) > 0:
            for instance in text:
                textmsg += instance + '\n'
        else:
            textmsg = 'All SFTP instances Published to Brick successfully'

        msg = MIMEMultipart()
        msg['From'] = fro
        msg['To'] = COMMASPACE.join(to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject

        msg.attach(MIMEText(textmsg))

        for file in files:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(open(file, "rb").read())
            Encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment; filename="%s"'
                            % os.path.basename(file))
            msg.attach(part)

        smtp = smtplib.SMTP(server)
        smtp.sendmail(fro, to, msg.as_string())
        smtp.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config_file", default="client_conf.json", help="Config file to run the script against")
    args = parser.parse_args()
    # Set logging
    logging.basicConfig(format='%(asctime)s: %(levelname)s: %(funcName)s: %(message)s', level=logging.DEBUG)


    complete = 0
    failed = []

    config_file = os.path.join(current_dir, args.config_file)
    tmp_loc = '/home/ot/audits'  # Temp location for Audits on remote server
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
            try:
                int(instance['Date'])
                fdate = str(instance['Date'])
            except ValueError:
                # Set date for the zip name
                if instance['Date'].lower() == 'today':
                    fdate = datetime.date.today().strftime("%Y%m%d")
                elif instance['Date'].lower() == 'yesterday':
                    fdate = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")
                elif instance['Date'].lower() == 'all':
                    fdate = datetime.date.today().strftime("%Y%m%d") + '_All'
                else:
                    raise Exception("Invalid date, Should be ['{date}, all, today or yesterday")

            instance_name = "%s's %s_%s_AuditTrail_%s_%s_%s" % (instance['Recipient'], instance['Client'],
                                                                instance['Exchange'], instance['Instance'],
                                                                instance['SessionID'], fdate)

            try:
                logging.info("Trying %s", instance_name)
                zipaud = ZipFiles(instance, tmp_loc, fdate)
                zipaud.run_zipit()
                decode = DecodeAudits(zipaud)
                decode.decode()
                encrypt = EncryptZIPs(zipaud)
                encrypt.encrypt()
                brick = BrickFTP(zipaud)
                brick.push_to_brick()
                complete += 1
                logging.info('%s Completed Successfully', instance_name)
            except Exception as err:
                print err
                logging.error("%s Failed: %s", instance_name, err)
                failed.append("%s: %s" % (instance_name, err))

    logging.info('%s Completed', complete)
    logging.error('%s', failed)

    # mail = EmailResult()
    # mail.sendMail(['amcfarlane@tradevela.com', 'fpotter@tradevela.com'], 'AuditReport@PaaSMgtVM.com', 'PaaSMgtVM Audit Report %s' % datetime.date.today().strftime("%Y%m%d"), failed)

if __name__ == '__main__':
    main()
