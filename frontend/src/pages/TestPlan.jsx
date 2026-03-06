import React, { useState, useEffect, useRef } from 'react'
import { Card, Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Tag, message, Popconfirm, Progress, Descriptions, Badge, Row, Col, Tooltip, Drawer, Image, Collapse, Statistic, Timeline } from 'antd'
import { PlusOutlined, PlayCircleOutlined, EditOutlined, DeleteOutlined, EyeOutlined, StopOutlined, EyeInvisibleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, WarningOutlined } from '@ant-design/icons'
import { getPlans, getPlan, createPlan, updatePlan, deletePlan, runPlan, stopPlan, getPlanStatus, getPlanResults, getCases, getReplayResult, getRunResult } from '../api'

// --- 复用回放页面的展示组件 ---
const stepTypeLabels = {
  key_group: '按键操作',
  adb_command: 'ADB 命令',
  ai_navigate: 'AI 导航',
  ai_verify: 'AI 验证',
  wait: '等待',
}

const statusConfig = {
  passed: { color: 'success', icon: <CheckCircleOutlined />, text: '通过', tagColor: 'green' },
  failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败', tagColor: 'red' },
  warning: { color: 'warning', icon: <WarningOutlined />, text: '警告', tagColor: 'orange' },
}

function StatusTag({ status }) {
  const cfg = statusConfig[status] || { tagColor: 'default', text: status || '-' }
  return <Tag color={cfg.tagColor} icon={cfg.icon}>{cfg.text}</Tag>
}

// 截图 URL 构建
const getScreenshotUrl = (screenshotPath) => {
  if (!screenshotPath) return null
  const parts = screenshotPath.replace(/\\/g, '/').split('/')
  const replayIdx = parts.lastIndexOf('replay')
  if (replayIdx < 0 || replayIdx + 3 >= parts.length) return null
  const caseKey = parts[replayIdx + 1]
  const timestamp = parts[replayIdx + 2]
  const filename = parts.slice(replayIdx + 3).join('/')
  return `/api/tv/replay/screenshot/${caseKey}/${timestamp}/${filename}`
}

