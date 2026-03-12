# Quick test of pyuff
import pyuff

# Test reading a file
try:
    uff = pyuff.UFF(r'C:\code\unv_read\testdata\test1.unv')
    datasets = uff.get_set_types()
    print(f"Datasets found: {datasets}")
    
    # Try to read dataset 15
    if 15 in datasets:
        data15 = uff.read(15)
        print(f"Dataset 15 data: {data15[:2]}")  # First 2 items
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
