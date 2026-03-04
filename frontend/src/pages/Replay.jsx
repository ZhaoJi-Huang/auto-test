import React, { useState, useEffect, useRef } from 'react'
import {
  Card, Select, Button, Space, Table, InputNumber, Switch, Progress, Tag, Tabs,
  message, Collapse, Image, Row, Col, Statistic, Badge, Timeline, Modal, Empty, Tooltip
} from 'antd'
import {
  PlayCircleOutlined, StopOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ClockCircleOutlined, EyeOutlined, WarningOutlined, ExclamationCircleOutlined,
  ReloadOutlined, FileTextOutlined, HistoryOutlined
} from '@ant-design/icons'
import { getCases, getCase, startReplay, stopReplay, getReplayStatus, getReplayResults, getReplayResult, getRunResult } from '../api'

// 步骤截图 URL：通过后端 API 获取
const getScreenshotUrl = (screenshotPath) => {
  if (!screenshotPath) return null
  // 从绝对路径中提取 case_key/timestamp/filename
  // 路径格式: .../replay/CASE-KEY/TIMESTAMP/step_N.png
  const parts = screenshotPath.replace(/\\/g, '/').split('/')
  const replayIdx = parts.lastIndexOf('replay')
  if (replayIdx < 0 || replayIdx + 3 >= parts.length) return null
  const caseKey = parts[replayIdx + 1]
  const timestamp = parts[replayIdx + 2]
  const filename = parts.slice(replayIdx + 3).join('/')
  return `/api/tv/replay/screenshot/${caseKey}/${timestamp}/${filename}`
}