export default function TestPlan() {
  const [plans, setPlans] = useState([])
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingPlan, setEditingPlan] = useState(null)
  const [runningPlanId, setRunningPlanId] = useState(null)
  const [planStatus, setPlanStatus] = useState(null)
  const [planResults, setPlanResults] = useState(null)
  const [resultsModalVisible, setResultsModalVisible] = useState(false)
  const [showProcess, setShowProcess] = useState(true)
  const [runModal, setRunModal] = useState(false)
  const [runTargetId, setRunTargetId] = useState(null)
  const [caseDetailDrawer, setCaseDetailDrawer] = useState(false)
  const [caseDetailData, setCaseDetailData] = useState(null)
  const [caseDetailLoading, setCaseDetailLoading] = useState(false)
  const [selectedRun, setSelectedRun] = useState(null)
  const [runDetailData, setRunDetailData] = useState(null)
  const [runDetailLoading, setRunDetailLoading] = useState(false)
  const [form] = Form.useForm()
  const [runForm] = Form.useForm()
  const timerRef = useRef(null)

  const fetchPlans = async () => {
    setLoading(true)
    try {
      const res = await getPlans()
      const data = res.data?.data || res.data?.plans || []
      setPlans(Array.isArray(data) ? data : [])
    } catch (e) {
      message.error('获取测试计划失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchCases = async () => {
    try {
      const res = await getCases()
      const data = res.data?.data || res.data?.cases || []
      setCases(Array.isArray(data) ? data : [])
    } catch (e) { /* 静默 */ }
  }

  const fetchPlanStatus = async (id) => {
    try {
      const res = await getPlanStatus(id)
      const data = res.data?.data || res.data
      setPlanStatus(data)
      if (!data?.is_running) {
        setRunningPlanId(null)
        setPlanStatus(null)
        if (timerRef.current) clearInterval(timerRef.current)
        fetchPlans()
        message.success('计划执行完成')
      }
    } catch (e) { /* 静默 */ }
  }

  useEffect(() => {
    fetchPlans()
    fetchCases()
  }, [])

  useEffect(() => {
    if (runningPlanId) {
      timerRef.current = setInterval(() => fetchPlanStatus(runningPlanId), 1500)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [runningPlanId])

  const handleCreate = () => {
    setEditingPlan(null)
    form.resetFields()
    setModalVisible(true)
  }

  const handleEdit = async (record) => {
    try {
      const res = await getPlan(record.id)
      const data = res.data?.data || res.data
      setEditingPlan(data)
      form.setFieldsValue(data)
      setModalVisible(true)
    } catch (e) {
      message.error('获取计划详情失败')
    }
  }

  const handleSubmit = async (values) => {
    try {
      if (editingPlan) {
        await updatePlan(editingPlan.id, values)
        message.success('计划已更新')
      } else {
        await createPlan(values)
        message.success('计划已创建')
      }
      setModalVisible(false)
      fetchPlans()
    } catch (e) {
      message.error('操作失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleDelete = async (id) => {
    try {
      await deletePlan(id)
      message.success('已删除')
      fetchPlans()
    } catch (e) {
      message.error('删除失败')
    }
  }

  const handleRunClick = (id) => {
    setRunTargetId(id)
    runForm.setFieldsValue({ repeat: 1 })
    setRunModal(true)
  }

  const handleRunConfirm = async (values) => {
    setRunModal(false)
    const id = runTargetId
    try {
      await runPlan(id, { repeat: values.repeat || 1 })
      message.success('计划开始执行')
      setRunningPlanId(id)
    } catch (e) {
      message.error('执行失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleStop = async () => {
    if (!runningPlanId) return
    try {
      await stopPlan(runningPlanId)
      message.info('正在停止...')
    } catch (e) {
      message.error('停止失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleViewResults = async (id) => {
    try {
      const res = await getPlanResults(id)
      setPlanResults(res.data?.data || res.data)
      setResultsModalVisible(true)
    } catch (e) {
      message.error('获取结果失败')
    }
  }

  // 查看某条用例的回放详情（截图、视频、步骤）
  // caseRecord: 计划结果中的用例记录（可能含 runs 数组）
  const handleViewCaseDetail = async (caseRecord) => {
    const caseKey = caseRecord.key
    // 多轮：有 runs 数组，展示轮次选择界面
    if (caseRecord.runs && caseRecord.runs.length > 0) {
      setCaseDetailData({
        _mode: 'plan_runs',
        case_key: caseKey,
        name: caseRecord.name,
        result: caseRecord.result,
        runs: caseRecord.runs,
        repeat: caseRecord.repeat,
        repeat_pass: caseRecord.repeat_pass,
        repeat_fail: caseRecord.repeat_fail,
      })
      setCaseDetailDrawer(true)
      setSelectedRun(null)
      setRunDetailData(null)
      return
    }
    // 单轮
    const replayTimestamp = caseRecord.replay_timestamp
    if (!caseKey || !replayTimestamp) {
      message.warning('该用例没有回放记录')
      return
    }
    setCaseDetailLoading(true)
    setCaseDetailDrawer(true)
    try {
      const res = await getReplayResult(caseKey, replayTimestamp)
      const data = res.data?.data || res.data
      setCaseDetailData({ ...data, case_key: caseKey, timestamp: replayTimestamp })
    } catch (e) {
      message.error('获取回放详情失败')
      setCaseDetailData(null)
    } finally {
      setCaseDetailLoading(false)
    }
  }

  // 查看多轮结果中某一轮的详情（replay engine 的 run_N 子目录）
  const handleViewRunDetail = async (runIndex) => {
    if (!caseDetailData) return
    setSelectedRun(runIndex)
    setRunDetailLoading(true)
    try {
      const res = await getRunResult(caseDetailData.case_key, caseDetailData.timestamp, runIndex)
      setRunDetailData(res.data?.data || res.data)
    } catch (e) {
      message.error('获取轮次详情失败')
      setRunDetailData(null)
    } finally {
      setRunDetailLoading(false)
    }
  }

  // 查看计划多轮中某一轮的回放详情（每轮独立的 replay timestamp）
  const handleViewPlanRun = async (run) => {
    if (!run.replay_timestamp || !caseDetailData?.case_key) {
      message.warning('该轮次没有回放记录')
      return
    }
    setSelectedRun(run.run)
    setRunDetailLoading(true)
    try {
      const res = await getReplayResult(caseDetailData.case_key, run.replay_timestamp)
      const data = res.data?.data || res.data
      setRunDetailData({ ...data, case_key: caseDetailData.case_key, timestamp: run.replay_timestamp })
    } catch (e) {
      message.error('获取轮次详情失败')
      setRunDetailData(null)
    } finally {
      setRunDetailLoading(false)
    }
  }

  // 构建截图 URL
  const getScreenshotUrl = (screenshotPath) => {
    if (!screenshotPath) return null
    const parts = screenshotPath.replace(/\\/g, '/').split('/')
    const replayIdx = parts.lastIndexOf('replay')
    if (replayIdx < 0 || replayIdx + 3 >= parts.length) return null
    const caseKey = parts[replayIdx + 1]
    const timestamp = parts[replayIdx + 2]
    const filename = parts.slice(replayIdx + 3).join('/')
    return `/api/tv/replay/screenshot/${caseKey}/${timestamp}/${filename}`
  }

  const columns = [
    { title: '计划名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '用例数', dataIndex: 'cases_count', key: 'cases_count', width: 80 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
    {
      title: '操作', key: 'action', width: 200,
      render: (_, record) => (
        <Space size={4}>
          <Tooltip title="编辑"><Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} /></Tooltip>
          <Tooltip title="执行"><Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleRunClick(record.id)} disabled={!!runningPlanId} /></Tooltip>
          <Tooltip title="结果"><Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewResults(record.id)} /></Tooltip>
          <Popconfirm title="确定删除此计划？" onConfirm={() => handleDelete(record.id)}>
            <Tooltip title="删除"><Button type="link" size="small" danger icon={<DeleteOutlined />} /></Tooltip>
          </Popconfirm>
        </Space>
      )
    }
  ]

  // 渲染执行中的进度面板
  const renderProgressPanel = () => {
    if (!runningPlanId || !planStatus) return null

    const { current_case = 0, total_cases = 0, current_case_key = '', current_case_name = '',
            current_repeat = 0, total_repeat = 1, replay_status, case_results = [] } = planStatus
    const percent = total_cases ? Math.round((current_case / total_cases) * 100) : 0

    // 回放引擎步骤级状态
    const rs = replay_status || {}
    const isReplaying = rs.is_replaying
    const currentStep = rs.current_step || 0
    const totalSteps = rs.total_steps || 0
    const stepsOverview = rs.steps_overview || []
    const stepResults = rs.step_results || []
    const stepPercent = totalSteps ? Math.round((currentStep / totalSteps) * 100) : 0

    return (
      <Card
        title={
          <Space>
            <Badge status="processing" />
            <span>正在执行: {planStatus.plan_name || runningPlanId}</span>
          </Space>
        }
        extra={
          <Space>
            <Button
              size="small"
              icon={showProcess ? <EyeInvisibleOutlined /> : <EyeOutlined />}
              onClick={() => setShowProcess(!showProcess)}
            >
              {showProcess ? '隐藏过程' : '显示过程'}
            </Button>
            <Button size="small" danger icon={<StopOutlined />} onClick={handleStop}>停止</Button>
          </Space>
        }
        style={{ marginBottom: 16 }}
      >
        {/* 总体进度 */}
        <Row gutter={16} align="middle" style={{ marginBottom: 12 }}>
          <Col>
            <span>用例进度: 第 <b>{current_case}</b> / {total_cases} 条</span>
            {total_repeat > 1 && <span style={{ marginLeft: 12 }}>轮次: <b>{current_repeat}</b> / {total_repeat}</span>}
          </Col>
          <Col flex="auto">
            <Progress percent={percent} size="small" />
          </Col>
        </Row>

        {current_case_key && (
          <div style={{ marginBottom: 8, color: '#666' }}>
            当前用例: <Tag>{current_case_key}</Tag> {current_case_name}
          </div>
        )}

        {/* 详细过程（可折叠） */}
        {showProcess && (
          <div>
            {/* 实时画面 */}
            {isReplaying && (
              <Row gutter={16} style={{ marginTop: 12 }}>
                <Col span={12}>
                  <div style={{ border: '1px solid #d9d9d9', borderRadius: 4, overflow: 'hidden', background: '#000' }}>
                    <img
                      src="/api/tv/stream"
                      alt="TV 实时画面"
                      style={{ width: '100%', display: 'block' }}
                    />
                  </div>
                </Col>
                <Col span={12}>
                  {/* 步骤进度 */}
                  <div style={{ marginBottom: 8 }}>
                    <Progress
                      percent={stepPercent}
                      format={() => `步骤 ${currentStep} / ${totalSteps}`}
                      size="small"
                      strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
                    />
                  </div>
                  <div style={{ maxHeight: 280, overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 4 }}>
                    {stepsOverview.map((s, i) => {
                      const isDone = i < stepResults.length
                      const isCurrent = i === currentStep - 1
                      const stepResult = stepResults[i]
                      const bg = isCurrent ? '#e6f7ff' : isDone ? '#f6ffed' : '#fff'
                      const icon = isDone
                        ? (stepResult?.status === 'failed' ? '❌' : '✅')
                        : isCurrent ? '▶' : '○'
                      return (
                        <div key={i} style={{ padding: '4px 8px', background: bg, borderBottom: '1px solid #f0f0f0', fontSize: 12 }}>
                          <span style={{ marginRight: 6 }}>{icon}</span>
                          <span style={{ color: '#999', marginRight: 4 }}>{i + 1}.</span>
                          {s.summary || s.type || '步骤'}
                        </div>
                      )
                    })}
                  </div>
                </Col>
              </Row>
            )}

            {/* 已完成的用例结果 */}
            {case_results.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div style={{ fontWeight: 500, marginBottom: 4 }}>已完成用例:</div>
                <Table
                  size="small"
                  dataSource={case_results}
                  rowKey={(r, i) => r.key + '_' + i}
                  pagination={false}
                  columns={[
                    { title: 'Key', dataIndex: 'key', width: 120 },
                    { title: '名称', dataIndex: 'name', ellipsis: true },
                    {
                      title: '结果', dataIndex: 'result', width: 100,
                      render: (v) => {
                        const colorMap = { passed: 'green', failed: 'red', no_script: 'orange', aborted: 'default', engine_unavailable: 'default' }
                        const labelMap = { passed: '通过', failed: '失败', no_script: '无脚本', aborted: '中止', engine_unavailable: '引擎不可用' }
                        return <Tag color={colorMap[v] || 'default'}>{labelMap[v] || v}</Tag>
                      }
                    },
                    { title: '耗时', dataIndex: 'duration_s', width: 80, render: (v) => v ? `${v}s` : '-' },
                  ]}
                />
              </div>
            )}
          </div>
        )}
      </Card>
    )
  }

  // 结果表格中用例列的通用列定义
  const resultCaseColumns = [
    { title: 'Key', dataIndex: 'key', width: 120 },
    { title: '名称', dataIndex: 'name', ellipsis: true },
    {
      title: '结果', dataIndex: 'result', width: 100,
      render: (v) => {
        const colorMap = { passed: 'green', failed: 'red', no_script: 'orange', aborted: 'default' }
        const labelMap = { passed: '通过', failed: '失败', no_script: '无脚本', aborted: '中止' }
        return <Tag color={colorMap[v] || 'default'}>{labelMap[v] || v}</Tag>
      }
    },
    { title: '耗时', dataIndex: 'duration_s', width: 80, render: (v) => v ? `${v}s` : '-' },
    {
      title: '重复', key: 'repeat_info', width: 100,
      render: (_, r) => r.repeat > 1 ? `${r.repeat_pass || 0}/${r.repeat} 通过` : '-'
    },
    {
      title: '详情', key: 'detail', width: 70,
      render: (_, r) => (r.replay_timestamp || (r.runs && r.runs.length > 0)) ? (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewCaseDetail(r)} />
      ) : '-'
    },
  ]

  // 渲染结果列表
  const renderResultsContent = () => {
    if (!planResults || !Array.isArray(planResults) || planResults.length === 0) {
      return <div style={{ textAlign: 'center', color: '#999', padding: 24 }}>暂无执行结果</div>
    }

    return planResults.map((pr, pi) => (
      <Card key={pi} size="small" title={`执行时间: ${pr.run_at || ''}`} style={{ marginBottom: 12 }}>
        <Descriptions bordered size="small" column={4} style={{ marginBottom: 12 }}>
          <Descriptions.Item label="总用例">{pr.total_cases || 0}</Descriptions.Item>
          <Descriptions.Item label="通过"><span style={{ color: '#52c41a' }}>{pr.passed || 0}</span></Descriptions.Item>
          <Descriptions.Item label="失败"><span style={{ color: '#ff4d4f' }}>{pr.failed || 0}</span></Descriptions.Item>
          <Descriptions.Item label="通过率">{((pr.pass_rate || 0) * 100).toFixed(1)}%</Descriptions.Item>
          {pr.repeat > 1 && <Descriptions.Item label="重复次数">{pr.repeat}</Descriptions.Item>}
          <Descriptions.Item label="总耗时">{pr.total_duration_s || 0}s</Descriptions.Item>
        </Descriptions>
        <Table
          size="small"
          dataSource={pr.cases || []}
          rowKey={(r, i) => (r.key || '') + '_' + i}
          pagination={false}
          columns={resultCaseColumns}
        />
      </Card>
    ))
  }

  // --- 步骤类型详情渲染（与回放页面一致） ---
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
            <span style={{ color: '#666' }}>{cmd.duration_ms ? `${(cmd.duration_ms / 1000).toFixed(1)}s` : ''}</span>
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
    const keyNames = commands.map(c => c.key)
    const allSame = keyNames.every(k => k === keyNames[0])
    return (
      <div style={{ padding: '8px 12px', background: '#f0f5ff', borderRadius: 6, border: '1px solid #d6e4ff', fontSize: 13 }}>
        {allSame ? (
          <><span style={{ fontWeight: 500 }}>连续按</span>{' '}<Tag color="blue" style={{ margin: '0 4px' }}>{keyNames[0]}</Tag><span style={{ color: '#666' }}>× {commands.length} 次</span></>
        ) : (
          <><span style={{ fontWeight: 500 }}>组合按键</span>{' '}{commands.map((c, i) => (
            <span key={i}><Tag color={c.is_long_press ? 'orange' : 'blue'} style={{ margin: '0 2px' }}>{c.key}{c.is_long_press ? ` (长按${c.duration_ms ? (c.duration_ms/1000).toFixed(1)+'s' : ''})` : ''}</Tag>{i < commands.length - 1 && <span style={{ color: '#ccc', margin: '0 2px' }}>→</span>}</span>
          ))}</>
        )}
        {intervalMs > 0 && <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>间隔 {intervalMs}ms</span>}
      </div>
    )
  }

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
            <div style={{ fontWeight: 500, marginBottom: 6, color: '#389e0d' }}>AI 执行过程（共 {rounds.length} 轮）</div>
            {rounds.map((r, i) => {
              const parsed = r.parsed || {}
              return (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', borderTop: i > 0 ? '1px solid #e8f5e0' : 'none' }}>
                  <Tag style={{ margin: 0, minWidth: 44, textAlign: 'center' }}>{`#${r.round || i + 1}`}</Tag>
                  {parsed.action && parsed.action !== 'none' && <Tag color="blue" style={{ margin: 0 }}>{parsed.action}</Tag>}
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

  const renderAdbCommandInfo = (step) => (
    <div style={{ padding: '8px 12px', background: '#f5f5f5', borderRadius: 6, border: '1px solid #e8e8e8', fontSize: 13 }}>
      {step.description && <div style={{ fontWeight: 500, marginBottom: 4 }}>{step.description}</div>}
      <code style={{ color: '#d46b08', fontSize: 12, wordBreak: 'break-all' }}>{step.command}</code>
      {step.output && <div style={{ marginTop: 4, color: '#666', fontSize: 12, whiteSpace: 'pre-wrap' }}>{step.output}</div>}
    </div>
  )

  const renderAiVerifyInfo = (step) => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {step.prompt && (
        <div style={{ padding: '8px 12px', background: '#f9f0ff', borderRadius: 6, border: '1px solid #d3adf7', fontSize: 13 }}>
          <span style={{ fontWeight: 500, color: '#722ed1' }}>校验条件：</span>{step.prompt}
        </div>
      )}
      {step.ai_reason && (
        <div style={{ padding: '8px 12px', borderRadius: 6, fontSize: 13, background: step.ai_passed ? '#f6ffed' : '#fff2f0', border: `1px solid ${step.ai_passed ? '#b7eb8f' : '#ffccc7'}` }}>
          <span style={{ fontWeight: 500 }}>AI 判断：</span>{step.ai_reason}
          {step.ai_confidence != null && <span style={{ marginLeft: 8, color: '#999' }}>置信度: {(step.ai_confidence * 100).toFixed(0)}%</span>}
        </div>
      )}
    </div>
  )

  const renderStepDetail = (step, index) => {
    const screenshotUrl = getScreenshotUrl(step.screenshot)
    return (
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
        <div style={{ flexShrink: 0 }}>
          {screenshotUrl ? (
            <Image src={screenshotUrl} alt={`步骤 ${index + 1} 截图`} width={320} style={{ borderRadius: 4, border: '1px solid #f0f0f0' }}
              placeholder={<div style={{ width: 320, height: 180, background: '#f5f5f5', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>加载中...</div>}
              fallback="data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIwIiBoZWlnaHQ9IjE4MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjVmNWY1Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGRvbWluYW50LWJhc2VsaW5lPSJtaWRkbGUiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IiM5OTkiIGZvbnQtc2l6ZT0iMTQiPuaXoOaIquWbvjwvdGV4dD48L3N2Zz4="
            />
          ) : (
            <div style={{ width: 320, height: 180, background: '#fafafa', borderRadius: 4, border: '1px dashed #d9d9d9', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#bbb' }}>无截图</div>
          )}
        </div>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Space size="middle">
            <StatusTag status={step.status} />
            <Tag>{stepTypeLabels[step.step_type] || step.step_type}</Tag>
            {step.duration_s != null && (
              <span style={{ color: '#999', fontSize: 13 }}><ClockCircleOutlined style={{ marginRight: 4 }} />{step.duration_s.toFixed(1)}s</span>
            )}
          </Space>
          {step.step_type === 'key_group' && renderKeyGroupInfo(step)}
          {step.step_type === 'adb_command' && renderAdbCommandInfo(step)}
          {step.step_type === 'ai_navigate' && renderAiNavigateInfo(step)}
          {step.step_type === 'ai_verify' && renderAiVerifyInfo(step)}
          {step.step_type === 'wait' && (
            <div style={{ padding: '8px 12px', background: '#fffbe6', borderRadius: 6, border: '1px solid #ffe58f', fontSize: 13 }}>
              <span style={{ fontWeight: 500 }}>等待</span>{' '}
              <span style={{ color: '#d48806' }}>{step.duration_ms || 0}ms（{((step.duration_ms || 0) / 1000).toFixed(1)}s）</span>
            </div>
          )}
          {step.reason && (
            <div style={{ padding: '8px 12px', borderRadius: 6, fontSize: 13, color: '#333', wordBreak: 'break-all',
              background: step.status === 'failed' ? '#fff2f0' : '#fffbe6',
              border: `1px solid ${step.status === 'failed' ? '#ffccc7' : '#ffe58f'}`,
            }}>{step.reason}</div>
          )}
        </div>
      </div>
    )
  }

  // --- 用例回放详情内容（与回放页面详情弹窗一致） ---
  const renderCaseDetailContent = () => {
    if (caseDetailLoading) return <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
    if (!caseDetailData) return null
    const d = caseDetailData

    // 计划多轮模式：每轮独立的 replay timestamp
    if (d._mode === 'plan_runs') {
      const resultColorMap = { passed: 'green', failed: 'red', aborted: 'default' }
      const resultLabelMap = { passed: '通过', failed: '失败', aborted: '中止' }
      return (
        <div style={{ maxHeight: '80vh', overflow: 'auto' }}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Card size="small"><Statistic title="总轮次" value={d.repeat || d.runs.length} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="通过" value={d.repeat_pass || 0} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="失败" value={d.repeat_fail || 0} valueStyle={{ color: '#cf1322' }} prefix={<CloseCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="总结果" value={resultLabelMap[d.result] || d.result} valueStyle={{ color: d.result === 'passed' ? '#3f8600' : '#cf1322' }} /></Card></Col>
          </Row>

          <Timeline
            items={d.runs.map((run) => ({
              color: run.result === 'passed' ? 'green' : run.result === 'failed' ? 'red' : 'gray',
              children: (
                <Space>
                  <span>第 {run.run} 轮</span>
                  <Tag color={resultColorMap[run.result] || 'default'}>{resultLabelMap[run.result] || run.result}</Tag>
                  {run.replay_timestamp ? (
                    <Button
                      type="link" size="small" icon={<EyeOutlined />}
                      onClick={() => handleViewPlanRun(run)}
                      loading={runDetailLoading && selectedRun === run.run}
                      style={{ padding: 0, fontWeight: selectedRun === run.run ? 600 : 400 }}
                    >
                      {selectedRun === run.run ? '当前查看' : '查看详情'}
                    </Button>
                  ) : <span style={{ color: '#999', fontSize: 12 }}>无记录</span>}
                </Space>
              ),
            }))}
          />

          {/* 选中轮次的步骤详情 */}
          {selectedRun != null && runDetailData && runDetailData.steps && (
            <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
              <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Space>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>第 {selectedRun} 轮 — 步骤详情</span>
                  <StatusTag status={runDetailData.result} />
                  {runDetailData.duration_s != null && <span style={{ color: '#999', fontSize: 13 }}>{runDetailData.duration_s.toFixed(1)}s</span>}
                </Space>
                <Button size="small" onClick={() => { setSelectedRun(null); setRunDetailData(null) }}>收起</Button>
              </div>

              {runDetailData.has_video && runDetailData.video_url && (
                <div style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ fontWeight: 500, fontSize: 13, color: '#555' }}><PlayCircleOutlined style={{ marginRight: 4 }} />回放视频</span>
                    <a href={runDetailData.video_url} download="replay.mp4" style={{ fontSize: 12 }}>下载视频</a>
                  </div>
                  <video src={runDetailData.video_url} controls preload="metadata" style={{ width: '100%', borderRadius: 6, background: '#000', maxHeight: 300 }} />
                </div>
              )}

              <Collapse
                defaultActiveKey={runDetailData.steps.map((s, i) => (s.status === 'failed' || s.status === 'error') ? String(i) : null).filter(Boolean)}
                items={runDetailData.steps.map((step, i) => {
                  let stepSummary = ''
                  if (step.step_type === 'key_group') {
                    const cmds = step.commands || []
                    if (cmds.length === 1) { const c = cmds[0] || {}; stepSummary = c.is_long_press ? `长按 ${c.key}` : c.key }
                    else if (cmds.length > 1) { const keys = cmds.map(c => c.key); stepSummary = keys.every(k => k === keys[0]) ? `${keys[0]} ×${cmds.length}` : keys.join(' → ') }
                  } else if (step.step_type === 'adb_command') { stepSummary = step.description || step.command || '' }
                  else if (step.step_type === 'ai_navigate' || step.step_type === 'ai_verify') { const p = step.prompt || ''; stepSummary = p.length > 30 ? p.slice(0, 30) + '...' : p }
                  return {
                    key: String(i),
                    label: (
                      <Space>
                        <span style={{ fontWeight: 500 }}>步骤 {i + 1}</span>
                        <StatusTag status={step.status} />
                        <Tag color="blue">{stepTypeLabels[step.step_type] || step.step_type}</Tag>
                        {stepSummary && <span style={{ color: '#555', fontSize: 12 }}>{stepSummary}</span>}
                        {step.duration_s != null && <span style={{ color: '#999', fontSize: 12 }}>{step.duration_s.toFixed(1)}s</span>}
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
      )
    }

    // 单次结果（有 steps）
    if (d.steps && d.steps.length > 0) {
      return (
        <div style={{ maxHeight: '80vh', overflow: 'auto' }}>
          {/* 概要统计 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Card size="small"><Statistic title="总步骤" value={d.total_steps || d.steps.length} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="通过" value={d.steps.filter(s => s.status === 'passed').length} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="失败" value={d.steps.filter(s => s.status === 'failed' || s.status === 'error').length} valueStyle={{ color: '#cf1322' }} prefix={<CloseCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="总耗时" value={d.duration_s ? `${d.duration_s.toFixed(1)}s` : '-'} prefix={<ClockCircleOutlined />} /></Card></Col>
          </Row>

          {/* 回放视频 */}
          {d.has_video && d.video_url && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontWeight: 500, fontSize: 13, color: '#555' }}><PlayCircleOutlined style={{ marginRight: 4 }} />回放视频</span>
                <a href={d.video_url} download="replay.mp4" style={{ fontSize: 12 }}>下载视频</a>
              </div>
              <video src={d.video_url} controls preload="metadata" style={{ width: '100%', borderRadius: 6, background: '#000', maxHeight: 360 }}>
                浏览器不支持该视频格式，请<a href={d.video_url} download="replay.mp4">下载</a>观看
              </video>
            </div>
          )}

          {/* 步骤列表（Collapse） */}
          <Collapse
            defaultActiveKey={d.steps.map((s, i) => (s.status === 'failed' || s.status === 'error') ? String(i) : null).filter(Boolean)}
            items={d.steps.map((step, i) => {
              let stepSummary = ''
              if (step.step_type === 'key_group') {
                const cmds = step.commands || []
                if (cmds.length === 1) {
                  const c = cmds[0] || {}
                  stepSummary = c.is_long_press ? `长按 ${c.key} ${c.duration_ms ? (c.duration_ms/1000).toFixed(1)+'s' : ''}` : c.key
                } else if (cmds.length > 1) {
                  const keys = cmds.map(c => c.key)
                  stepSummary = keys.every(k => k === keys[0]) ? `${keys[0]} ×${cmds.length}` : keys.join(' → ')
                }
              } else if (step.step_type === 'adb_command') {
                stepSummary = step.description || step.command || ''
              } else if (step.step_type === 'ai_navigate' || step.step_type === 'ai_verify') {
                const p = step.prompt || ''
                stepSummary = p.length > 30 ? p.slice(0, 30) + '...' : p
              } else if (step.step_type === 'wait') {
                stepSummary = `${((step.duration_ms || 0) / 1000).toFixed(1)}s`
              }
              return {
                key: String(i),
                label: (
                  <Space>
                    <span style={{ fontWeight: 500 }}>步骤 {i + 1}</span>
                    <StatusTag status={step.status} />
                    <Tag color="blue">{stepTypeLabels[step.step_type] || step.step_type}</Tag>
                    {stepSummary && <span style={{ color: '#555', fontSize: 12 }}>{stepSummary}</span>}
                    {step.duration_s != null && <span style={{ color: '#999', fontSize: 12 }}>{step.duration_s.toFixed(1)}s</span>}
                  </Space>
                ),
                children: renderStepDetail(step, i),
              }
            })}
          />
        </div>
      )
    }

    // 多轮结果（summary 模式，有 runs）
    if (d.runs && d.runs.length > 0) {
      return (
        <div style={{ maxHeight: '80vh', overflow: 'auto' }}>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}><Card size="small"><Statistic title="总轮次" value={d.repeat || d.runs.length} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="通过" value={d.passed || 0} valueStyle={{ color: '#3f8600' }} prefix={<CheckCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="失败" value={d.failed || 0} valueStyle={{ color: '#cf1322' }} prefix={<CloseCircleOutlined />} /></Card></Col>
            <Col span={6}><Card size="small"><Statistic title="通过率" value={d.pass_rate != null ? `${(d.pass_rate * 100).toFixed(0)}%` : '-'} valueStyle={{ color: (d.pass_rate || 0) >= 0.8 ? '#3f8600' : '#cf1322' }} /></Card></Col>
          </Row>
          <Timeline
            items={(d.runs || []).map((run, i) => ({
              color: run.result === 'passed' ? 'green' : run.result === 'failed' ? 'red' : 'gray',
              children: (
                <Space>
                  <span>第 {run.run || i + 1} 轮</span>
                  <StatusTag status={run.result} />
                  {run.duration_s != null && <span style={{ color: '#999' }}>{run.duration_s.toFixed(1)}s</span>}
                  <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewRunDetail(run.run || i + 1)}>查看详情</Button>
                </Space>
              ),
            }))}
          />
          {runDetailData && runDetailData.steps && (
            <div style={{ marginTop: 8, borderTop: '1px solid #f0f0f0', paddingTop: 16 }}>
              <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Space>
                  <span style={{ fontWeight: 600, fontSize: 14 }}>第 {selectedRun} 轮 — 步骤详情</span>
                  <StatusTag status={runDetailData.result} />
                </Space>
                <Button size="small" onClick={() => { setSelectedRun(null); setRunDetailData(null) }}>收起</Button>
              </div>
              {runDetailData.has_video && runDetailData.video_url && (
                <div style={{ marginBottom: 16 }}>
                  <video src={runDetailData.video_url} controls preload="metadata" style={{ width: '100%', borderRadius: 6, background: '#000', maxHeight: 300 }} />
                </div>
              )}
              <Collapse
                defaultActiveKey={runDetailData.steps.map((s, i) => (s.status === 'failed' || s.status === 'error') ? String(i) : null).filter(Boolean)}
                items={runDetailData.steps.map((step, i) => {
                  let stepSummary = ''
                  if (step.step_type === 'key_group') {
                    const cmds = step.commands || []
                    if (cmds.length === 1) { const c = cmds[0] || {}; stepSummary = c.is_long_press ? `长按 ${c.key}` : c.key }
                    else if (cmds.length > 1) { const keys = cmds.map(c => c.key); stepSummary = keys.every(k => k === keys[0]) ? `${keys[0]} ×${cmds.length}` : keys.join(' → ') }
                  } else if (step.step_type === 'adb_command') { stepSummary = step.description || step.command || '' }
                  else if (step.step_type === 'ai_navigate' || step.step_type === 'ai_verify') { const p = step.prompt || ''; stepSummary = p.length > 30 ? p.slice(0, 30) + '...' : p }
                  return {
                    key: String(i),
                    label: (
                      <Space>
                        <span style={{ fontWeight: 500 }}>步骤 {i + 1}</span>
                        <StatusTag status={step.status} />
                        <Tag color="blue">{stepTypeLabels[step.step_type] || step.step_type}</Tag>
                        {stepSummary && <span style={{ color: '#555', fontSize: 12 }}>{stepSummary}</span>}
                        {step.duration_s != null && <span style={{ color: '#999', fontSize: 12 }}>{step.duration_s.toFixed(1)}s</span>}
                      </Space>
                    ),
                    children: renderStepDetail(step, i),
                  }
                })}
              />
            </div>
          )}
        </div>
      )
    }

    return <div style={{ textAlign: 'center', color: '#999', padding: 24 }}>无详细数据</div>
  }

  return (
    <div>
      <h2>测试计划</h2>

      {renderProgressPanel()}

      <Card>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ marginBottom: 16 }}>新建计划</Button>
        <Table
          columns={columns}
          dataSource={plans}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 新建/编辑计划 */}
      <Modal
        title={editingPlan ? '编辑计划' : '新建计划'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
        destroyOnClose
      >
        <Form form={form} onFinish={handleSubmit} layout="vertical">
          <Form.Item label="计划名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="测试计划名称" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={2} placeholder="计划描述" />
          </Form.Item>
          <Form.Item label="选择用例" name="cases" rules={[{ required: true, message: '请选择用例' }]}>
            <Select
              mode="multiple"
              placeholder="选择要包含的用例"
              optionFilterProp="label"
              showSearch
            >
              {(() => {
                const grouped = {}
                const ungrouped = []
                cases.forEach(c => {
                  if (c.module) {
                    if (!grouped[c.module]) grouped[c.module] = []
                    grouped[c.module].push(c)
                  } else {
                    ungrouped.push(c)
                  }
                })
                return [
                  ...Object.entries(grouped).map(([mod, items]) => (
                    <Select.OptGroup key={mod} label={mod}>
                      {items.map(c => <Select.Option key={c.key} value={c.key} label={`${c.key} - ${c.name}`}>{c.key} - {c.name}</Select.Option>)}
                    </Select.OptGroup>
                  )),
                  ...ungrouped.map(c => <Select.Option key={c.key} value={c.key} label={`${c.key} - ${c.name}`}>{c.key} - {c.name}</Select.Option>)
                ]
              })()}
            </Select>
          </Form.Item>
          <Form.Item label="失败时停止" name="stop_on_failure" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 执行确认 - 输入重复次数 */}
      <Modal
        title="执行计划"
        open={runModal}
        onCancel={() => setRunModal(false)}
        onOk={() => runForm.submit()}
        width={400}
        destroyOnClose
      >
        <Form form={runForm} onFinish={handleRunConfirm} layout="vertical" initialValues={{ repeat: 1 }}>
          <Form.Item label="每个用例执行次数" name="repeat" rules={[{ required: true }]}>
            <InputNumber min={1} max={100} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 执行结果 */}
      <Modal
        title="执行结果"
        open={resultsModalVisible}
        onCancel={() => setResultsModalVisible(false)}
        footer={null}
        width={800}
      >
        {renderResultsContent()}
      </Modal>

      {/* 用例回放详情抽屉 */}
      <Drawer
        title={`回放详情 ${caseDetailData?.jira_key || caseDetailData?.case_key || ''}`}
        open={caseDetailDrawer}
        onClose={() => { setCaseDetailDrawer(false); setCaseDetailData(null); setSelectedRun(null); setRunDetailData(null) }}
        width={720}
      >
        {renderCaseDetailContent()}
      </Drawer>
    </div>
  )
}
