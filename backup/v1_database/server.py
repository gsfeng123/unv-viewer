# UNV Viewer - Python Flask Backend
# 使用 pyuff 库解析 UNV 文件

import os
import json
import sqlite3
import pyuff
import numpy as np
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
from pathlib import Path

app = Flask(__name__, static_folder='public')
CORS(app)

# 数据库配置
DB_PATH = os.path.join(os.path.dirname(__file__), 'unv_data.db')

# 自定义JSON编码器处理numpy类型
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)

app.json_encoder = NumpyEncoder

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建文件信息表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT NOT NULL,
            file_size INTEGER,
            import_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_datasets INTEGER,
            total_points INTEGER,
            file_hash TEXT
        )
    ''')
    
    # 创建数据集表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            dataset_number INTEGER NOT NULL,
            dataset_name TEXT,
            dataset_type TEXT,
            data_points INTEGER,
            num_pts INTEGER,
            id1 TEXT,
            id2 TEXT,
            id3 TEXT,
            id4 TEXT,
            FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建函数数据表（存储曲线数据）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS function_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER NOT NULL,
            x_value REAL,
            y_real REAL,
            y_imag REAL,
            FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_name ON files(file_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_dataset_file ON datasets(file_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_function_dataset ON function_data(dataset_id)')
    
    conn.commit()
    conn.close()

# 初始化数据库
init_db()

# 数据集名称映射
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

def import_file_to_db(file_path):
    """导入单个文件到数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 检查文件是否已存在
        cursor.execute('SELECT id, file_hash FROM files WHERE file_path = ?', (file_path,))
        existing = cursor.fetchone()
        
        if existing:
            print(f"文件已存在: {file_path}")
            conn.close()
            return {'success': False, 'message': '文件已存在', 'existing': True}
        
        # 解析UNV文件
        uff = pyuff.UFF(file_path)
        datasets = uff.read_sets()
        
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        
        # 计算数据点总数
        total_points = 0
        for ds in datasets:
            if ds.get('type') == 58:
                total_points += int(ds.get('num_pts', 0))
        
        # 插入文件记录
        cursor.execute('''
            INSERT INTO files (file_path, file_name, file_size, total_datasets, total_points)
            VALUES (?, ?, ?, ?, ?)
        ''', (file_path, file_name, file_size, len(datasets), total_points))
        
        file_id = cursor.lastrowid
        
        # 插入数据集记录
        for ds in datasets:
            ds_type = ds.get('type', 0)
            
            cursor.execute('''
                INSERT INTO datasets (file_id, dataset_number, dataset_name, dataset_type, data_points, num_pts, id1, id2, id3, id4)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_id,
                ds_type,
                get_dataset_name(ds_type),
                ds.get('type_name', ''),
                0,  # data_points - will update
                int(ds.get('num_pts', 0)),
                str(ds.get('id1', '')),
                str(ds.get('id2', '')),
                str(ds.get('id3', '')),
                str(ds.get('id4', ''))
            ))
            
            dataset_id = cursor.lastrowid
            
            # 如果是函数类型(58)，存储数据点
            if ds_type == 58:
                x_data = ds.get('x', [])
                y_data = ds.get('data', [])
                num_pts = int(ds.get('num_pts', 0))
                
                if isinstance(x_data, np.ndarray):
                    x_data = x_data.tolist()
                if isinstance(y_data, np.ndarray):
                    y_data = y_data.tolist()
                
                max_points = min(num_pts, 5000) if num_pts > 0 else min(len(x_data), len(y_data), 5000)
                
                # 批量插入数据点
                data_points = []
                for j in range(max_points):
                    try:
                        val = y_data[j]
                        if isinstance(val, complex):
                            data_points.append((dataset_id, x_data[j], val.real, val.imag))
                        else:
                            data_points.append((dataset_id, x_data[j], val, 0))
                    except:
                        pass
                
                if data_points:
                    cursor.executemany('''
                        INSERT INTO function_data (dataset_id, x_value, y_real, y_imag)
                        VALUES (?, ?, ?, ?)
                    ''', data_points)
                
                # 更新数据点数
                cursor.execute('UPDATE datasets SET data_points = ? WHERE id = ?', (len(data_points), dataset_id))
        
        conn.commit()
        print(f"成功导入: {file_path}")
        return {'success': True, 'file_id': file_id, 'datasets': len(datasets)}
        
    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def import_folder_to_db(folder_path):
    """导入文件夹中的所有UNV文件"""
    results = {
        'success': [],
        'failed': [],
        'skipped': []
    }
    
    if not os.path.exists(folder_path):
        return {'error': '文件夹不存在'}
    
    # 获取所有UNV文件
    unv_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.unv'):
                unv_files.append(os.path.join(root, file))
    
    for file_path in unv_files:
        result = import_file_to_db(file_path)
        if result.get('success'):
            results['success'].append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'datasets': result.get('datasets', 0)
            })
        elif result.get('existing'):
            results['skipped'].append({
                'path': file_path,
                'name': os.path.basename(file_path)
            })
        else:
            results['failed'].append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'error': result.get('message', 'Unknown error')
            })
    
    return results

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

