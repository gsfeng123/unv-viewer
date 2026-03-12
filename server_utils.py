# UNV解析工具函数

import os
import pyuff
import numpy as np

DATASET_NAMES = {
    15: 'Nodes',
    55: 'Data at Nodes',
    58: 'Function / Group',
    82: 'Tracelines',
    151: 'Project Information',
    152: 'Model Definition',
    154: 'Analysis',
    158: 'Material',
    164: 'Response Function',
    1801: 'Unit',
    1802: 'Function Definition',
    1803: 'Coordinate System',
    1804: 'Layer',
    1806: 'Color',
    1807: 'Text Style',
    1808: 'Line Style',
    1810: 'Post Script',
    1815: 'Measurement Data',
    1858: 'Reduced Data Set',
    1700: '3D Node',
    1702: '3D Element',
    2411: 'Nodes - Double Precision',
    2412: 'Elements',
    2413: 'Element Properties',
    2414: 'Element Groups',
    2415: 'Coordinate Systems',
    2416: 'Constraints',
    2417: 'Degrees of Freedom',
    2418: 'Singular Points',
    2420: 'Load Cases',
    2421: 'Load Types',
    2422: 'Response Spectra',
    2423: 'Random Response'
}

def get_dataset_name(dataset_num):
    return DATASET_NAMES.get(dataset_num, f'Unknown ({dataset_num})')

def format_file_size(bytes_size):
    if bytes_size == 0:
        return '0 B'
    k = 1024
    sizes = ['B', 'KB', 'MB', 'GB']
    i = 0
    while bytes_size >= k and i < len(sizes) - 1:
        bytes_size /= k
        i += 1
    return f"{bytes_size:.2f} {sizes[i]}"

def parse_unv_file(file_path):
    """解析UNV文件"""
    try:
        print(f"Parsing file: {file_path}")
        
        uff = pyuff.UFF(file_path)
        datasets = uff.read_sets()
        
        print(f"Number of datasets: {len(datasets)}")
        
        set_types = {}
        for ds in datasets:
            ds_type = ds.get('type', 0)
            set_types[ds_type] = set_types.get(ds_type, 0) + 1
        
        result = {
            'success': True,
            'fileName': os.path.basename(file_path),
            'fileSize': os.path.getsize(file_path),
            'fileSizeFormatted': format_file_size(os.path.getsize(file_path)),
            'totalDatasets': len(datasets),
            'datasets': [],
            'summary': {
                'datasetTypes': {},
                'totalRecords': 0
            }
        }
        
        for i, ds in enumerate(datasets):
            ds_type = ds.get('type', 0)
            
            dataset = {
                'number': ds_type,
                'name': get_dataset_name(ds_type),
                'index': i,
                'records': None
            }
            
            try:
                if ds_type == 58:
                    x_data = ds.get('x', [])
                    y_data = ds.get('data', [])
                    num_pts = int(ds.get('num_pts', 0))
                    
                    # 获取响应实体名称 (Record 6 Field 5) - rsp_ent_name
                    response_name = str(ds.get('rsp_ent_name', '')).strip()
                    
                    # 如果有响应名称，使用它作为数据集名称
                    if response_name and response_name != '0':
                        dataset['name'] = response_name
                    
                    # 同时保存到records中供前端使用
                    dataset['rsp_ent_name'] = response_name
                    
                    if isinstance(x_data, np.ndarray):
                        x_data = x_data.tolist()
                    if isinstance(y_data, np.ndarray):
                        y_data = y_data.tolist()
                    
                    max_points = min(num_pts, 10000) if num_pts > 0 else min(len(x_data), len(y_data), 10000)
                    
                    func_data = []
                    for j in range(max_points):
                        try:
                            val = y_data[j]
                            if isinstance(val, complex):
                                func_data.append([x_data[j], val.real, val.imag])
                            else:
                                func_data.append([x_data[j], val, 0])
                        except:
                            pass
                    
                    dataset['records'] = {
                        'type': 'function',
                        'count': len(func_data),
                        'totalPoints': num_pts,
                        'data': func_data,
                        'id1': str(ds.get('id1', '')),
                        'id2': str(ds.get('id2', '')),
                        'id3': str(ds.get('id3', '')),
                        'id4': str(ds.get('id4', '')),
                        'num_pts': num_pts,
                        'abscissa_min': float(ds.get('abscissa_min', 0)),
                        'abscissa_inc': float(ds.get('abscissa_inc', 0))
                    }
                    result['summary']['totalRecords'] += len(func_data)
                
                elif ds_type == 151:
                    dataset['records'] = {
                        'type': 'project_info',
                        'data': {
                            'id1': str(ds.get('id1', '')),
                            'id2': str(ds.get('id2', '')),
                            'id3': str(ds.get('id3', '')),
                            'id4': str(ds.get('id4', '')),
                            'id5': str(ds.get('id5', '')),
                            'id6': str(ds.get('id6', ''))
                        }
                    }
                
                elif ds_type == 15 or ds_type == 2411:
                    nodes = []
                    for key in ['nodelab', 'node_label', 'label']:
                        if key in ds:
                            nodes.append({
                                'label': ds.get(key, i+1),
                                'x': float(ds.get('x', 0)),
                                'y': float(ds.get('y', 0)),
                                'z': float(ds.get('z', 0))
                            })
                            break
                    
                    if not nodes and 'x' in ds:
                        x = ds.get('x', [])
                        y = ds.get('y', [])
                        z = ds.get('z', [])
                        if isinstance(x, np.ndarray):
                            for j in range(min(len(x), 100)):
                                nodes.append({
                                    'label': j + 1,
                                    'x': float(x[j]) if j < len(x) else 0,
                                    'y': float(y[j]) if j < len(y) else 0,
                                    'z': float(z[j]) if j < len(z) else 0
                                })
                    
                    dataset['records'] = {
                        'type': 'nodes',
                        'count': len(nodes),
                        'data': nodes
                    }
                    result['summary']['totalRecords'] += len(nodes)
                
                elif ds_type == 2412:
                    elements = []
                    if 'elelab' in ds:
                        elements.append({
                            'label': ds.get('elelab', 0),
                            'feDescriptor': ds.get('fe', 0),
                            'nodes': convert_numpy(ds.get('nodelist', []))
                        })
                    
                    dataset['records'] = {
                        'type': 'elements',
                        'count': len(elements),
                        'data': elements
                    }
                    result['summary']['totalRecords'] += len(elements)
                
                else:
                    clean_ds = convert_numpy(ds)
                    if 'x' in clean_ds:
                        del clean_ds['x']
                    if 'data' in clean_ds:
                        del clean_ds['data']
                    
                    dataset['records'] = {
                        'type': 'generic',
                        'data': str(clean_ds)[:500]
                    }
                
            except Exception as e:
                dataset['records'] = {
                    'type': 'error',
                    'error': str(e)
                }
            
            result['datasets'].append(dataset)
            
            ds_name = dataset['name']
            if ds_name not in result['summary']['datasetTypes']:
                result['summary']['datasetTypes'][ds_name] = 0
            result['summary']['datasetTypes'][ds_name] += 1
        
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }

def convert_numpy(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy(i) for i in obj]
    return obj
