import React, { useState, useEffect, useRef } from 'react'
import { Card, Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Tag, message, Popconfirm, Progress, Descriptions, Badge, Row, Col, Tooltip, Drawer, Image, Collapse, Tabs } from 'antd'
import { PlusOutlined, PlayCircleOutlined, EditOutlined, DeleteOutlined, EyeOutlined, StopOutlined, EyeInvisibleOutlined, CaretRightOutlined, VideoCameraOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { getPlans, getPlan, createPlan, updatePlan, deletePlan, runPlan, stopPlan, getPlanStatus, getPlanResults, getCases, getReplayResult, getRunResult } from '../api'

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
  const handleViewCaseDetail = async (caseKey, replayTimestamp) => {
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
      render: (_, r) => r.replay_timestamp ? (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewCaseDetail(r.key, r.replay_timestamp)} />
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

  // 渲染用例回放详情抽屉内容
  const renderCaseDetailContent = () => {
    if (caseDetailLoading) return <div style={{ textAlign: 'center', padding: 40 }}>加载中...</div>
    if (!caseDetailData) return null

    const d = caseDetailData
    const hasVideo = d.has_video && d.video_url
    const steps = d.steps || []

    return (
      <div>
        {/* 基本信息 */}
        <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
          <Descriptions.Item label="用例">{d.jira_key || d.case_key}</Descriptions.Item>
          <Descriptions.Item label="结果">
            <Tag color={d.result === 'passed' ? 'green' : 'red'}>{d.result === 'passed' ? '通过' : '失败'}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="时间">{d.replay_at || ''}</Descriptions.Item>
          <Descriptions.Item label="耗时">{d.duration_s || 0}s</Descriptions.Item>
          {d.failed_reason && <Descriptions.Item label="失败原因" span={2}>{d.failed_reason}</Descriptions.Item>}
        </Descriptions>

        {/* 回放视频 */}
        {hasVideo && (
          <Card size="small" title={<><VideoCameraOutlined /> 回放视频</>} style={{ marginBottom: 16 }}>
            <video
              src={d.video_url}
              controls
              style={{ width: '100%', maxHeight: 400, background: '#000' }}
            />
          </Card>
        )}

        {/* 步骤列表 */}
        {steps.length > 0 && (
          <Card size="small" title={`步骤详情 (${steps.length} 步)`}>
            <div style={{ maxHeight: 500, overflow: 'auto' }}>
              {steps.map((step, i) => {
                const isPassed = step.status === 'passed'
                const isFailed = step.status === 'failed'
                const screenshotUrl = getScreenshotUrl(step.screenshot)

                return (
                  <div key={i} style={{
                    padding: '8px 12px',
                    marginBottom: 8,
                    border: `1px solid ${isFailed ? '#ffccc7' : isPassed ? '#d9f7be' : '#f0f0f0'}`,
                    borderRadius: 4,
                    background: isFailed ? '#fff2f0' : isPassed ? '#f6ffed' : '#fff',
                  }}>
                    <Row align="middle" gutter={8}>
                      <Col>
                        {isPassed ? <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                         isFailed ? <CloseCircleOutlined style={{ color: '#ff4d4f' }} /> :
                         <span style={{ color: '#999' }}>○</span>}
                      </Col>
                      <Col>
                        <span style={{ color: '#999' }}>{i + 1}.</span>
                      </Col>
                      <Col flex="auto">
                        <span style={{ fontWeight: 500 }}>{step.summary || step.type || '步骤'}</span>
                        {step.duration_s != null && <span style={{ color: '#999', marginLeft: 8 }}>{step.duration_s}s</span>}
                      </Col>
                    </Row>
                    {step.error && <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4, marginLeft: 36 }}>{step.error}</div>}
                    {screenshotUrl && (
                      <div style={{ marginTop: 8, marginLeft: 36 }}>
                        <Image src={screenshotUrl} width={300} style={{ borderRadius: 4, border: '1px solid #d9d9d9' }} />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </Card>
        )}
      </div>
    )
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
              options={cases.map(c => ({ label: `${c.key} - ${c.name}`, value: c.key }))}
              optionFilterProp="label"
              showSearch
            />
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
        onClose={() => { setCaseDetailDrawer(false); setCaseDetailData(null) }}
        width={720}
      >
        {renderCaseDetailContent()}
      </Drawer>
    </div>
  )
}
