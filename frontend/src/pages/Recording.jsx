import React, { useState, useEffect, useRef } from 'react'
import { Card, Select, Button, Space, Table, Input, Tag, message, Alert, Divider, Radio, Modal, Popconfirm, Collapse } from 'antd'
import { PlayCircleOutlined, PauseOutlined, DeleteOutlined, SendOutlined, PlusOutlined, EditOutlined, WarningOutlined, ThunderboltOutlined, LoadingOutlined, CheckCircleOutlined, ClockCircleOutlined, StopOutlined } from '@ant-design/icons'
import { getCases, getCase, startRecording, stopRecording, getRecordingStatus, insertAdb, insertAi, deleteLastStep, insertStepAt, deleteStep, getSavedSteps, insertSavedStep, deleteSavedStep, updateSavedStep, quickReplay, stopQuickReplay, getReplayStatus } from '../api'

const COMMON_KEYS = [
  'UP', 'DOWN', 'LEFT', 'RIGHT', 'ENTER', 'BACK', 'HOME', 'MENU', 'SETTING',
  'VOLUME_UP', 'VOLUME_DOWN', 'MUTE',
  '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
  'POWER', 'SOURCE', 'CHANNEL_UP', 'CHANNEL_DOWN',
  'PLAY_PAUSE', 'STOP', 'REWIND', 'FAST_FORWARD',
]

