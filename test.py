import logging

logging.basicConfig(format='%(asctime)s: %(levelname)s: %(funcName)s: %(name)s: %(message)s', level=logging.INFO)
fh = logging.FileHandler('filehandler.log')
fh.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(funcName)s: %(name)s: %(message)s')
fh.setFormatter(formatter)
logging.getLogger('').addHandler(fh)

logging.info('log this message')