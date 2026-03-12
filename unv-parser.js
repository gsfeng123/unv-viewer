/**
 * UNV文件解析器
 * Universal File Format 解析
 */

const fs = require('fs');
const path = require('path');

class UNVParser {
  constructor() {
    // 数据集类型定义
    this.datasetNames = {
      15: 'Nodes',
      55: 'Data at Nodes',
      58: 'Group / Tracelines',
      82: 'Tracelines',
      151: 'Project Information',
      152: 'Model Definition',
      154: 'Analysis',
      158: 'Material',
      164: 'Response Function',
      1801: 'Unit',
      1802: 'Function',
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
    };
  }

  /**
   * 解析UNV文件
   * @param {string} filePath - 文件路径
   * @returns {Object} 解析结果
   */
  parseFile(filePath) {
    const content = fs.readFileSync(filePath, 'utf8');
    return this.parseContent(content);
  }

  /**
   * 解析UNV内容
   * @param {string} content - 文件内容
   * @returns {Object} 解析结果
   */
  parseContent(content) {
    const lines = content.split(/\r?\n/);
    const datasets = [];
    let i = 0;

    while (i < lines.length) {
      // 查找数据集开始标记 "-1"
      if (lines[i].trim() === '-1') {
        i++;
        if (i < lines.length) {
          const datasetNumber = parseInt(lines[i].trim());
          // 忽略-1作为数据集编号
          if (!isNaN(datasetNumber) && datasetNumber > 0) {
            const dataset = this.parseDataset(lines, datasetNumber, i + 1);
            if (dataset) {
              datasets.push(dataset);
              i = dataset.endLine;
              continue;
            }
          }
        }
      }
      i++;
    }

    return {
      success: true,
      totalDatasets: datasets.length,
      datasets: datasets,
      summary: this.generateSummary(datasets)
    };
  }

  /**
   * 解析单个数据集
   */
  parseDataset(lines, datasetNumber, startIndex) {
    const dataset = {
      number: datasetNumber,
      name: this.datasetNames[datasetNumber] || `Unknown (${datasetNumber})`,
      records: [],
      rawData: {}
    };

    let currentLine = startIndex;
    let endLine = currentLine;

    try {
      switch (datasetNumber) {
        case 15: // Nodes
          dataset.records = this.parseNodes(lines, currentLine);
          break;
        case 55: // Data at Nodes
          dataset.records = this.parseDataAtNodes(lines, currentLine);
          break;
        case 82: // Tracelines
          dataset.records = this.parseTracelines(lines, currentLine);
          break;
        case 151: // Project Information
          dataset.records = this.parseProjectInfo(lines, currentLine);
          break;
        case 152: // Model Definition
          dataset.records = this.parseModelDef(lines, currentLine);
          break;
        case 164: // Response Function
          dataset.records = this.parseResponseFunction(lines, currentLine);
          break;
        case 2411: // Nodes - Double Precision
          dataset.records = this.parseNodesDouble(lines, currentLine);
          break;
        case 2412: // Elements
          dataset.records = this.parseElements(lines, currentLine);
          break;
        default:
          // 通用解析 - 读取到下一个 "-1" 或文件结束
          dataset.records = this.parseGeneric(lines, currentLine);
      }

      // 找到数据集结束位置
      for (let j = currentLine; j < lines.length; j++) {
        if (lines[j].trim() === '-1' && j > currentLine) {
          endLine = j;
          break;
        }
        if (j === lines.length - 1) {
          endLine = j + 1;
        }
      }

      dataset.endLine = endLine;
    } catch (error) {
      dataset.error = error.message;
      dataset.endLine = currentLine + 100; // 跳过100行
    }

    return dataset;
  }

  /**
   * 解析节点 (Dataset 15)
   */
  parseNodes(lines, startIndex) {
    const nodes = [];
    let i = startIndex;
    
    // 跳过前6行（头部信息）
    i += 6;

    while (i < lines.length) {
      const line = lines[i].trim();
      if (line === '-1' || line === '') {
        i++;
        continue;
      }
      
      // 格式: 4I10, 1P3E13.5
      // node label, coord sys, displacement sys, color, x, y, z
      const parts = lines[i].match(/.{1,10}/g);
      if (parts && parts.length >= 4) {
        const nodeLabel = parseInt(parts[0].trim());
        const coordSys = parseInt(parts[1].trim());
        const dispSys = parseInt(parts[2].trim());
        const color = parseInt(parts[3].trim());
        
        i++;
        if (i < lines.length) {
          const coordParts = lines[i].match(/.{1,13}/g);
          if (coordParts && coordParts.length >= 3) {
            const x = parseFloat(coordParts[0].trim());
            const y = parseFloat(coordParts[1].trim());
            const z = parseFloat(coordParts[2].trim());
            
            nodes.push({
              label: nodeLabel,
              coordSystem: coordSys,
              dispSystem: dispSys,
              color: color,
              x: isNaN(x) ? null : x,
              y: isNaN(y) ? null : y,
              z: isNaN(z) ? null : z
            });
          }
        }
      }
      i++;
      
      // 遇到下一个数据集标记
      if (i < lines.length && lines[i].trim() === '-1') break;
    }

    return { type: 'nodes', count: nodes.length, data: nodes };
  }

