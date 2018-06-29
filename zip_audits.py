#!/usr/bin/python

__version__ = '1.0'

import zipfile
import os
import datetime
import logging
import re
import shutil
import optparse
import sys

logging.basicConfig(format='%(asctime)s: %(levelname)s: %(message)s', level=logging.DEBUG)


class ZipFiles(object):
    def __init__(self, audit_location, temp_directory, filedate):
        self.audit_location = audit_location
        self.temp_directory = temp_directory
        self.filedate = filedate

        if not os.path.exists(self.temp_directory):
            os.makedirs(self.temp_directory)

        self.output_name = 'Audit.%s.zip' % datetime.date.today().strftime("%Y%m%d")
        self.zf = zipfile.ZipFile(os.path.join(self.temp_directory, self.output_name), mode='w')

    def audit_date(self):
        if self.filedate == 'today':
            fdate = datetime.date.today().strftime("%Y%m%d")  # current_date in {20181231 format}
            adate = ['Audit.'+fdate+'.log']
            self.date_logging(adate)
            self.zip_date(adate)
        elif self.filedate == 'yesterday':
            fdate = (datetime.date.today() - datetime.timedelta(days=1)).strftime("%Y%m%d")  # current_date -1 day
            adate = ['Audit.'+fdate+'.log']
            self.date_logging(adate)
            self.zip_date(adate)
        elif self.filedate == 'all':
            self.all_audits()

    def date_logging(self, fdate):
        logging.debug('audit date: Audit date requested: %s', fdate)

    def all_audits(self):
        to_zip = []
        files = os.listdir(self.audit_location)

        for audit in files:
            if re.search('Audit.*.log', audit):
                to_zip.append(audit)

        self.zip_date(to_zip)

    def zip_date(self, audittodecode):
        """
        Set the date of the Audit to be zipped and copy it to the temp directory
        :param audittodecode: date of the audit to be zipped
        :return:
        """
        try:
            prod_files = os.listdir(self.audit_location)
        except OSError as err:
            logging.error(err)
            sys.exit()

        self.zf = zipfile.ZipFile(os.path.join(self.temp_directory, self.output_name), mode='w')

        for audit in audittodecode:
            if audit not in prod_files:
                logging.error('zip date: %s does not exist in %s directory', audit, self.audit_location)
            else:
                logging.debug('zip date: Copying %s to %s', audit, self.temp_directory)
                shutil.copy2(os.path.join(self.audit_location, audit), self.temp_directory)
                if not audit.endswith('.zip'):
                    logging.info('zip date: Adding %s to %s', audit, self.output_name)
                    self.zf.write(os.path.join(self.temp_directory, audit), audit, compress_type=zipfile.ZIP_DEFLATED)
                    logging.debug('zip date: Deleting %s from %s', audit, self.temp_directory)
                    os.remove(os.path.join(self.temp_directory, audit))

        self.zf.close()


def main():
    usage = "usage: %prog [options]"
    parser = optparse.OptionParser(usage=usage, version='%prog ' + __version__)
    parser.add_option('-d', '--date', action='store', default='today', dest='filedate', metavar=' ',
                      help='Choose the date of the file. [default: %default]')
    parser.add_option('-a', '--audit-loc', action='store', default='/home/ot', dest='audit_location', metavar=' ',
                      help='Define Audit Location i.e. LogFiles directory. [default: %default]')
    parser.add_option('-t', '--tmp-loc', action='store', default='/var/tmp/audits', dest='tmp_location', metavar=' ',
                      help='Define temp file location where audits will be copied and processed '
                           'i.e. LogFiles directory. [default: %default]')
    (options, args) = parser.parse_args()
    getzip = ZipFiles(options.audit_location, options.tmp_location, options.filedate)
    getzip.audit_date()


if __name__ == "__main__":
    main()
