import React, { useState, useEffect } from 'react'
import { Card, Button, Space, Table, Input, Tag, message, Alert, List } from 'antd'
import { SyncOutlined, SendOutlined, HistoryOutlined } from '@ant-design/icons'
import { gitStatus, gitCommit, gitPull, gitLog } from '../api'

export default function GitCollab() {
  const [status, setStatus] = useState(null)
  const [log, setLog] = useState([])
  const [commitMsg, setCommitMsg] = useState('')
  const [loading, setLoading] = useState(false)
  const [pullLoading, setPullLoading] = useState(false)

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
    setLoading(true)
    try {
      await gitCommit({ message: commitMsg })
      message.success('提交成功')
      setCommitMsg('')
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
          <Card type="inner" title="变更文件列表" style={{ marginBottom: 16 }}>
            <List
              size="small"
              dataSource={changedFiles}
              renderItem={(item) => (
                <List.Item>
                  <Tag color={
                    (item.status || item.type) === 'modified' ? 'blue' :
                    (item.status || item.type) === 'added' || (item.status || item.type) === 'new' ? 'green' :
                    (item.status || item.type) === 'deleted' ? 'red' : 'default'
                  }>
                    {item.status || item.type || '变更'}
                  </Tag>
                  {item.file || item.path || item}
                </List.Item>
              )}
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
          <Button type="primary" icon={<SendOutlined />} onClick={handleCommit} loading={loading} disabled={!hasChanges}>
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
    </div>
  )
}