  /**
   * 解析双精度节点 (Dataset 2411)
   */
  parseNodesDouble(lines, startIndex) {
    const nodes = [];
    let i = startIndex;

    while (i < lines.length) {
      const line = lines[i].trim();
      if (line === '-1' || line === '') {
        i++;
        continue;
      }

      // Record 1: 4I10
      const parts = lines[i].match(/.{1,10}/g);
      if (parts && parts.length >= 4) {
        const nodeLabel = parseInt(parts[0].trim());
        const exportSys = parseInt(parts[1].trim());
        const dispSys = parseInt(parts[2].trim());
        const color = parseInt(parts[3].trim());

        i++;
        // Record 2: 1P3D25.16
        if (i < lines.length) {
          const coordParts = lines[i].trim().split(/\s+/);
          if (coordParts.length >= 3) {
            const x = parseFloat(coordParts[0]);
            const y = parseFloat(coordParts[1]);
            const z = parseFloat(coordParts[2]);

            nodes.push({
              label: nodeLabel,
              exportSystem: exportSys,
              dispSystem: dispSys,
              color: color,
              x: isNaN(x) ? null : x,
              y: isNaN(y) ? null : y,
              z: isNaN(z) ? null : z
            });
          }
        }
      }
      i++;

      if (i < lines.length && lines[i].trim() === '-1') break;
    }

    return { type: 'nodes_double', count: nodes.length, data: nodes };
  }

  /**
   * 解析单元 (Dataset 2412)
   */
  parseElements(lines, startIndex) {
    const elements = [];
    let i = startIndex;

    while (i < lines.length) {
      const line = lines[i].trim();
      if (line === '-1' || line === '') {
        i++;
        continue;
      }

      // Record 1: 6I10
      const parts = lines[i].match(/.{1,10}/g);
      if (parts && parts.length >= 6) {
        const elementLabel = parseInt(parts[0].trim());
        const feDescriptor = parseInt(parts[1].trim());
        const physProp = parseInt(parts[2].trim());
        const matProp = parseInt(parts[3].trim());
        const color = parseInt(parts[4].trim());
        const numNodes = parseInt(parts[5].trim());

        i++;
        // Record 2: 节点列表
        const nodeLabels = [];
        if (i < lines.length) {
          const nodeParts = lines[i].match(/.{1,10}/g);
          if (nodeParts) {
            for (let j = 0; j < nodeParts.length && j < numNodes; j++) {
              const nodeLabel = parseInt(nodeParts[j].trim());
              if (!isNaN(nodeLabel)) {
                nodeLabels.push(nodeLabel);
              }
            }
          }
        }

        elements.push({
          label: elementLabel,
          feDescriptor: feDescriptor,
          physicalProperty: physProp,
          materialProperty: matProp,
          color: color,
          nodeCount: numNodes,
          nodes: nodeLabels
        });
      }
      i++;

      if (i < lines.length && lines[i].trim() === '-1') break;
    }

    return { type: 'elements', count: elements.length, data: elements };
  }

  /**
   * 解析节点数据 (Dataset 55)
   */
  parseDataAtNodes(lines, startIndex) {
    const result = {
      type: 'data_at_nodes',
      idLines: [],
      parameters: {},
      dataPoints: []
    };

    let i = startIndex;

    // 读取ID行 (Record 1-6)
    for (let j = 0; j < 6 && i < lines.length; j++) {
      const line = lines[i].trim();
      if (line !== '-1') {
        result.idLines.push(line);
      }
      i++;
    }

    // 解析参数 (Record 6)
    if (i < lines.length) {
      const parts = lines[i].match(/.{1,10}/g);
      if (parts && parts.length >= 6) {
        result.parameters = {
          modelType: parseInt(parts[0].trim()),
          analysisType: parseInt(parts[1].trim()),
          dataCharacteristic: parseInt(parts[2].trim()),
          specificDataType: parseInt(parts[3].trim()),
          dataType: parseInt(parts[4].trim()),
          ndv: parseInt(parts[5].trim())
        };
      }
      i++;
    }

    // 读取一些数据点
    const maxPoints = 100;
    while (i < lines.length && result.dataPoints.length < maxPoints) {
      const line = lines[i].trim();
      if (line === '-1') break;
      if (line !== '') {
        const values = line.match(/.{1,13}/g);
        if (values) {
          const dataValues = values.map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
          if (dataValues.length > 0) {
            result.dataPoints.push(dataValues);
          }
        }
      }
      i++;
    }

    result.totalPoints = result.dataPoints.length;
    return result;
  }