# ========== 文件解析API ==========

@app.route('/api/parse', methods=['POST'])
def parse_upload():
    if 'file' not in request.files:
        return jsonify({'error': '请上传文件'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'}), 400
    
    filename = file.filename
    filepath = os.path.join('uploads', filename)
    os.makedirs('uploads', exist_ok=True)
    file.save(filepath)
    
    try:
        from server_utils import parse_unv_file
        result = parse_unv_file(filepath)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)

@app.route('/api/parse-path', methods=['POST'])
def parse_path():
    data = request.get_json()
    file_path = data.get('filePath', '')
    
    if not file_path:
        return jsonify({'error': '请提供文件路径'}), 400
    
    if not os.path.exists(file_path):
        return jsonify({'error': f'文件不存在: {file_path}'}), 404
    
    try:
        from server_utils import parse_unv_file
        result = parse_unv_file(file_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/testfiles', methods=['GET'])
def test_files():
    possible_dirs = ['testdata', 'C:\\code\\unv_read\\testdata']
    
    testdata_dir = None
    for d in possible_dirs:
        if os.path.exists(d):
            testdata_dir = d
            break
    
    if not testdata_dir:
        return jsonify({'files': []})
    
    files = []
    for f in os.listdir(testdata_dir):
        if f.endswith('.unv'):
            filepath = os.path.join(testdata_dir, f)
            size = os.path.getsize(filepath)
            files.append({
                'name': f,
                'path': filepath,
                'size': size,
                'sizeFormatted': format_file_size(size)
            })
    
    return jsonify({'files': files})

# ========== 数据库API ==========

@app.route('/api/db/files', methods=['GET'])
def get_db_files():
    """获取数据库中所有文件"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, file_path, file_name, file_size, import_time, total_datasets, total_points
        FROM files ORDER BY import_time DESC
    ''')
    
    files = []
    for row in cursor.fetchall():
        files.append({
            'id': row['id'],
            'file_path': row['file_path'],
            'file_name': row['file_name'],
            'file_size': row['file_size'],
            'file_size_formatted': format_file_size(row['file_size']),
            'import_time': row['import_time'],
            'total_datasets': row['total_datasets'],
            'total_points': row['total_points']
        })
    
    conn.close()
    return jsonify({'files': files})

@app.route('/api/db/file/<int:file_id>', methods=['GET'])
def get_db_file(file_id):
    """获取单个文件的详细信息"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM files WHERE id = ?', (file_id,))
    file_row = cursor.fetchone()
    
    if not file_row:
        conn.close()
        return jsonify({'error': '文件不存在'}), 404
    
    file_info = {
        'id': file_row['id'],
        'file_path': file_row['file_path'],
        'file_name': file_row['file_name'],
        'file_size': file_row['file_size'],
        'file_size_formatted': format_file_size(file_row['file_size']),
        'import_time': file_row['import_time'],
        'total_datasets': file_row['total_datasets'],
        'total_points': file_row['total_points']
    }
    
    # 获取数据集列表
    cursor.execute('''
        SELECT id, dataset_number, dataset_name, data_points, num_pts, id1, id2, id3, id4
        FROM datasets WHERE file_id = ? ORDER BY dataset_number
    ''', (file_id,))
    
    datasets = []
    for row in cursor.fetchall():
        datasets.append({
            'id': row['id'],
            'dataset_number': row['dataset_number'],
            'dataset_name': row['dataset_name'],
            'data_points': row['data_points'],
            'num_pts': row['num_pts'],
            'id1': row['id1'],
            'id2': row['id2']
        })
    
    file_info['datasets'] = datasets
    conn.close()
    
    return jsonify(file_info)

@app.route('/api/db/dataset/<int:dataset_id>', methods=['GET'])
def get_db_dataset(dataset_id):
    """获取数据集的曲线数据"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 获取数据集信息
    cursor.execute('SELECT * FROM datasets WHERE id = ?', (dataset_id,))
    ds_row = cursor.fetchone()
    
    if not ds_row:
        conn.close()
        return jsonify({'error': '数据集不存在'}), 404
    
    dataset_info = {
        'id': ds_row['id'],
        'dataset_number': ds_row['dataset_number'],
        'dataset_name': ds_row['dataset_name'],
        'num_pts': ds_row['num_pts'],
        'data_points': ds_row['data_points'],
        'id1': ds_row['id1'],
        'id2': ds_row['id2']
    }
    
    # 获取数据点
    limit = int(request.args.get('limit', 1000))
    cursor.execute('''
        SELECT x_value, y_real, y_imag FROM function_data
        WHERE dataset_id = ? ORDER BY x_value LIMIT ?
    ''', (dataset_id, limit))
    
    data = []
    for row in cursor.fetchall():
        data.append([row['x_value'], row['y_real'], row['y_imag']])
    
    dataset_info['data'] = data
    conn.close()
    
    return jsonify(dataset_info)

@app.route('/api/db/import-file', methods=['POST'])
def import_single_file():
    """导入单个文件到数据库"""
    data = request.get_json()
    file_path = data.get('filePath', '')
    
    if not file_path:
        return jsonify({'error': '请提供文件路径'}), 400
    
    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    result = import_file_to_db(file_path)
    return jsonify(result)

@app.route('/api/db/import-folder', methods=['POST'])
def import_folder():
    """批量导入文件夹中的所有UNV文件"""
    data = request.get_json()
    folder_path = data.get('folderPath', '')
    
    if not folder_path:
        return jsonify({'error': '请提供文件夹路径'}), 400
    
    if not os.path.exists(folder_path):
        return jsonify({'error': '文件夹不存在'}), 404
    
    if not os.path.isdir(folder_path):
        return jsonify({'error': '路径不是文件夹'}), 400
    
    result = import_folder_to_db(folder_path)
    return jsonify(result)

@app.route('/api/db/select-files', methods=['POST'])
def import_selected_files():
    """导入选中的文件列表"""
    data = request.get_json()
    file_paths = data.get('filePaths', [])
    
    if not file_paths:
        return jsonify({'error': '请选择文件'}), 400
    
    results = {
        'success': [],
        'failed': []
    }
    
    for file_path in file_paths:
        if not os.path.exists(file_path):
            results['failed'].append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'error': '文件不存在'
            })
            continue
            
        result = import_file_to_db(file_path)
        if result.get('success'):
            results['success'].append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'datasets': result.get('datasets', 0)
            })
        else:
            results['failed'].append({
                'path': file_path,
                'name': os.path.basename(file_path),
                'error': result.get('message', 'Unknown error')
            })
    
    return jsonify(results)

@app.route('/api/db/delete-file/<int:file_id>', methods=['DELETE'])
def delete_file(file_id):
    """删除数据库中的文件记录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DELETE FROM files WHERE id = ?', (file_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/db/folder-files', methods=['POST'])
def get_folder_files():
    """获取文件夹中的UNV文件列表"""
    data = request.get_json()
    folder_path = data.get('folderPath', '')
    
    if not folder_path:
        return jsonify({'error': '请提供文件夹路径'}), 400
    
    if not os.path.exists(folder_path):
        return jsonify({'error': '文件夹不存在'}), 404
    
    # 检查是否已入库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    files = []
    for root, dirs, filenames in os.walk(folder_path):
        for filename in filenames:
            if filename.endswith('.unv'):
                full_path = os.path.join(root, filename)
                size = os.path.getsize(full_path)
                
                # 检查是否已入库
                cursor.execute('SELECT id FROM files WHERE file_path = ?', (full_path,))
                existing = cursor.fetchone()
                
                files.append({
                    'path': full_path,
                    'name': filename,
                    'size': size,
                    'sizeFormatted': format_file_size(size),
                    'imported': existing is not None
                })
    
    conn.close()
    return jsonify({'files': files, 'folder': folder_path})

@app.route('/api/db/stats', methods=['GET'])
def get_db_stats():
    """获取数据库统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM files')
    total_files = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM datasets')
    total_datasets = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM function_data')
    total_points = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(file_size) FROM files')
    total_size = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_files': total_files,
        'total_datasets': total_datasets,
        'total_points': total_points,
        'total_size': total_size,
        'total_size_formatted': format_file_size(total_size)
    })

if __name__ == '__main__':
    print("UNV Viewer 服务已启动: http://localhost:3000")
    print(f"数据库路径: {DB_PATH}")
    app.run(host='0.0.0.0', port=3000, debug=True)
