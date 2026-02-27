import React, { useState, useEffect, useRef } from 'react'
import { Card, Select, Button, Space, Table, Input, Tag, message, Alert, Divider, Radio, Modal, Popconfirm } from 'antd'
import { PlayCircleOutlined, PauseOutlined, DeleteOutlined, SendOutlined, PlusOutlined, EditOutlined } from '@ant-design/icons'
import { getCases, getCase, startRecording, stopRecording, getRecordingStatus, insertAdb, insertAi, deleteLastStep, insertStepAt, deleteStep, getSavedSteps, insertSavedStep, deleteSavedStep, updateSavedStep } from '../api'

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
      const keys = (s.commands || []).map(c => c.key || '?').join(' → ')
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

  return (
    <div>
      <h2>录制</h2>

      <Card style={{ marginBottom: 16 }}>
        <Space size="middle" wrap>
          <span style={{ fontWeight: 'bold' }}>选择用例：</span>
          <Select
            style={{ width: 300 }}
            placeholder="请选择要录制的用例"
            value={selectedCase}
            onChange={handleCaseChange}
            disabled={recording}
            showSearch
            optionFilterProp="label"
            options={cases.map(c => ({ label: `${c.key} - ${c.name}`, value: c.key }))}
          />
          {!recording ? (
            <Button type="primary" icon={<PlayCircleOutlined />}
              onClick={(e) => { e.currentTarget.blur(); handleStart(); }}
              onKeyDown={(e) => e.preventDefault()}
            >开始录制</Button>
          ) : (
            <Button danger icon={<PauseOutlined />}
              onClick={(e) => { e.currentTarget.blur(); handleStop(); }}
              onKeyDown={(e) => e.preventDefault()}
            >停止录制</Button>
          )}
        </Space>

        {recording && (
          <Alert
            style={{ marginTop: 12 }}
            type="info"
            message={`录制中 — 已录制 ${displayItems.length} 步`}
            showIcon
          />
        )}
      </Card>

      {caseDetail && (
        <Card title={`用例详情 — ${caseDetail.key || ''} ${caseDetail.name || caseDetail.summary || ''}`} style={{ marginBottom: 16 }} size="small">
          {caseDetail.precondition && (
            <div style={{ marginBottom: 12 }}>
              <strong>前置条件：</strong>
              <div style={{ whiteSpace: 'pre-wrap', color: '#555', marginTop: 4, padding: '8px 12px', background: '#fff7e6', border: '1px solid #ffe7ba', borderRadius: 4 }}>
                {caseDetail.precondition}
              </div>
            </div>
          )}
          {caseDetail.description && (
            <div style={{ marginBottom: 12 }}>
              <strong>描述：</strong>
              <div style={{ whiteSpace: 'pre-wrap', color: '#555', marginTop: 4, padding: '8px 12px', background: '#fafafa', borderRadius: 4 }}>
                {caseDetail.description}
              </div>
            </div>
          )}
          {caseDetail.test_steps && caseDetail.test_steps.length > 0 && (
            <div>
              <strong>测试步骤：</strong>
              <Table
                style={{ marginTop: 4 }}
                size="small"
                pagination={false}
                dataSource={caseDetail.test_steps}
                rowKey={(r) => r.sequenceNumber || r.step}
                columns={[
                  { title: '序号', dataIndex: 'sequenceNumber', key: 'seq', width: 60 },
                  { title: '操作步骤', dataIndex: 'step', key: 'step' },
                  { title: '期望结果', dataIndex: 'expectedResult', key: 'expected' },
                  { title: '测试数据', dataIndex: 'stepData', key: 'data', render: (v) => v || '-' },
                ]}
              />
            </div>
          )}
          {(!caseDetail.test_steps || caseDetail.test_steps.length === 0) && !caseDetail.description && !caseDetail.precondition && (
            <span style={{ color: '#999' }}>该用例无详细步骤信息</span>
          )}
        </Card>
      )}

      <div style={{ display: 'flex', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <Card title="实时预览" style={{ marginBottom: 16 }}>
            <img
              src="/api/tv/stream"
              alt="TV 实时画面"
              style={{ width: '100%', maxHeight: 400, border: '1px solid #d9d9d9', borderRadius: 4, background: '#000' }}
            />
          </Card>

          <Card title="操作面板">
            <div style={{ marginBottom: 16 }}>
              <h4>插入 ADB 命令</h4>
              <Space>
                <Input
                  placeholder="ADB 命令"
                  value={adbCommand}
                  onChange={e => setAdbCommand(e.target.value)}
                  style={{ width: 250 }}
                  disabled={!recording}
                />
                <Input
                  placeholder="描述（可选）"
                  value={adbDesc}
                  onChange={e => setAdbDesc(e.target.value)}
                  style={{ width: 150 }}
                  disabled={!recording}
                />
                <Button icon={<SendOutlined />} onClick={handleInsertAdb} disabled={!recording}>插入</Button>
              </Space>
            </div>
            <Divider />
            <div>
              <h4>插入 AI 指令</h4>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio.Group value={aiType} onChange={e => setAiType(e.target.value)} disabled={!recording}>
                  <Radio.Button value="ai_navigate">AI 导航</Radio.Button>
                  <Radio.Button value="ai_verify">AI 验证</Radio.Button>
                </Radio.Group>
                <Space>
                  <Input.TextArea
                    placeholder="AI 指令描述"
                    value={aiPrompt}
                    onChange={e => setAiPrompt(e.target.value)}
                    style={{ width: 400 }}
                    rows={2}
                    disabled={!recording}
                  />
                  <Button icon={<SendOutlined />} onClick={handleInsertAi} disabled={!recording}>插入</Button>
                </Space>
              </Space>
            </div>
          </Card>
        </div>

        <div style={{ width: 400 }}>
          <Card
            title={`已录制步骤 (${displayItems.length})`}
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
              scroll={{ y: 500 }}
            />
          </Card>
        </div>
      </div>

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