  /**
   * 解析轨迹线 (Dataset 82)
   */
  parseTracelines(lines, startIndex) {
    const result = {
      type: 'tracelines',
      lines: []
    };

    let i = startIndex;

    while (i < lines.length) {
      const line = lines[i].trim();
      if (line === '-1' || line === '') {
        i++;
        continue;
      }

      // Record 1: 3I10
      const parts1 = lines[i].match(/.{1,10}/g);
      if (parts1 && parts1.length >= 3) {
        const traceNum = parseInt(parts1[0].trim());
        const numNodes = parseInt(parts1[1].trim());
        const color = parseInt(parts1[2].trim());

        i++;
        // Record 2: 标识行
        const idLine = lines[i] ? lines[i].trim() : '';

        i++;
        // Record 3: 节点列表
        const nodeList = [];
        if (i < lines.length) {
          const nodeParts = lines[i].match(/.{1,10}/g);
          if (nodeParts) {
            for (let j = 0; j < nodeParts.length && j < numNodes; j++) {
              const nodeLabel = parseInt(nodeParts[j].trim());
              if (!isNaN(nodeLabel)) {
                nodeList.push(nodeLabel);
              }
            }
          }
        }

        result.lines.push({
          number: traceNum,
          nodeCount: numNodes,
          color: color,
          idLine: idLine,
          nodes: nodeList
        });
      }
      i++;

      if (i < lines.length && lines[i].trim() === '-1') break;
    }

    return result;
  }

  /**
   * 解析项目信息 (Dataset 151)
   */
  parseProjectInfo(lines, startIndex) {
    const info = {};
    let i = startIndex;

    // 跳过前两行 (-1)
    while (i < lines.length && lines[i].trim() !== '-1') {
      const line = lines[i].trim();
      if (line) {
        const key = `field${Object.keys(info).length + 1}`;
        info[key] = line;
      }
      i++;
      if (Object.keys(info).length >= 10) break;
    }

    return { type: 'project_info', data: info };
  }

  /**
   * 解析模型定义 (Dataset 152)
   */
  parseModelDef(lines, startIndex) {
    const defs = [];
    let i = startIndex;

    while (i < lines.length) {
      const line = lines[i].trim();
      if (line === '-1') break;
      if (line) {
        defs.push(line);
      }
      i++;
      if (defs.length >= 10) break;
    }

    return { type: 'model_def', data: defs };
  }

  /**
   * 解析响应函数 (Dataset 164)
   */
  parseResponseFunction(lines, startIndex) {
    const result = {
      type: 'response_function',
      header: [],
      parameters: {},
      data: []
    };

    let i = startIndex;

    // 跳过 -1 标记和头部
    i += 2;

    // 读取头部信息
    while (i < lines.length && result.header.length < 6) {
      const line = lines[i].trim();
      if (line && line !== '-1') {
        result.header.push(line);
      }
      i++;
    }

    // 参数行
    if (i < lines.length) {
      const parts = lines[i].match(/.{1,10}/g);
      if (parts && parts.length >= 6) {
        result.parameters = {
          responseType: parseInt(parts[0].trim()),
          direction: parseInt(parts[1].trim()),
          responseCode: parseInt(parts[2].trim()),
          responseForm: parseInt(parts[3].trim()),
          inputType: parseInt(parts[4].trim()),
          units: parseInt(parts[5].trim())
        };
      }
      i++;
    }

    // 数据点
    const maxPoints = 100;
    while (i < lines.length && result.data.length < maxPoints) {
      const line = lines[i].trim();
      if (line === '-1') break;
      if (line) {
        const values = line.match(/.{1,13}/g);
        if (values) {
          const dataValues = values.map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
          if (dataValues.length > 0) {
            result.data.push(dataValues);
          }
        }
      }
      i++;
    }

    result.totalPoints = result.data.length;
    return result;
  }

  /**
   * 通用解析
   */
  parseGeneric(lines, startIndex) {
    const data = [];
    let i = startIndex;
    const maxLines = 50;

    while (i < lines.length && data.length < maxLines) {
      const line = lines[i].trim();
      if (line === '-1') break;
      if (line) {
        data.push(line);
      }
      i++;
    }

    return { type: 'generic', data: data };
  }

  /**
   * 生成摘要
   */
  generateSummary(datasets) {
    const summary = {
      datasetTypes: {},
      totalRecords: 0
    };

    for (const ds of datasets) {
      const name = ds.name;
      if (!summary.datasetTypes[name]) {
        summary.datasetTypes[name] = 0;
      }
      summary.datasetTypes[name]++;
      
      if (ds.records && ds.records.count) {
        summary.totalRecords += ds.records.count;
      }
    }

    return summary;
  }
}

module.exports = UNVParser;
