import React, { useState, useEffect, useRef } from 'react'
import { Card, Table, Button, Space, Modal, Form, Input, Select, Switch, Tag, message, Popconfirm, Progress, Descriptions, Collapse } from 'antd'
import { PlusOutlined, PlayCircleOutlined, EditOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { getPlans, getPlan, createPlan, updatePlan, deletePlan, runPlan, getPlanStatus, getPlanResults, getCases } from '../api'

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
  const [form] = Form.useForm()
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
    } catch (e) {
      // 静默
    }
  }

  const fetchPlanStatus = async (id) => {
    try {
      const res = await getPlanStatus(id)
      const data = res.data?.data || res.data
      setPlanStatus(data)
      if (!data?.running) {
        setRunningPlanId(null)
        if (timerRef.current) clearInterval(timerRef.current)
        fetchPlans()
      }
    } catch (e) {
      // 静默
    }
  }

  useEffect(() => {
    fetchPlans()
    fetchCases()
  }, [])

  useEffect(() => {
    if (runningPlanId) {
      timerRef.current = setInterval(() => fetchPlanStatus(runningPlanId), 2000)
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

  const handleRun = async (id) => {
    try {
      await runPlan(id)
      message.success('计划开始执行')
      setRunningPlanId(id)
    } catch (e) {
      message.error('执行失败: ' + (e.response?.data?.error || e.message))
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

  const columns = [
    { title: '计划名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '用例数', dataIndex: 'case_count', key: 'case_count', width: 80, render: (v, r) => v || r.cases?.length || 0 },
    { title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 180 },
    {
      title: '操作', key: 'action', width: 280,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handleRun(record.id)} disabled={!!runningPlanId}>执行</Button>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewResults(record.id)}>结果</Button>
          <Popconfirm title="确定删除此计划？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      )
    }
  ]

  return (
    <div>
      <h2>测试计划</h2>

      {runningPlanId && planStatus && (
        <Card style={{ marginBottom: 16 }}>
          <p>正在执行计划... 当前第 {planStatus.current || 0} 条 / 共 {planStatus.total || 0} 条</p>
          <Progress percent={planStatus.total ? Math.round((planStatus.current / planStatus.total) * 100) : 0} />
        </Card>
      )}

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

      <Modal
        title="执行结果"
        open={resultsModalVisible}
        onCancel={() => setResultsModalVisible(false)}
        footer={null}
        width={700}
      >
        {planResults && (
          <div>
            {planResults.summary && (
              <Descriptions bordered size="small" column={3} style={{ marginBottom: 16 }}>
                <Descriptions.Item label="总用例数">{planResults.summary.total || 0}</Descriptions.Item>
                <Descriptions.Item label="通过">{planResults.summary.passed || 0}</Descriptions.Item>
                <Descriptions.Item label="失败">{planResults.summary.failed || 0}</Descriptions.Item>
              </Descriptions>
            )}
            <Table
              size="small"
              dataSource={planResults.results || planResults.cases || []}
              rowKey={(r) => r.case_key || r.key || Math.random()}
              columns={[
                { title: '用例', dataIndex: 'case_key', key: 'case_key' },
                {
                  title: '结果', dataIndex: 'result', key: 'result',
                  render: (v) => <Tag color={v === 'passed' ? 'green' : v === 'failed' ? 'red' : 'default'}>{v || '-'}</Tag>
                },
                { title: '时长', dataIndex: 'duration', key: 'duration', render: (v) => v ? `${v}s` : '-' },
                { title: '错误信息', dataIndex: 'error', key: 'error', ellipsis: true },
              ]}
              pagination={false}
            />
          </div>
        )}
      </Modal>
    </div>
  )
}
