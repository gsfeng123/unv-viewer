/**
 * UNV Viewer Server - BS架构后端
 * 提供文件上传、解析和API服务
 */

const express = require('express');
const multer = require('multer');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const UNVParser = require('./unv-parser');

const app = express();
const PORT = process.env.PORT || 3000;

// 中间件
app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// 配置文件上传
const upload = multer({
  dest: 'uploads/',
  limits: { fileSize: 100 * 1024 * 1024 }, // 100MB限制
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    if (ext === '.unv' || ext === '.txt' || ext === '') {
      cb(null, true);
    } else {
      cb(new Error('只支持UNV或TXT文件'));
    }
  }
});

// 确保上传目录存在
const uploadsDir = path.join(__dirname, 'uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// 创建解析器实例
const parser = new UNVParser();

/**
 * API: 解析UNV文件
 */
app.post('/api/parse', upload.single('file'), (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: '请上传文件' });
    }

    const filePath = req.file.path;
    const result = parser.parseFile(filePath);
    
    // 添加文件名信息
    result.fileName = req.file.originalname;
    result.fileSize = req.file.size;

    // 清理上传的临时文件
    fs.unlinkSync(filePath);

    res.json(result);
  } catch (error) {
    console.error('解析错误:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * API: 从路径解析UNV文件
 */
app.post('/api/parse-path', (req, res) => {
  try {
    const { filePath } = req.body;
    
    if (!filePath) {
      return res.status(400).json({ error: '请提供文件路径' });
    }

    if (!fs.existsSync(filePath)) {
      return res.status(404).json({ error: '文件不存在: ' + filePath });
    }

    const stats = fs.statSync(filePath);
    const result = parser.parseFile(filePath);
    
    result.fileName = path.basename(filePath);
    result.fileSize = stats.size;

    res.json(result);
  } catch (error) {
    console.error('解析错误:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * API: 获取测试数据文件列表
 */
app.get('/api/testfiles', (req, res) => {
  try {
    const testdataDir = path.join(__dirname, 'testdata');
    
    if (!fs.existsSync(testdataDir)) {
      return res.json({ files: [] });
    }

    const files = fs.readdirSync(testdataDir)
      .filter(f => f.endsWith('.unv'))
      .map(f => {
        const filePath = path.join(testdataDir, f);
        const stats = fs.statSync(filePath);
        return {
          name: f,
          path: filePath,
          size: stats.size,
          sizeFormatted: formatFileSize(stats.size)
        };
      });

    res.json({ files });
  } catch (error) {
    console.error('获取文件列表错误:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * API: 获取默认测试文件
 */
app.get('/api/default-file', (req, res) => {
  try {
    const testdataDir = path.join(__dirname, 'testdata');
    const testFile = path.join(testdataDir, 'test1.unv');
    
    if (!fs.existsSync(testFile)) {
      return res.status(404).json({ error: '测试文件不存在' });
    }

    const stats = fs.statSync(testFile);
    const result = parser.parseFile(testFile);
    
    result.fileName = 'test1.unv';
    result.fileSize = stats.size;

    res.json(result);
  } catch (error) {
    console.error('解析默认文件错误:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * 辅助函数: 格式化文件大小
 */
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 启动服务器
app.listen(PORT, () => {
  console.log(`UNV Viewer 服务已启动: http://localhost:${PORT}`);
  console.log(`测试数据目录: ${path.join(__dirname, 'testdata')}`);
});
