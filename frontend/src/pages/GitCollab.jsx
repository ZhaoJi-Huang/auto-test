import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Input, Tag, message, Alert, List, Modal, Checkbox } from 'antd'
import { SyncOutlined, SendOutlined, HistoryOutlined } from '@ant-design/icons'
import { gitStatus, gitCommit, gitPull, gitLog, gitFileContent } from '../api'

export default function GitCollab() {
  const [status, setStatus] = useState(null)
  const [log, setLog] = useState([])
  const [commitMsg, setCommitMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [pullLoading, setPullLoading] = useState(false)
  const [fileModalVisible, setFileModalVisible] = useState(false)
  const [selectedFile, setSelectedFile] = useState('')
  const [fileContent, setFileContent] = useState('')
  const [selectedFiles, setSelectedFiles] = useState([])

  const fetchStatus = async () => {
    try {
      const res = await gitStatus()
      setStatus(res.data?.data || res.data)
    } catch (e) {
      message.error('获取 Git 状态失败')
    }
  }

  const fetchLog = async () => {
    try {
      const res = await gitLog()
      const data = res.data?.data || res.data?.commits || []
      setLog(Array.isArray(data) ? data : [])
    } catch (e) {
      message.error('获取提交历史失败')
    }
  }

  useEffect(() => {
    fetchStatus()
    fetchLog()
  }, [])

  const handleCommit = async () => {
    if (!commitMsg.trim()) { message.warning('请输入提交说明'); return }
    if (selectedFiles.length === 0) { message.warning('请选择要提交的文件'); return }
    setLoading(true)
    try {
      await gitCommit({ message: commitMsg, files: selectedFiles })
      message.success('提交成功')
      setCommitMsg('')
      setSelectedFiles([])
      fetchStatus()
      fetchLog()
    } catch (e) {
      message.error('提交失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handlePull = async () => {
    setPullLoading(true)
    try {
      const res = await gitPull()
      message.success('同步完成: ' + (res.data?.message || ''))
      fetchStatus()
      fetchLog()
    } catch (e) {
      message.error('同步失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setPullLoading(false)
    }
  }

  const handleFileClick = async (fileName) => {
    setSelectedFile(fileName)
    setFileContent('')
    setFileModalVisible(true)
    try {
      const res = await gitFileContent(fileName)
      setFileContent(res.data?.data?.content ?? '无法读取内容')
    } catch (e) {
      setFileContent('读取失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const changedFiles = status?.files || status?.changed_files || []
  const hasChanges = changedFiles.length > 0 || status?.has_changes

  const logColumns = [
    { title: '提交 ID', dataIndex: 'hash', key: 'hash', width: 100, render: (v) => v ? v.substring(0, 7) : '-' },
    { title: '提交说明', dataIndex: 'message', key: 'message', ellipsis: true },
    { title: '作者', dataIndex: 'author', key: 'author', width: 120 },
    { title: '时间', dataIndex: 'date', key: 'date', width: 180 },
  ]

  return (
    <div>
      <h2>Git 协作</h2>

      <Card title="Git 状态" style={{ marginBottom: 16 }}>
        {hasChanges ? (
          <Alert type="warning" message="有待提交的变更" showIcon style={{ marginBottom: 16 }} />
        ) : (
          <Alert type="success" message="工作区干净，无待提交变更" showIcon style={{ marginBottom: 16 }} />
        )}

        {changedFiles.length > 0 && (
          <Card type="inner" title={
            <Space>
              <span>变更文件列表</span>
              <Checkbox
                checked={selectedFiles.length === changedFiles.length && changedFiles.length > 0}
                indeterminate={selectedFiles.length > 0 && selectedFiles.length < changedFiles.length}
                onChange={(e) => {
                  setSelectedFiles(e.target.checked ? changedFiles.map(f => f.file || f.path || f) : [])
                }}
              >全选</Checkbox>
            </Space>
          } style={{ marginBottom: 16 }}>
            <List
              size="small"
              dataSource={changedFiles}
              renderItem={(item) => {
                const fileName = item.file || item.path || item
                const checked = selectedFiles.includes(fileName)
                return (
                  <List.Item style={{ cursor: 'pointer' }}>
                    <Checkbox
                      checked={checked}
                      onChange={(e) => {
                        setSelectedFiles(prev =>
                          e.target.checked ? [...prev, fileName] : prev.filter(f => f !== fileName)
                        )
                      }}
                      style={{ marginRight: 8 }}
                    />
                    <span onClick={() => handleFileClick(fileName)} style={{ flex: 1 }}>
                      <Tag color={
                        (item.status || item.type) === 'modified' ? 'blue' :
                        (item.status || item.type) === 'added' || (item.status || item.type) === 'new' ? 'green' :
                        (item.status || item.type) === 'deleted' ? 'red' : 'default'
                      }>
                        {item.status || item.type || '变更'}
                      </Tag>
                      {fileName}
                    </span>
                  </List.Item>
                )
              }}
            />
          </Card>
        )}

        <Space>
          <Input.TextArea
            placeholder="输入提交说明"
            value={commitMsg}
            onChange={e => setCommitMsg(e.target.value)}
            style={{ width: 400 }}
            rows={2}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={handleCommit} loading={loading} disabled={!hasChanges || selectedFiles.length === 0}>
            提交
          </Button>
          <Button icon={<SyncOutlined />} onClick={handlePull} loading={pullLoading}>
            同步 (Pull)
          </Button>
        </Space>
      </Card>

      <Card title="提交历史">
        <Table
          columns={logColumns}
          dataSource={log}
          rowKey={(r) => r.hash || Math.random()}
          size="small"
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title={selectedFile}
        open={fileModalVisible}
        onCancel={() => setFileModalVisible(false)}
        footer={null}
        width={800}
      >
        <pre style={{ maxHeight: 500, overflow: 'auto', background: '#f5f5f5', padding: 12, borderRadius: 4, fontSize: 13 }}>
          {fileContent || '加载中...'}
        </pre>
      </Modal>
    </div>
  )
}
