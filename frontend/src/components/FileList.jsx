import React from 'react'
import './FileList.css'

function FileList({ files }) {
  if (!files || files.length === 0) {
    return (
      <div className="file-list-container">
        <div className="file-list-header">
          <h3>已识别文件</h3>
        </div>
        <div className="file-list-empty">
          <p>暂无文件</p>
        </div>
      </div>
    )
  }

  const getFileIcon = (fileName) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    switch (ext) {
      case 'csv':
        return '📊'
      case 'pdf':
        return '📄'
      case 'doc':
      case 'docx':
        return '📝'
      case 'xls':
      case 'xlsx':
        return '📈'
      case 'txt':
        return '📃'
      default:
        return '📎'
    }
  }

  const formatFileSize = (bytes) => {
    if (!bytes) return '未知'
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  return (
    <div className="file-list-container">
      <div className="file-list-header">
        <h3>已识别文件</h3>
        <span className="file-count">{files.length}</span>
      </div>
      <div className="file-list-content">
        {files.map((file, index) => (
          <div key={index} className="file-item">
            <div className="file-icon">{getFileIcon(file.name)}</div>
            <div className="file-info">
              <div className="file-name" title={file.name}>
                {file.name}
              </div>
              {file.size && (
                <div className="file-size">{formatFileSize(file.size)}</div>
              )}
              {file.uploadTime && (
                <div className="file-time">{file.uploadTime}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default FileList





