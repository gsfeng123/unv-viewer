import sys
sys.path.insert(0, r'C:\code\unv_read')
from server import import_file_to_db
import os

folder = r'C:\code\unv_read\unv\psd'
for f in os.listdir(folder):
    if f.endswith('.unv'):
        path = os.path.join(folder, f)
        print(f'Importing: {f}')
        result = import_file_to_db(path)
        print(f'Result: {result}')
        print('---')
