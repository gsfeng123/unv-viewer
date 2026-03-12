# Test import
import sys
sys.path.insert(0, r'C:\code\unv_read')
from server import import_folder_to_db

result = import_folder_to_db(r'C:\code\unv_read\testdata')
print(result)
