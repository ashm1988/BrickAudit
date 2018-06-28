import zip_audits
import logging
import os

logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.DEBUG)



audit_loc = r'/home/ot'
script = 'zip_audits.py'

audit_loc = os.path.split(audit_loc)
# print os.path.join(audit_loc[0], audit_loc[1], script)
A2C_loc = r'C:\Users\amcfarlane\Documents\Object Trading\FR Admin Tools 4.1.3.9 Windows x64\AuditToCsv'

print os.path.dirname(A2C_loc)