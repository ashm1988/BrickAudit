import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sftp_script = 'zip_audits.py'  # Name of SFTP Script
scripts_loc = '/opt/ot/scripts'  # Where on the remote server to put the Script
sftp_script_loc = r'/opt/ot/scripts/zip_audits.py'  # Lazy location naming for the script to run on the remote server
client_zip_location = r'C:\Users\amcfarlane\Documents\temp\audits'  # Base location of where to save/process the audits
A2C_loc = r'C:\Users\amcfarlane\Documents'  # location of the FR Admin Tools
ssh_key_loc = r'C:\cygwin64\home\amcfarlane\.ssh'  # ssh key location
gpg_loc = r'C:\Program Files (x86)\GnuPG\bin\gpg.exe'
gpg_home = r'C:\Users\amcfarlane\AppData\Roaming\gnupg'