const statusConfig = {
  passed: { color: 'success', icon: <CheckCircleOutlined />, text: '通过', tagColor: 'green' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败', tagColor: 'red' },
  warning: { color: 'warning', icon: <WarningOutlined />, text: '警告', tagColor: 'orange' },
  aborted: { color: 'default', icon: <ExclamationCircleOutlined />, text: '中止', tagColor: 'default' },
  error: { color: 'error', icon: <CloseCircleOutlined />, text: '异常', tagColor: 'red' },
  skipped: { color: 'default', icon: <ClockCircleOutlined />, text: '跳过', tagColor: 'default' },
}

const stepTypeLabels = {
  key_group: '按键操作',
  adb_command: 'ADB 命令',
  ai_navigate: 'AI 导航',
  ai_verify: 'AI 验证',
}

function StatusTag({ status }) {
  const cfg = statusConfig[status] || { tagColor: 'default', text: status || '-' }
  return <Tag color={cfg.tagColor} icon={cfg.icon}>{cfg.text}</Tag>
}

export default function Replay() {
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [repeatCount, setRepeatCount] = useState(1)
  const [stopOnFailure, setStopOnFailure] = useState(true)
  const [replaying, setReplaying] = useState(false)
  const [status, setStatus] = useState(null)
  const [results, setResults] = useState([])
  const [detailVisible, setDetailVisible] = useState(false)
  const [detailData, setDetailData] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [caseDetail, setCaseDetail] = useState(null)
  const [rightTab, setRightTab] = useState('info')
  const [selectedRun, setSelectedRun] = useState(null)
  const [runDetailData, setRunDetailData] = useState(null)
  const [runDetailLoading, setRunDetailLoading] = useState(false)
  const [detailTimestamp, setDetailTimestamp] = useState(null)
  const timerRef = useRef(null)

  const fetchCaseDetail = async (caseKey) => {
    if (!caseKey) { setCaseDetail(null); return }
    try {
      const res = await getCase(caseKey)
      setCaseDetail(res.data?.data || null)
    } catch (e) {
      setCaseDetail(null)
    }
  }

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
      setReplaying(data?.is_replaying || false)
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
    if (selectedCase) {
      fetchResults(selectedCase)
      fetchCaseDetail(selectedCase)
    } else {
      setCaseDetail(null)
    }
  }, [selectedCase])

  useEffect(() => {
    if (replaying) {
      timerRef.current = setInterval(() => {
        fetchStatus()
        if (selectedCase) fetchResults(selectedCase)
      }, 2000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [replaying, selectedCase])

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

  const handleViewRunDetail = async (runIndex) => {
    if (!detailData || !selectedCase) return
    setSelectedRun(runIndex)
    setRunDetailLoading(true)
    try {
      const res = await getRunResult(selectedCase, detailTimestamp, runIndex)
      setRunDetailData(res.data?.data || res.data)
    } catch (e) {
      message.error(`获取第 ${runIndex} 轮详情失败`)
      setRunDetailData(null)
    } finally {
      setRunDetailLoading(false)
    }
  }

  const handleViewDetail = async (record) => {
    setDetailLoading(true)
    setDetailVisible(true)
    const ts = record.timestamp || record.time
    setDetailTimestamp(ts)
    try {
      const res = await getReplayResult(selectedCase, ts)
      setDetailData(res.data?.data || res.data)
    } catch (e) {
      message.error('获取详情失败')
    } finally {
      setDetailLoading(false)
    }
  }

  const currentStep = status?.current_step || 0
  const totalSteps = status?.total_steps || 0
  const currentRound = status?.current_run || 0
  const totalRounds = status?.total_runs || repeatCount
  const stepPercent = totalSteps > 0 ? Math.round((currentStep / totalSteps) * 100) : 0

  const resultColumns = [
    {
      title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 170,
      render: (v) => {
        if (!v) return '-'
        // 格式化 20260227_155903 → 2026-02-27 15:59:03
        const m = v.match(/^(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})$/)
        return m ? `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]}` : v
      }
    },
    {
      title: '结果', dataIndex: 'result', key: 'result', width: 100,
      render: (v) => <StatusTag status={v} />
    },
    {
      title: '步骤', dataIndex: 'total_steps', key: 'total_steps', width: 60,
      render: (v) => v || '-'
    },
    {
      title: '时长', dataIndex: 'duration_s', key: 'duration_s', width: 90,
      render: (v) => v ? `${v.toFixed(1)}s` : '-'
    },
    {
      title: '操作', key: 'action', width: 80,
      render: (_, record) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record)}>
          详情
        </Button>
      )
    },
  ]

  // 渲染按键组详情
  const renderKeyGroupInfo = (step) => {
    const commands = step.commands || []
    const intervalMs = step.interval_ms || 0
    if (commands.length === 0) return null

    const isSingleKey = commands.length === 1
    const cmd = commands[0] || {}

    if (isSingleKey) {
      if (cmd.is_long_press) {
        return (
          <div style={{ padding: '8px 12px', background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff', fontSize: 13 }}>
            <span style={{ fontWeight: 500 }}>长按</span>{' '}
            <Tag color="blue" style={{ margin: '0 4px' }}>{cmd.key}</Tag>
            <span style={{ color: '#666' }}>
              {cmd.duration_ms ? `${(cmd.duration_ms / 1000).toFixed(1)}s` : ''}
            </span>
          </div>
        )
      }
      return (
        <div style={{ padding: '8px 12px', background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff', fontSize: 13 }}>
          <span style={{ fontWeight: 500 }}>按键</span>{' '}
          <Tag color="blue" style={{ margin: '0 4px' }}>{cmd.key}</Tag>
        </div>
      )
    }

    // 多个按键
    const keyNames = commands.map(c => c.key)
    // 检查是否所有按键相同（连续短按同一键）
    const allSame = keyNames.every(k => k === keyNames[0])

    return (
      <div style={{ padding: '8px 12px', background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff', fontSize: 13 }}>
        {allSame ? (
          <>
            <span style={{ fontWeight: 500 }}>连续按</span>{' '}
            <Tag color="blue" style={{ margin: '0 4px' }}>{keyNames[0]}</Tag>
            <span style={{ color: '#666' }}>× {commands.length} 次</span>
          </>
        ) : (
          <>
            <span style={{ fontWeight: 500 }}>组合按键</span>{' '}
            {commands.map((c, i) => (
              <span key={i}>
                <Tag color={c.is_long_press ? 'orange' : 'blue'} style={{ margin: '0 2px' }}>
                  {c.key}{c.is_long_press ? ` (长按${c.duration_ms ? (c.duration_ms/1000).toFixed(1)+'s' : ''})` : ''}
                </Tag>
                {i < commands.length - 1 && <span style={{ color: '#ccc', margin: '0 2px' }}>→</span>}
              </span>
            ))}
          </>
        )}
        {intervalMs > 0 && (
          <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>
            间隔 {intervalMs}ms
          </span>
        )}
      </div>
    )
  }

  // 渲染 AI 导航详情（展示每一轮操作）
  const renderAiNavigateInfo = (step) => {
    const rounds = step.rounds || []
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {step.prompt && (
          <div style={{ padding: '8px 12px', background: '#f9f0ff', borderRadius: 6, border: '1px solid #d3adf7', fontSize: 13 }}>
            <span style={{ fontWeight: 500, color: '#722ed1' }}>指令：</span>{step.prompt}
          </div>
        )}
        {rounds.length > 0 && (
          <div style={{ padding: '8px 12px', background: '#f6ffed', borderRadius: 6, border: '1px solid #b7eb8f', fontSize: 13 }}>
            <div style={{ fontWeight: 500, marginBottom: 6, color: '#389e0d' }}>
              AI 执行过程（共 {rounds.length} 轮）
            </div>
            {rounds.map((r, i) => {
              const parsed = r.parsed || {}
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderTop: i > 0 ? '1px solid #e8f5e0' : 'none' }}>
                  <Tag style={{ margin: 0, minWidth: 44, textAlign: 'center' }}>{`#${r.round || i + 1}`}</Tag>
                  {parsed.action && parsed.action !== 'none' && (
                    <Tag color="blue" style={{ margin: 0 }}>{parsed.action}</Tag>
                  )}
                  {parsed.done && <Tag color="green" style={{ margin: 0 }}>完成</Tag>}
                  {parsed.reason && <span style={{ color: '#666', fontSize: 12 }}>{parsed.reason}</span>}
                  {r.error && <span style={{ color: '#f5222d', fontSize: 12 }}>{r.error}</span>}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  // 渲染 ADB 命令详情
  const renderAdbCommandInfo = (step) => {
    return (
      <div style={{ padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, border: '1px solid #e8e8e8', fontSize: 13 }}>
        {step.description && <div style={{ fontWeight: 500, marginBottom: 4 }}>{step.description}</div>}
        <code style={{ color: '#d46b08', fontSize: 12, wordBreak: 'break-all' }}>{step.command}</code>
        {step.output && <div style={{ marginTop: 4, color: '#666', fontSize: 12, whiteSpace: 'pre-wrap' }}>{step.output}</div>}
      </div>
    )
  }

  // 渲染 AI 校验详情
  const renderAiVerifyInfo = (step) => {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {step.prompt && (
          <div style={{ padding: '8px 12px', background: '#f9f0ff', borderRadius: 6, border: '1px solid #d3adf7', fontSize: 13 }}>
            <span style={{ fontWeight: 500, color: '#722ed1' }}>校验条件：</span>{step.prompt}
          </div>
        )}
        {step.ai_reason && (
          <div style={{
            padding: '8px 12px', borderRadius: 6, fontSize: 13,
            background: step.ai_passed ? '#f6ffed' : '#fff2f0',
            border: `1px solid ${step.ai_passed ? '#b7eb8f' : '#ffccc7'}`,
          }}>
            <span style={{ fontWeight: 500 }}>AI 判断：</span>{step.ai_reason}
            {step.ai_confidence != null && (
              <span style={{ marginLeft: 8, color: '#999' }}>置信度: {(step.ai_confidence * 100).toFixed(0)}%</span>
            )}
          </div>
        )}
      </div>
    )
  }

  // 详情弹窗中的步骤渲染
  const renderStepDetail = (step, index) => {
    const screenshotUrl = getScreenshotUrl(step.screenshot)

    return (
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        {/* 截图区域 */}
        <div style={{ flexShrink: 0 }}>
          {screenshotUrl ? (
            <Image
              src={screenshotUrl}
              alt={`步骤 ${index + 1} 截图`}
              width={320}
              style={{ borderRadius: 4, border: '1px solid #f0f0f0' }}
              placeholder={<div style={{ width: 320, height: 180, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>加载中...</div>}
              fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjE4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiM5OTkiIGZvbnQtc2l6ZT0iMTQiPuaXoOaIquWbvjwvdGV4dD48L3N2Zz4="
            />
          ) : (
            <div style={{
              width: 320, height: 180, background: '#fafafa', borderRadius: 4,
              border: '1px dashed #d9d9d9', display: 'flex', alignItems: 'center',
              justifyContent: 'center', color: '#bbb'
            }}>
              无截图
            </div>
          )}
        </div>

        {/* 信息区域 */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Space size="middle">
            <StatusTag status={step.status} />
            <Tag>{stepTypeLabels[step.step_type] || step.step_type}</Tag>
            {step.duration_s != null && (
              <span style={{ color: '#999', fontSize: 13 }}>
                <ClockCircleOutlined style={{ marginRight: 4 }} />
                {step.duration_s.toFixed(1)}s
              </span>
            )}
          </Space>

          {/* 按步骤类型渲染详细信息 */}
          {step.step_type === 'key_group' && renderKeyGroupInfo(step)}
          {step.step_type === 'adb_command' && renderAdbCommandInfo(step)}
          {step.step_type === 'ai_navigate' && renderAiNavigateInfo(step)}
          {step.step_type === 'ai_verify' && renderAiVerifyInfo(step)}

          {step.reason && (
            <div style={{
              padding: '8px 12px', borderRadius: 6, fontSize: 13, color: '#333', wordBreak: 'break-all',
              background: step.status === 'failed' ? '#fff2f0' : '#fffbe6',
              border: `1px solid ${step.status === 'failed' ? '#ffccc7' : '#ffe58f'}`,
            }}>
              {step.reason}
            </div>
          )}
        </div>
      </div>
    )
  }

  return (
    <div style={{ padding: '0 0 24px' }}>
      <h2 style={{ marginBottom: 16 }}>回放</h2>

      {/* 控制面板 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Space size="middle" wrap>
              <Select
                style={{ width: 320 }}
                placeholder="选择要回放的用例"
                value={selectedCase}
                onChange={setSelectedCase}
                disabled={replaying}
                showSearch
                optionFilterProp="label"
                options={cases.map(c => ({ label: `${c.key} - ${c.name}`, value: c.key }))}
                allowClear
              />
              <Tooltip title="重复回放次数">
                <Space size={4}>
                  <ReloadOutlined style={{ color: '#999' }} />
                  <InputNumber min={1} max={100} value={repeatCount} onChange={setRepeatCount} disabled={replaying} style={{ width: 70 }} />
                </Space>
              </Tooltip>
              <Tooltip title="遇到失败步骤时停止回放">
                <Space size={4}>
                  <span style={{ color: '#999', fontSize: 13 }}>失败停止</span>
                  <Switch size="small" checked={stopOnFailure} onChange={setStopOnFailure} disabled={replaying} />
                </Space>
              </Tooltip>
            </Space>
          </Col>
          <Col>
            {!replaying ? (
              <Button type="primary" size="large" icon={<PlayCircleOutlined />} onClick={handleStart} disabled={!selectedCase}>
                开始回放
              </Button>
            ) : (
              <Button danger size="large" icon={<StopOutlined />} onClick={handleStop}>
                停止回放
              </Button>
            )}
          </Col>
        </Row>

        {/* 回放进度 */}
        {replaying && status && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #f0f0f0' }}>
            <Row gutter={16} align="middle">
              <Col>
                <Badge status="processing" text={
                  <span style={{ fontSize: 13 }}>
                    正在回放 · 轮次 <b>{currentRound}</b> / {totalRounds}
                  </span>
                } />
              </Col>
              <Col flex="auto">
                <Progress
                  percent={stepPercent}
                  format={() => `步骤 ${currentStep} / ${totalSteps}`}
                  strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
                  size="small"
                />
              </Col>
            </Row>
          </div>
        )}
      </Card>

      {/* 主体内容 */}
      <Row gutter={16}>
        <Col span={12}>
          <Card
            title="实时预览"
            size="small"
            bodyStyle={{ padding: 8 }}
          >
            <img
              src="/api/tv/stream"
              alt="TV 实时画面"
              style={{
                width: '100%', display: 'block', borderRadius: 4,
                background: '#000', minHeight: 200
              }}
            />
          </Card>
        </Col>

        <Col span={12}>
          {/* 回放中：显示步骤进度列表 */}
          {replaying && status?.steps_overview?.length > 0 ? (
            <Card
              title={<Space>步骤进度<Tag color="processing">{currentStep} / {totalSteps}</Tag></Space>}
              size="small"
              bodyStyle={{ padding: 0 }}
            >
              <div style={{ maxHeight: 420, overflow: 'auto' }}>
                {(status.steps_overview || []).map((s, i) => {
                  const stepNum = i + 1
                  const isDone = stepNum < currentStep
                  const isCurrent = stepNum === currentStep
                  const isPending = stepNum > currentStep
                  const stepResult = (status.step_results || [])[i]
                  const stepStatus = stepResult?.status

                  let statusIcon = <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
                  let bgColor = 'transparent'
                  if (isCurrent) {
                    statusIcon = <Badge status="processing" />
                    bgColor = '#e6f4ff'
                  } else if (isDone) {
                    if (stepStatus === 'passed') {
                      statusIcon = <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    } else if (stepStatus === 'failed' || stepStatus === 'error') {
                      statusIcon = <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
                    } else if (stepStatus === 'warning') {
                      statusIcon = <WarningOutlined style={{ color: '#faad14' }} />
                    } else {
                      statusIcon = <CheckCircleOutlined style={{ color: '#52c41a' }} />
                    }
                  }

                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 14px',
                        borderBottom: '1px solid #f5f5f5',
                        background: bgColor,
                        opacity: isPending ? 0.5 : 1,
                        transition: 'all 0.3s',
                      }}
                    >
                      <span style={{ flexShrink: 0, width: 20, display: 'flex', justifyContent: 'center' }}>
                        {statusIcon}
                      </span>
                      <span style={{
                        flexShrink: 0, width: 36,
                        fontWeight: 500, fontSize: 13,
                        color: isCurrent ? '#1677ff' : isPending ? '#bbb' : '#333'
                      }}>
                        {stepNum}
                      </span>
                      <Tag
                        color={isPending ? 'default' : 'blue'}
                        style={{ margin: 0, fontSize: 11 }}
                      >
                        {stepTypeLabels[s.type] || s.type}
                      </Tag>
                      <span style={{
                        flex: 1, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        color: isCurrent ? '#1677ff' : isPending ? '#bbb' : '#555'
                      }}>
                        {s.summary}
                      </span>
                      {isDone && stepResult?.duration_s != null && (
                        <span style={{ flexShrink: 0, fontSize: 11, color: '#999' }}>
                          {stepResult.duration_s.toFixed(1)}s
                        </span>
                      )}
                      {isCurrent && (
                        <span style={{ flexShrink: 0, fontSize: 11, color: '#1677ff', fontWeight: 500 }}>
                          执行中...
                        </span>
                      )}
                    </div>
                  )
                })}
              </div>
            </Card>
          ) : (
            <Card size="small" bodyStyle={{ padding: 0 }}>
              <Tabs
                activeKey={rightTab}
                onChange={setRightTab}
                size="small"
                style={{ marginBottom: 0 }}
                tabBarStyle={{ margin: '0 16px' }}
                items={[
                  {
                    key: 'info',
                    label: <span><FileTextOutlined /> 用例信息</span>,
                    children: selectedCase && caseDetail ? (
                      <div style={{ maxHeight: 420, overflow: 'auto', padding: '0 16px 12px' }}>
                        {/* 基本信息 */}
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>
                            {caseDetail.summary || caseDetail.key}
                          </div>
                          <Space size={[4, 4]} wrap>
                            {caseDetail.priority && <Tag color="orange">{caseDetail.priority}</Tag>}
                            {caseDetail.source && <Tag>{caseDetail.source === 'jira' ? 'Jira' : '本地'}</Tag>}
                            {caseDetail.issuetype && <Tag>{caseDetail.issuetype}</Tag>}
                          </Space>
                        </div>

                        {/* 用例路径 */}
                        {caseDetail.customfield_10107 && (
                          <div style={{ fontSize: 12, color: '#888', marginBottom: 10, wordBreak: 'break-all' }}>
                            {caseDetail.customfield_10107}
                          </div>
                        )}

                        {/* 前置条件 */}
                        {caseDetail.precondition && (
                          <div style={{
                            padding: '10px 12px', marginBottom: 12,
                            background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6,
                          }}>
                            <div style={{ fontWeight: 500, fontSize: 13, color: '#ad6800', marginBottom: 4 }}>
                              <WarningOutlined style={{ marginRight: 4 }} />前置条件
                            </div>
                            <div style={{ fontSize: 13, color: '#333', whiteSpace: 'pre-wrap' }}>
                              {caseDetail.precondition}
                            </div>
                          </div>
                        )}

                        {/* Jira 测试步骤 */}
                        {caseDetail.test_steps?.length > 0 && (
                          <div style={{ marginBottom: 12 }}>
                            <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6, color: '#555' }}>
                              测试步骤
                            </div>
                            {caseDetail.test_steps.map((ts, i) => (
                              <div key={i} style={{
                                padding: '8px 12px', marginBottom: 6,
                                background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 6, fontSize: 13,
                              }}>
                                <div style={{ color: '#333', whiteSpace: 'pre-wrap' }}>{ts.step}</div>
                                {ts.expectedResult && (
                                  <div style={{ marginTop: 6, padding: '6px 10px', background: '#f6ffed', borderRadius: 4, border: '1px solid #d9f7be' }}>
                                    <span style={{ color: '#389e0d', fontWeight: 500, fontSize: 12 }}>期望结果：</span>
                                    <span style={{ color: '#555', fontSize: 12, whiteSpace: 'pre-wrap' }}>{ts.expectedResult}</span>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* 录制步骤预览 */}
                        {caseDetail.recorded_steps?.length > 0 && (
                          <div>
                            <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6, color: '#555' }}>
                              录制步骤 <Tag style={{ marginLeft: 4 }}>{caseDetail.recorded_steps.length} 步</Tag>
                            </div>
                            {caseDetail.recorded_steps.map((s, i) => {
                              const sType = s.type || ''
                              let summary = ''
                              if (sType === 'key_group') {
                                const cmds = s.commands || []
                                if (cmds.length === 1) {
                                  const c = cmds[0]
                                  summary = c.is_long_press ? `长按 ${c.key}` : c.key
                                } else if (cmds.length > 1) {
                                  const keys = cmds.map(c => c.key)
                                  summary = keys.every(k => k === keys[0])
                                    ? `${keys[0]} x${cmds.length}`
                                    : keys.join(' → ')
                                  if (s.interval_ms) summary += ` (${s.interval_ms}ms)`
                                }
                              } else if (sType === 'adb_command') {
                                summary = s.description || s.command || ''
                              } else if (sType === 'ai_navigate' || sType === 'ai_verify') {
                                const p = s.prompt || ''
                                summary = p.length > 40 ? p.slice(0, 40) + '...' : p
                              }
                              return (
                                <div key={i} style={{
                                  display: 'flex', alignItems: 'center', gap: 8,
                                  padding: '6px 12px', borderBottom: '1px solid #f5f5f5',
                                }}>
                                  <span style={{ flexShrink: 0, width: 28, fontSize: 12, color: '#999', textAlign: 'center' }}>{i + 1}</span>
                                  <Tag color="default" style={{ margin: 0, fontSize: 11 }}>{stepTypeLabels[sType] || sType}</Tag>
                                  <span style={{ flex: 1, fontSize: 12, color: '#555', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{summary}</span>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    ) : (
                      <Empty description="请选择用例" style={{ padding: '40px 0' }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ),
                  },
                  {
                    key: 'history',
                    label: <span><HistoryOutlined /> 回放记录{results.length > 0 && <Tag style={{ marginLeft: 4 }}>{results.length}</Tag>}</span>,
                    children: results.length > 0 ? (
                      <Table
                        columns={resultColumns}
                        dataSource={results}
                        rowKey={(r) => r.timestamp || r.time || Math.random()}
                        size="small"
                        pagination={{ pageSize: 8, size: 'small' }}
                        style={{ margin: 0 }}
                      />
                    ) : (
                      <Empty description="暂无回放结果" style={{ padding: '40px 0' }} image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    ),
                  },
                ]}
              />
            </Card>
          )}
        </Col>
      </Row>

      {/* 详情弹窗 */}
      <Modal
        title={
          detailData ? (
            <Space>
              <span>回放详情</span>
              <StatusTag status={detailData.result} />
              {detailData.duration_s != null && (
                <span style={{ color: '#999', fontSize: 13, fontWeight: 'normal' }}>
                  总耗时 {detailData.duration_s.toFixed(1)}s
                </span>
              )}
            </Space>
          ) : '回放详情'
        }
        open={detailVisible}
        onCancel={() => { setDetailVisible(false); setDetailData(null); setSelectedRun(null); setRunDetailData(null); setDetailTimestamp(null) }}
        footer={null}
        width={860}
        loading={detailLoading}
        destroyOnClose
      >
        {detailData && detailData.steps && (
          <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
            {/* 概要统计 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="总步骤" value={detailData.total_steps || detailData.steps.length} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="通过"
                    value={detailData.steps.filter(s => s.status === 'passed').length}
                    valueStyle={{ color: '#3f8600' }}
                    prefix={<CheckCircleOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="失败"
                    value={detailData.steps.filter(s => s.status === 'failed' || s.status === 'error').length}
                    valueStyle={{ color: '#cf1322' }}
                    prefix={<CloseCircleOutlined />}
                  />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="总耗时"
                    value={detailData.duration_s ? `${detailData.duration_s.toFixed(1)}s` : '-'}
                    prefix={<ClockCircleOutlined />}
                  />
                </Card>
              </Col>
            </Row>

            {/* 回放视频 */}
            {detailData.has_video && detailData.video_url && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ fontWeight: 500, fontSize: 13, color: '#555' }}>
                    <PlayCircleOutlined style={{ marginRight: 4 }} />回放视频
                  </span>
                  <a href={detailData.video_url} download="replay.mp4" style={{ fontSize: 12 }}>下载视频</a>
                </div>
                <video
                  src={detailData.video_url}
                  controls
                  preload="metadata"
                  style={{ width: '100%', borderRadius: 6, background: '#000', maxHeight: 360 }}
                >
                  浏览器不支持该视频格式，请<a href={detailData.video_url} download="replay.mp4">下载</a>观看
                </video>
              </div>
            )}

            {/* 步骤列表 */}
            <Collapse
              defaultActiveKey={
                // 默认展开失败的步骤
                detailData.steps
                  .map((s, i) => (s.status === 'failed' || s.status === 'error') ? String(i) : null)
                  .filter(Boolean)
              }
              items={detailData.steps.map((step, i) => {
                // 生成步骤摘要文字
                let stepSummary = ''
                if (step.step_type === 'key_group') {
                  const cmds = step.commands || []
                  if (cmds.length === 1) {
                    const c = cmds[0] || {}
                    stepSummary = c.is_long_press
                      ? `长按 ${c.key} ${c.duration_ms ? (c.duration_ms/1000).toFixed(1)+'s' : ''}`
                      : c.key
                  } else if (cmds.length > 1) {
                    const keys = cmds.map(c => c.key)
                    const allSame = keys.every(k => k === keys[0])
                    stepSummary = allSame ? `${keys[0]} ×${cmds.length}` : keys.join(' → ')
                  }
                } else if (step.step_type === 'adb_command') {
                  stepSummary = step.description || step.command || ''
                } else if (step.step_type === 'ai_navigate') {
                  stepSummary = step.prompt ? (step.prompt.length > 30 ? step.prompt.slice(0, 30) + '...' : step.prompt) : ''
                } else if (step.step_type === 'ai_verify') {
                  stepSummary = step.prompt ? (step.prompt.length > 30 ? step.prompt.slice(0, 30) + '...' : step.prompt) : ''
                }

                return {
                  key: String(i),
                  label: (
                    <Space>
                      <span style={{ fontWeight: 500 }}>步骤 {i + 1}</span>
                      <StatusTag status={step.status} />
                      <Tag color="blue">{stepTypeLabels[step.step_type] || step.step_type}</Tag>
                      {stepSummary && <span style={{ color: '#555', fontSize: 12 }}>{stepSummary}</span>}
                      {step.duration_s != null && (
                        <span style={{ color: '#999', fontSize: 12 }}>{step.duration_s.toFixed(1)}s</span>
                      )}
                    </Space>
                  ),
                  children: renderStepDetail(step, i),
                }
              })}
            />
          </div>
        )}

        {/* Summary 模式（多次重复） */}
        {detailData && detailData.runs && !detailData.steps && (
          <div style={{ maxHeight: '70vh', overflow: 'auto' }}>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="总轮次" value={detailData.repeat || detailData.runs.length} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="通过" value={detailData.passed || 0} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic title="失败" value={detailData.failed || 0} valueStyle={{ color: '#cf1322' }} prefix={<CloseCircleOutlined />} />
                </Card>
              </Col>
              <Col span={6}>
                <Card size="small">
                  <Statistic
                    title="通过率"
                    value={detailData.pass_rate != null ? `${(detailData.pass_rate * 100).toFixed(0)}%` : '-'}
                    valueStyle={{ color: (detailData.pass_rate || 0) >= 0.8 ? '#3f8600' : '#cf1322' }}
                  />
                </Card>
              </Col>
            </Row>

            <Timeline
              items={(detailData.runs || []).map((run, i) => {
                const runIdx = run.run || i + 1
                const isSelected = selectedRun === runIdx
                return {
                  color: run.result === 'passed' ? 'green' : run.result === 'failed' ? 'red' : 'gray',
                  children: (
                    <Space>
                      <span>第 {runIdx} 轮</span>
                      <StatusTag status={run.result} />
                      {run.duration_s != null && <span style={{ color: '#999' }}>{run.duration_s.toFixed(1)}s</span>}
                      <Button
                        type="link"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handleViewRunDetail(runIdx)}
                        loading={runDetailLoading && selectedRun === runIdx}
                        style={{ padding: 0, fontWeight: isSelected ? 600 : 400 }}
                      >
                        {isSelected ? '当前查看' : '查看详情'}
                      </Button>
                    </Space>
                  ),
                }
              })}
            />

            {/* 选中轮次的步骤详情 */}
            {selectedRun != null && runDetailData && runDetailData.steps && (
              <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
                <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Space>
                    <span style={{ fontWeight: 600, fontSize: 14 }}>第 {selectedRun} 轮 — 步骤详情</span>
                    <StatusTag status={runDetailData.result} />
                    {runDetailData.duration_s != null && (
                      <span style={{ color: '#999', fontSize: 13 }}>{runDetailData.duration_s.toFixed(1)}s</span>
                    )}
                  </Space>
                  <Button size="small" onClick={() => { setSelectedRun(null); setRunDetailData(null) }}>收起</Button>
                </div>

                {/* 回放视频 */}
                {runDetailData.has_video && runDetailData.video_url && (
                  <div style={{ marginBottom: 16 }}>
                    <video
                      src={runDetailData.video_url}
                      controls
                      preload="metadata"
                      style={{ width: '100%', borderRadius: 6, background: '#000', maxHeight: 300 }}
                    />
                  </div>
                )}

                <Collapse
                  defaultActiveKey={
                    runDetailData.steps
                      .map((s, i) => (s.status === 'failed' || s.status === 'error') ? String(i) : null)
                      .filter(Boolean)
                  }
                  items={runDetailData.steps.map((step, i) => {
                    let stepSummary = ''
                    if (step.step_type === 'key_group') {
                      const cmds = step.commands || []
                      if (cmds.length === 1) {
                        const c = cmds[0] || {}
                        stepSummary = c.is_long_press
                          ? `长按 ${c.key} ${c.duration_ms ? (c.duration_ms/1000).toFixed(1)+'s' : ''}`
                          : c.key
                      } else if (cmds.length > 1) {
                        const keys = cmds.map(c => c.key)
                        stepSummary = keys.every(k => k === keys[0]) ? `${keys[0]} ×${cmds.length}` : keys.join(' → ')
                      }
                    } else if (step.step_type === 'adb_command') {
                      stepSummary = step.description || step.command || ''
                    } else if (step.step_type === 'ai_navigate' || step.step_type === 'ai_verify') {
                      const p = step.prompt || ''
                      stepSummary = p.length > 30 ? p.slice(0, 30) + '...' : p
                    }

                    return {
                      key: String(i),
                      label: (
                        <Space>
                          <span style={{ fontWeight: 500 }}>步骤 {i + 1}</span>
                          <StatusTag status={step.status} />
                          <Tag color="blue">{stepTypeLabels[step.step_type] || step.step_type}</Tag>
                          {stepSummary && <span style={{ color: '#555', fontSize: 12 }}>{stepSummary}</span>}
                          {step.duration_s != null && (
                            <span style={{ color: '#999', fontSize: 12 }}>{step.duration_s.toFixed(1)}s</span>
                          )}
                        </Space>
                      ),
                      children: renderStepDetail(step, i),
                    }
                  })}
                />
              </div>
            )}
            {selectedRun != null && runDetailLoading && (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#999' }}>加载中...</div>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}