export default function Recording() {
  const [cases, setCases] = useState([])
  const [selectedCase, setSelectedCase] = useState(null)
  const [caseDetail, setCaseDetail] = useState(null)
  const [recording, setRecording] = useState(false)
  const [status, setStatus] = useState(null)
  const [adbCommand, setAdbCommand] = useState('')
  const [adbDesc, setAdbDesc] = useState('')
  const [aiType, setAiType] = useState('ai_navigate')
  const [aiPrompt, setAiPrompt] = useState('')
  const timerRef = useRef(null)
  const [savedSteps, setSavedSteps] = useState([])

  // 快速回放状态
  const [quickReplaying, setQuickReplaying] = useState(false)
  const [replayStatus, setReplayStatus] = useState(null)
  const replayTimerRef = useRef(null)

  // 插入/编辑 Modal 状态
  const [modalVisible, setModalVisible] = useState(false)
  const [modalMode, setModalMode] = useState('insert') // 'insert' | 'edit'
  const [modalIndex, setModalIndex] = useState(0)
  const [modalStepType, setModalStepType] = useState('key')
  const [modalKey, setModalKey] = useState('ENTER')
  const [modalAdbCmd, setModalAdbCmd] = useState('')
  const [modalAdbDesc, setModalAdbDesc] = useState('')
  const [modalAiType, setModalAiType] = useState('ai_navigate')
  const [modalAiPrompt, setModalAiPrompt] = useState('')

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
      const res = await getRecordingStatus()
      const data = res.data?.data || res.data
      setStatus(data)
      setRecording(data?.is_recording || data?.recording || false)
    } catch (e) {
      // 静默失败
    }
  }

  const fetchCaseDetail = async (key) => {
    if (!key) { setCaseDetail(null); setSavedSteps([]); return }
    try {
      const res = await getCase(key)
      setCaseDetail(res.data?.data || res.data)
    } catch (e) {
      setCaseDetail(null)
    }
    // 获取已保存的录制步骤
    try {
      const res = await getSavedSteps(key)
      setSavedSteps(res.data?.data || [])
    } catch (e) {
      setSavedSteps([])
    }
  }

  const handleCaseChange = (key) => {
    setSelectedCase(key)
    fetchCaseDetail(key)
  }

  useEffect(() => {
    fetchCases()
    fetchStatus()
  }, [])

  useEffect(() => {
    if (recording) {
      timerRef.current = setInterval(fetchStatus, 1000)
    } else {
      if (timerRef.current) clearInterval(timerRef.current)
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [recording])

  // 快速回放轮询
  useEffect(() => {
    if (quickReplaying) {
      const poll = async () => {
        try {
          const res = await getReplayStatus()
          const data = res.data?.data
          setReplayStatus(data)
          if (data && !data.is_replaying) {
            setQuickReplaying(false)
            setReplayStatus(null)
            message.success('快速回放完成')
          }
        } catch (e) { /* 静默 */ }
      }
      poll()
      replayTimerRef.current = setInterval(poll, 800)
    } else {
      if (replayTimerRef.current) clearInterval(replayTimerRef.current)
    }
    return () => { if (replayTimerRef.current) clearInterval(replayTimerRef.current) }
  }, [quickReplaying])

  const handleQuickReplay = async () => {
    if (!selectedCase) { message.warning('请先选择用例'); return }
    try {
      const res = await quickReplay(selectedCase)
      if (res.data?.success) {
        setQuickReplaying(true)
        message.success('快速回放已启动')
      } else {
        message.error(res.data?.message || res.data?.error || '启动失败')
      }
    } catch (e) {
      message.error('快速回放失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleStopQuickReplay = async () => {
    try {
      await stopQuickReplay()
      message.info('正在停止快速回放...')
    } catch (e) {
      message.error('停止失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleStart = async () => {
    if (!selectedCase) {
      message.warning('请先选择用例')
      return
    }
    try {
      await startRecording(selectedCase)
      message.success('录制已开始')
      setRecording(true)
    } catch (e) {
      message.error('开始录制失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleStop = async () => {
    try {
      await stopRecording()
      message.success('录制已停止')
      setRecording(false)
      fetchStatus()
      // 重新加载已保存的步骤，确保显示本次录制结果
      if (selectedCase) {
        fetchCaseDetail(selectedCase)
      }
    } catch (e) {
      message.error('停止录制失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleInsertAdb = async () => {
    if (!adbCommand) { message.warning('请输入 ADB 命令'); return }
    try {
      await insertAdb(adbCommand, adbDesc)
      message.success('ADB 命令已插入')
      setAdbCommand('')
      setAdbDesc('')
      fetchStatus()
    } catch (e) {
      message.error('插入失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleInsertAi = async () => {
    if (!aiPrompt) { message.warning('请输入 AI 指令'); return }
    try {
      await insertAi(aiType, aiPrompt)
      message.success('AI 指令已插入')
      setAiPrompt('')
      fetchStatus()
    } catch (e) {
      message.error('插入失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleDeleteLast = async () => {
    try {
      await deleteLastStep()
      message.success('已删除最后一步')
      fetchStatus()
    } catch (e) {
      message.error('删除失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleDeleteStepByIndex = async (index) => {
    try {
      if (recording) {
        await deleteStep(index)
      } else {
        if (!selectedCase) return
        await deleteSavedStep(selectedCase, index)
      }
      message.success('已删除步骤')
      recording ? fetchStatus() : fetchCaseDetail(selectedCase)
    } catch (e) {
      message.error('删除失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const resetModal = () => {
    setModalStepType('key')
    setModalKey('ENTER')
    setModalAdbCmd('')
    setModalAdbDesc('')
    setModalAiType('ai_navigate')
    setModalAiPrompt('')
  }

  const openInsertModal = (afterIndex) => {
    setModalMode('insert')
    setModalIndex(afterIndex)
    resetModal()
    setModalVisible(true)
  }

  const openEditModal = (index, step) => {
    setModalMode('edit')
    setModalIndex(index)
    if (step.type === 'adb_command') {
      setModalStepType('adb_command')
      setModalAdbCmd(step.command || '')
      setModalAdbDesc(step.description || '')
    } else if (step.type === 'ai_navigate' || step.type === 'ai_verify') {
      setModalStepType('ai')
      setModalAiType(step.type)
      setModalAiPrompt(step.prompt || '')
    } else if (step.type === 'key_group') {
      setModalStepType('key')
      const firstKey = step.commands?.[0]?.key || 'ENTER'
      setModalKey(firstKey)
    }
    setModalVisible(true)
  }

  const getModalParams = () => {
    let params = {}
    let type = modalStepType
    if (modalStepType === 'key') {
      params = { key: modalKey }
    } else if (modalStepType === 'adb_command') {
      if (!modalAdbCmd) { message.warning('请输入 ADB 命令'); return null }
      params = { command: modalAdbCmd, description: modalAdbDesc }
    } else {
      if (!modalAiPrompt) { message.warning('请输入 AI 指令'); return null }
      params = { prompt: modalAiPrompt }
      type = modalAiType
    }
    return { type, params }
  }

  const handleModalOk = async () => {
    const result = getModalParams()
    if (!result) return
    const { type, params } = result
    try {
      if (modalMode === 'insert') {
        if (recording) {
          await insertStepAt(modalIndex, type, params)
        } else {
          if (!selectedCase) return
          await insertSavedStep(selectedCase, modalIndex, type, params)
        }
        message.success('步骤已插入')
      } else {
        if (recording) {
          await deleteStep(modalIndex)
          await insertStepAt(modalIndex, type, params)
        } else {
          if (!selectedCase) return
          await updateSavedStep(selectedCase, modalIndex, type, params)
        }
        message.success('步骤已修改')
      }
      setModalVisible(false)
      recording ? fetchStatus() : fetchCaseDetail(selectedCase)
    } catch (e) {
      message.error('插入失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const steps = recording ? (status?.steps || []) : savedSteps
  const rawKeys = status?.raw_keys || []

  // 合并已确认步骤和未分组按键，生成统一的展示列表
  const displayItems = []
  steps.forEach((s, i) => {
    const base = { seq: displayItems.length + 1, stepIndex: i, editable: true, rawStep: s }
    if (s.type === 'adb_command') {
      displayItems.push({ ...base, type: 'ADB', label: s.description || s.command, color: 'orange' })
    } else if (s.type === 'ai_navigate') {
      displayItems.push({ ...base, type: 'AI导航', label: s.prompt, color: 'purple' })
    } else if (s.type === 'ai_verify') {
      displayItems.push({ ...base, type: 'AI验证', label: s.prompt, color: 'green' })
    } else if (s.type === 'key_group') {
      const keys = (s.commands || []).map(c => {
        const name = c.key || '?'
        if (c.is_long_press) {
          const sec = c.duration_ms ? `${(c.duration_ms / 1000).toFixed(1)}s` : ''
          return `${name}(长按${sec})`
        }
        return name
      }).join(' → ')
      displayItems.push({ ...base, type: '按键组', label: keys, color: 'blue' })
    }
  })
  if (recording) {
    rawKeys.forEach((k) => {
      const name = k.key || '?'
      const suffix = k.is_long_press ? ' (长按)' : ''
      displayItems.push({ seq: displayItems.length + 1, type: '按键', label: name + suffix, color: 'cyan', editable: false })
    })
  }

  const stepColumns = [
    { title: '#', key: 'seq', dataIndex: 'seq', width: 45 },
    {
      title: '类型', key: 'type', width: 80,
      render: (_, r) => <Tag color={r.color}>{r.type}</Tag>
    },
    { title: '内容', key: 'label', dataIndex: 'label', ellipsis: true },
    {
      title: '操作', key: 'action', width: 110,
      render: (_, r) => r.editable ? (
        <Space size={4}>
          <Button
            type="text"
            size="small"
            icon={<PlusOutlined />}
            onClick={() => openInsertModal(r.stepIndex + 1)}
            title="在此步骤后插入"
          />
          <Button
            type="text"
            size="small"
            icon={<EditOutlined />}
            onClick={() => openEditModal(r.stepIndex, r.rawStep)}
            title="修改此步骤"
          />
          <Popconfirm title="确定删除此步骤？" onConfirm={() => handleDeleteStepByIndex(r.stepIndex)} okText="删除" cancelText="取消">
            <Button type="text" size="small" danger icon={<DeleteOutlined />} title="删除此步骤" />
          </Popconfirm>
        </Space>
      ) : null,
    },
  ]

  // 用例详情面板（录制时作为左侧栏，非录制时作为独立卡片）
  const caseDetailContent = caseDetail ? (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {/* 标题 */}
      <div style={{ fontWeight: 600, fontSize: 14 }}>
        {caseDetail.key} {caseDetail.name || caseDetail.summary || ''}
      </div>

      {/* 前置条件 */}
      {caseDetail.precondition && (
        <div style={{
          padding: '8px 12px', background: '#fffbe6', border: '1px solid #ffe58f', borderRadius: 6,
        }}>
          <div style={{ fontWeight: 500, fontSize: 12, color: '#ad6800', marginBottom: 4 }}>
            <WarningOutlined style={{ marginRight: 4 }} />前置条件
          </div>
          <div style={{ fontSize: 13, color: '#333', whiteSpace: 'pre-wrap' }}>
            {caseDetail.precondition}
          </div>
        </div>
      )}

      {/* 描述 */}
      {caseDetail.description && (
        <div style={{ padding: '8px 12px', background: '#fafafa', borderRadius: 6, border: '1px solid #f0f0f0' }}>
          <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 4 }}>描述</div>
          <div style={{ fontSize: 13, color: '#333', whiteSpace: 'pre-wrap' }}>{caseDetail.description}</div>
        </div>
      )}

      {/* 测试步骤 */}
      {caseDetail.test_steps?.length > 0 && (
        <div>
          <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 4 }}>测试步骤</div>
          {caseDetail.test_steps.map((ts, i) => (
            <div key={i} style={{
              padding: '8px 10px', marginBottom: 4,
              background: '#fafafa', border: '1px solid #f0f0f0', borderRadius: 6, fontSize: 13,
            }}>
              <div style={{ color: '#333', whiteSpace: 'pre-wrap' }}>
                <Tag style={{ marginRight: 6 }}>{ts.sequenceNumber || i + 1}</Tag>{ts.step}
              </div>
              {ts.expectedResult && (
                <div style={{ marginTop: 4, padding: '4px 8px', background: '#f6ffed', borderRadius: 4, border: '1px solid #d9f7be', fontSize: 12 }}>
                  <span style={{ color: '#389e0d', fontWeight: 500 }}>期望：</span>
                  <span style={{ color: '#555', whiteSpace: 'pre-wrap' }}>{ts.expectedResult}</span>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {(!caseDetail.test_steps || caseDetail.test_steps.length === 0) && !caseDetail.description && !caseDetail.precondition && (
        <span style={{ color: '#999', fontSize: 13 }}>该用例无详细步骤信息</span>
      )}
    </div>
  ) : null

  // 操作面板内容
  const operationPanel = (
    <Collapse
      size="small"
      items={[{
        key: 'ops',
        label: '插入 ADB / AI 指令',
        children: (
          <div>
            <div style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 6 }}>ADB 命令</div>
              <Space size={4} wrap>
                <Input placeholder="ADB 命令" value={adbCommand} onChange={e => setAdbCommand(e.target.value)} style={{ width: 200 }} disabled={!recording} size="small" />
                <Input placeholder="描述" value={adbDesc} onChange={e => setAdbDesc(e.target.value)} style={{ width: 120 }} disabled={!recording} size="small" />
                <Button size="small" icon={<SendOutlined />} onClick={handleInsertAdb} disabled={!recording}>插入</Button>
              </Space>
            </div>
            <div>
              <div style={{ fontWeight: 500, fontSize: 12, color: '#666', marginBottom: 6 }}>AI 指令</div>
              <Space size={4} wrap>
                <Radio.Group value={aiType} onChange={e => setAiType(e.target.value)} disabled={!recording} size="small">
                  <Radio.Button value="ai_navigate">导航</Radio.Button>
                  <Radio.Button value="ai_verify">验证</Radio.Button>
                </Radio.Group>
                <Input.TextArea placeholder="AI 指令" value={aiPrompt} onChange={e => setAiPrompt(e.target.value)} style={{ width: 220 }} rows={1} disabled={!recording} size="small" />
                <Button size="small" icon={<SendOutlined />} onClick={handleInsertAi} disabled={!recording}>插入</Button>
              </Space>
            </div>
          </div>
        ),
      }]}
    />
  )

  // 已录制步骤面板
  const stepsPanel = (
    <Card
      title={`已录制步骤 (${displayItems.length})`}
      size="small"
      extra={
        <Space size={4}>
          <Button size="small" icon={<PlusOutlined />} onClick={() => openInsertModal(0)} disabled={displayItems.length === 0 && !recording && !selectedCase}>
            在开头插入
          </Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={handleDeleteLast} disabled={!recording || displayItems.length === 0}>
            删除最后一步
          </Button>
        </Space>
      }
    >
      <Table
        columns={stepColumns}
        dataSource={displayItems}
        rowKey={(r) => r.seq}
        size="small"
        pagination={false}
        scroll={{ y: recording ? 'calc(100vh - 280px)' : 500 }}
      />
    </Card>
  )

  return (
    <div>
      {/* 控制栏 */}
      <Card size="small" style={{ marginBottom: 12 }}>
        <Space size="middle" wrap>
          <span style={{ fontWeight: 'bold' }}>选择用例：</span>
          <Select
            style={{ width: 300 }}
            placeholder="请选择要录制的用例"
            value={selectedCase}
            onChange={handleCaseChange}
            disabled={recording || quickReplaying}
            showSearch
            optionFilterProp="label"
            options={cases.map(c => ({ label: `${c.key} - ${c.name}`, value: c.key }))}
          />
          {!recording && !quickReplaying ? (
            <>
              <Button type="primary" icon={<PlayCircleOutlined />}
                onClick={(e) => { e.currentTarget.blur(); handleStart(); }}
                onKeyDown={(e) => e.preventDefault()}
              >开始录制</Button>
              <Button icon={<ThunderboltOutlined />}
                onClick={(e) => { e.currentTarget.blur(); handleQuickReplay(); }}
                onKeyDown={(e) => e.preventDefault()}
                disabled={!selectedCase || savedSteps.length === 0}
              >快速回放</Button>
            </>
          ) : recording ? (
            <Button danger icon={<PauseOutlined />}
              onClick={(e) => { e.currentTarget.blur(); handleStop(); }}
              onKeyDown={(e) => e.preventDefault()}
            >停止录制</Button>
          ) : (
            <Button danger icon={<StopOutlined />}
              onClick={(e) => { e.currentTarget.blur(); handleStopQuickReplay(); }}
              onKeyDown={(e) => e.preventDefault()}
            >停止回放</Button>
          )}
          {recording && (
            <Tag color="processing" style={{ marginLeft: 8 }}>录制中 — 已录制 {displayItems.length} 步</Tag>
          )}
          {quickReplaying && replayStatus && (
            <Tag color="blue" style={{ marginLeft: 8 }}>
              <LoadingOutlined style={{ marginRight: 4 }} />
              回放中 {replayStatus.current_step}/{replayStatus.total_steps} 步
            </Tag>
          )}
        </Space>
      </Card>

      {quickReplaying ? (
        /* ===== 快速回放中：三栏布局 ===== */
        <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 130px)' }}>
          {/* 左栏：用例详情 */}
          <div style={{
            width: 320, flexShrink: 0,
            overflow: 'auto', padding: '12px',
            background: '#fff', borderRadius: 8, border: '1px solid #f0f0f0',
          }}>
            {caseDetailContent || <span style={{ color: '#999' }}>未选择用例</span>}
          </div>

          {/* 中栏：实时预览 */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <Card title="实时预览" size="small" bodyStyle={{ padding: 8 }}>
              <img
                src="/api/tv/stream"
                alt="TV 实时画面"
                style={{ width: '100%', display: 'block', borderRadius: 4, background: '#000' }}
              />
            </Card>
          </div>

          {/* 右栏：步骤进度 */}
          <div style={{
            width: 350, flexShrink: 0,
            overflow: 'auto', padding: '12px',
            background: '#fff', borderRadius: 8, border: '1px solid #f0f0f0',
          }}>
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12 }}>
              步骤进度 {replayStatus ? `${replayStatus.current_step}/${replayStatus.total_steps}` : ''}
            </div>
            {(replayStatus?.steps_overview || []).map((step, idx) => {
              const stepResult = (replayStatus?.step_results || [])[idx]
              const currentStep = replayStatus?.current_step || 0
              const isCompleted = stepResult != null
              const isRunning = !isCompleted && idx + 1 === currentStep
              const isPending = !isCompleted && !isRunning

              return (
                <div key={idx} style={{
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                  padding: '8px 10px', marginBottom: 4,
                  background: isRunning ? '#e6f7ff' : isCompleted ? '#f6ffed' : '#fafafa',
                  border: `1px solid ${isRunning ? '#91d5ff' : isCompleted ? '#b7eb8f' : '#f0f0f0'}`,
                  borderRadius: 6, fontSize: 13, transition: 'all 0.3s',
                }}>
                  <div style={{ flexShrink: 0, marginTop: 2 }}>
                    {isCompleted ? (
                      <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 16 }} />
                    ) : isRunning ? (
                      <LoadingOutlined style={{ color: '#1890ff', fontSize: 16 }} />
                    ) : (
                      <ClockCircleOutlined style={{ color: '#d9d9d9', fontSize: 16 }} />
                    )}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Tag color={
                        step.type === 'key_group' ? 'blue' :
                        step.type === 'adb_command' ? 'orange' :
                        step.type === 'ai_navigate' ? 'purple' :
                        step.type === 'ai_verify' ? 'green' : 'default'
                      } style={{ margin: 0 }}>
                        {step.type === 'key_group' ? '按键' :
                         step.type === 'adb_command' ? 'ADB' :
                         step.type === 'ai_navigate' ? 'AI导航' :
                         step.type === 'ai_verify' ? 'AI验证' : step.type}
                      </Tag>
                      <span style={{ fontWeight: 500 }}>#{idx + 1}</span>
                    </div>
                    <div style={{ marginTop: 4, color: '#666', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {step.summary}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : recording ? (
        /* ===== 录制中：三栏布局 ===== */
        <div style={{ display: 'flex', gap: 12, height: 'calc(100vh - 130px)' }}>
          {/* 左栏：用例详情 */}
          <div style={{
            width: 320, flexShrink: 0,
            overflow: 'auto', padding: '12px',
            background: '#fff', borderRadius: 8, border: '1px solid #f0f0f0',
          }}>
            {caseDetailContent || <span style={{ color: '#999' }}>未选择用例</span>}
          </div>

          {/* 中栏：预览 + 操作面板 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0, overflow: 'auto' }}>
            <Card title="实时预览" size="small" bodyStyle={{ padding: 8 }}>
              <img
                src="/api/tv/stream"
                alt="TV 实时画面"
                style={{ width: '100%', display: 'block', borderRadius: 4, background: '#000' }}
              />
            </Card>
            {operationPanel}
          </div>

          {/* 右栏：已录制步骤 */}
          <div style={{ width: 380, flexShrink: 0 }}>
            {stepsPanel}
          </div>
        </div>
      ) : (
        /* ===== 未录制：原有布局 ===== */
        <>
          {caseDetail && (
            <Card title={`用例详情 — ${caseDetail.key || ''} ${caseDetail.name || caseDetail.summary || ''}`} style={{ marginBottom: 12 }} size="small">
              {caseDetailContent}
            </Card>
          )}

          <div style={{ display: 'flex', gap: 16 }}>
            <div style={{ flex: 1 }}>
              <Card title="实时预览" size="small" bodyStyle={{ padding: 8 }}>
                <img
                  src="/api/tv/stream"
                  alt="TV 实时画面"
                  style={{ width: '100%', maxHeight: 400, border: '1px solid #d9d9d9', borderRadius: 4, background: '#000' }}
                />
              </Card>
            </div>

            <div style={{ width: 400 }}>
              {stepsPanel}
            </div>
          </div>
        </>
      )}

      <Modal
        title={modalMode === 'insert' ? `在位置 ${modalIndex} 插入步骤` : `修改第 ${modalIndex + 1} 步`}
        open={modalVisible}
        onOk={handleModalOk}
        onCancel={() => setModalVisible(false)}
        okText={modalMode === 'insert' ? '插入' : '保存'}
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 8 }}>类型：</span>
          <Radio.Group value={modalStepType} onChange={e => setModalStepType(e.target.value)}>
            <Radio.Button value="key">按键</Radio.Button>
            <Radio.Button value="adb_command">ADB 命令</Radio.Button>
            <Radio.Button value="ai">AI 指令</Radio.Button>
          </Radio.Group>
        </div>

        {modalStepType === 'key' && (
          <Select
            style={{ width: '100%' }}
            value={modalKey}
            onChange={setModalKey}
            showSearch
            options={COMMON_KEYS.map(k => ({ label: k, value: k }))}
          />
        )}

        {modalStepType === 'adb_command' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Input placeholder="ADB 命令" value={modalAdbCmd} onChange={e => setModalAdbCmd(e.target.value)} />
            <Input placeholder="描述（可选）" value={modalAdbDesc} onChange={e => setModalAdbDesc(e.target.value)} />
          </Space>
        )}

        {modalStepType === 'ai' && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Radio.Group value={modalAiType} onChange={e => setModalAiType(e.target.value)}>
              <Radio.Button value="ai_navigate">AI 导航</Radio.Button>
              <Radio.Button value="ai_verify">AI 验证</Radio.Button>
            </Radio.Group>
            <Input.TextArea placeholder="AI 指令描述" value={modalAiPrompt} onChange={e => setModalAiPrompt(e.target.value)} rows={3} />
          </Space>
        )}
      </Modal>
    </div>
  )
}
