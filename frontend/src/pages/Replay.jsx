import React, { useState, useEffect, useRef } from 'react'
import { Card, Select, Button, Space, Table, InputNumber, Switch, Progress, Tag, message, Descriptions, Collapse } from 'antd'
import { PlayCircleOutlined, StopOutlined } from '@ant-design/icons'
import { getCases, startReplay, stopReplay, getReplayStatus, getReplayResults, getReplayResult } from '../api'

export default function Replay() {
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [repeatCount, setRepeatCount] = useState(1)
  const [stopOnFailure, setStopOnFailure] = useState(true)
  const [replaying, setReplaying] = useState(false)
  const [status, setStatus] = useState(null)
  const [results, setResults] = useState([])
  const [expandedResult, setExpandedResult] = useState(null)
  const timerRef = useRef(null)

  const fetchCases = async () => {
    try {
      const res = await getCases()
      const data = res.data?.data || res.data?.cases || []
      setCases(Array.isArray(data) ? data : [])
    } catch (e) {
      message.error('获取用例列表失败')
    }
  }

  const fetchStatus = async () => {
    try {
      const res = await getReplayStatus()
      const data = res.data?.data || res.data
      setStatus(data)
      setReplaying(data?.replaying || false)
    } catch (e) {
      // 静默
    }
  }

  const fetchResults = async (caseKey) => {
    if (!caseKey) return
    try {
      const res = await getReplayResults(caseKey)
      const data = res.data?.data || res.data?.results || []
      setResults(Array.isArray(data) ? data : [])
    } catch (e) {
      // 静默
    }
  }

  useEffect(() => {
    fetchCases()
    fetchStatus()
  }, [])

  useEffect(() => {
    if (selectedCase) fetchResults(selectedCase)
  }, [selectedCase])

  useEffect(() => {
    if (replaying) {
      timerRef.current = setInterval(fetchStatus, 2000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [replaying])

  const handleStart = async () => {
    if (!selectedCase) { message.warning('请先选择用例'); return }
    try {
      await startReplay({
        case_key: selectedCase,
        repeat: repeatCount,
        stop_on_failure: stopOnFailure,
      })
      message.success('回放已开始')
      setReplaying(true)
    } catch (e) {
      message.error('开始回放失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleStop = async () => {
    try {
      await stopReplay()
      message.success('回放已停止')
      setReplaying(false)
      fetchStatus()
      if (selectedCase) fetchResults(selectedCase)
    } catch (e) {
      message.error('停止回放失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleViewDetail = async (record) => {
    try {
      const res = await getReplayResult(selectedCase, record.timestamp || record.time)
      setExpandedResult(res.data?.data || res.data)
    } catch (e) {
      message.error('获取详情失败')
    }
  }

  const currentStep = status?.current_step || 0
  const totalSteps = status?.total_steps || 0
  const currentRound = status?.current_round || 0
  const totalRounds = status?.total_rounds || repeatCount
  const stepPercent = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0

  const resultColumns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180, render: (v) => v || '-' },
    {
      title: '结果', dataIndex: 'result', key: 'result', width: 80,
      render: (v) => {
        const colorMap = { passed: 'green', failed: 'red' }
        return <Tag color={colorMap[v] || 'default'}>{v || '-'}</Tag>
      }
    },
    { title: '时长', dataIndex: 'duration', key: 'duration', width: 100, render: (v) => v ? `${v}s` : '-' },
    { title: '失败原因', dataIndex: 'error', key: 'error', ellipsis: true, render: (v) => v || '-' },
    {
      title: '操作', key: 'action', width: 80,
      render: (_, record) => <Button type="link" size="small" onClick={() => handleViewDetail(record)}>详情</Button>
    },
  ]

  return (
    <div>
      <h2>回放</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <span style={{ fontWeight: 'bold' }}>选择用例：</span>
          <Select
            style={{ width: 300 }}
            placeholder="请选择要回放的用例"
            value={selectedCase}
            onChange={setSelectedCase}
            disabled={replaying}
            showSearch
            optionFilterProp="label"
            options={cases.map(c => ({ label: `${c.key} - ${c.name}`, value: c.key }))}
          />
          <span>重复次数：</span>
          <InputNumber min={1} max={100} value={repeatCount} onChange={setRepeatCount} disabled={replaying} />
          <span>失败停止：</span>
          <Switch checked={stopOnFailure} onChange={setStopOnFailure} disabled={replaying} />
          {!replaying ? (
            <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleStart}>开始回放</Button>
          ) : (
            <Button danger icon={<StopOutlined />} onClick={handleStop}>停止回放</Button>
          )}
        </Space>

        {replaying && status && (
          <div style={{ marginTop: 16 }}>
            <p>轮次：{currentRound} / {totalRounds}</p>
            <Progress percent={stepPercent} format={() => `${currentStep} / ${totalSteps}`} />
          </div>
        )}
      </Card>

      <div style={{ display: 'flex', gap: 16 }}>
        <Card title="实时预览" style={{ flex: 1 }}>
          <img
            src="/api/tv/stream"
            alt="TV 实时画面"
            style={{ width: '100%', maxHeight: 400, border: '1px solid #d9d9d9', borderRadius: 4, background: '#000' }}
          />
        </Card>

        <Card title="回放结果" style={{ flex: 1 }}>
          <Table
            columns={resultColumns}
            dataSource={results}
            rowKey={(r) => r.timestamp || r.time || Math.random()}
            size="small"
            pagination={{ pageSize: 10 }}
          />
        </Card>
      </div>

      {expandedResult && (
        <Card title="回放详情" style={{ marginTop: 16 }}>
          <Collapse
            items={(expandedResult.steps || []).map((step, i) => ({
              key: i,
              label: `步骤 ${i + 1}: ${step.type || ''} - ${step.result || ''}`,
              children: (
                <Descriptions column={1} size="small" bordered>
                  {Object.entries(step).map(([k, v]) => (
                    <Descriptions.Item key={k} label={k}>
                      {typeof v === 'object' ? <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(v, null, 2)}</pre> : String(v ?? '')}
                    </Descriptions.Item>
                  ))}
                </Descriptions>
              )
            }))}
          />
        </Card>
      )}
    </div>
  )
}
