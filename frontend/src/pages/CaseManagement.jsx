import React, { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Input, Select, Tag, Modal, Form, Drawer, message, Popconfirm, Descriptions } from 'antd'
import { PlusOutlined, ImportOutlined, SyncOutlined, DeleteOutlined, EyeOutlined, EditOutlined, CopyOutlined, MinusCircleOutlined } from '@ant-design/icons'
import { getCases, getCase, importByJql, importByKey, syncCase, createCase, updateCase, copyCase, deleteCase } from '../api'

const { Search } = Input

// 测试步骤编辑组件
function TestStepsField() {
  return (
    <Form.List name="test_steps">
      {(fields, { add, remove }) => (
        <div>
          {fields.map(({ key, name, ...restField }) => (
            <div key={key} style={{ display: 'flex', gap: 8, marginBottom: 8, alignItems: 'flex-start' }}>
              <span style={{ lineHeight: '32px', minWidth: 24, color: '#999' }}>{name + 1}.</span>
              <Form.Item {...restField} name={[name, 'step']} style={{ flex: 1, marginBottom: 0 }}>
                <Input placeholder="测试步骤" />
              </Form.Item>
              <Form.Item {...restField} name={[name, 'expectedResult']} style={{ flex: 1, marginBottom: 0 }}>
                <Input placeholder="期望结果" />
              </Form.Item>
              <MinusCircleOutlined onClick={() => remove(name)} style={{ lineHeight: '32px', color: '#ff4d4f', cursor: 'pointer' }} />
            </div>
          ))}
          <Button type="dashed" onClick={() => add({ step: '', expectedResult: '' })} block icon={<PlusOutlined />}>
            添加步骤
          </Button>
        </div>
      )}
    </Form.List>
  )
}

export default function CaseManagement() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [jqlModal, setJqlModal] = useState(false)
  const [keyModal, setKeyModal] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [editModal, setEditModal] = useState(false)
  const [editingCase, setEditingCase] = useState(null)
  const [detailDrawer, setDetailDrawer] = useState(false)
  const [caseDetail, setCaseDetail] = useState(null)
  const [jqlForm] = Form.useForm()
  const [keyForm] = Form.useForm()
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()

  const fetchCases = async () => {
    setLoading(true)
    try {
      const params = {}
      if (keyword) params.keyword = keyword
      if (sourceFilter) params.source = sourceFilter
      const res = await getCases(params)
      const data = res.data?.data || res.data?.cases || []
      setCases(Array.isArray(data) ? data : [])
    } catch (e) {
      message.error('获取用例列表失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchCases() }, [keyword, sourceFilter])

  const handleViewDetail = async (key) => {
    try {
      const res = await getCase(key)
      setCaseDetail(res.data?.data || res.data)
      setDetailDrawer(true)
    } catch (e) {
      message.error('获取用例详情失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleJqlImport = async (values) => {
    try {
      await importByJql(values.jql)
      message.success('JQL 导入成功')
      setJqlModal(false)
      jqlForm.resetFields()
      fetchCases()
    } catch (e) {
      message.error('JQL 导入失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleKeyImport = async (values) => {
    try {
      await importByKey(values.key)
      message.success('导入成功')
      setKeyModal(false)
      keyForm.resetFields()
      fetchCases()
    } catch (e) {
      message.error('导入失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleCreate = async (values) => {
    try {
      // 过滤掉空步骤
      if (values.test_steps) {
        values.test_steps = values.test_steps.filter(s => s.step || s.expectedResult)
      }
      await createCase(values)
      message.success('用例创建成功')
      setCreateModal(false)
      createForm.resetFields()
      fetchCases()
    } catch (e) {
      message.error('创建失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleEdit = async (key) => {
    try {
      const res = await getCase(key)
      const data = res.data?.data || res.data
      setEditingCase(data)
      editForm.setFieldsValue({
        name: data.name || data.summary || '',
        description: data.description || '',
        precondition: data.precondition || '',
        test_steps: data.test_steps?.length ? data.test_steps : [],
      })
      setEditModal(true)
    } catch (e) {
      message.error('获取用例详情失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleEditSubmit = async (values) => {
    try {
      if (values.test_steps) {
        values.test_steps = values.test_steps.filter(s => s.step || s.expectedResult)
      }
      await updateCase(editingCase.key, values)
      message.success('用例已更新')
      setEditModal(false)
      setEditingCase(null)
      editForm.resetFields()
      fetchCases()
    } catch (e) {
      message.error('更新失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleCopy = async (key) => {
    try {
      const res = await copyCase(key)
      message.success(res.data?.message || '复制成功')
      fetchCases()
    } catch (e) {
      message.error('复制失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleSync = async (key) => {
    try {
      await syncCase(key)
      message.success('同步成功')
      fetchCases()
    } catch (e) {
      message.error('同步失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleDelete = async (key) => {
    try {
      await deleteCase(key)
      message.success('已删除')
      fetchCases()
    } catch (e) {
      message.error('删除失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const columns = [
    { title: 'Key', dataIndex: 'key', key: 'key', width: 120 },
    { title: '名称', dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: '来源', dataIndex: 'source', key: 'source', width: 100,
      render: (v) => <Tag color={v === 'jira' ? 'blue' : 'orange'}>{v === 'jira' ? 'Jira' : '自定义'}</Tag>
    },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
    {
      title: '录制状态', dataIndex: 'recorded', key: 'recorded', width: 100,
      render: (v) => <Tag color={v ? 'green' : 'default'}>{v ? '已录制' : '未录制'}</Tag>
    },
    {
      title: '最近回放', dataIndex: 'last_result', key: 'last_result', width: 100,
      render: (v) => {
        if (!v) return '-'
        const colorMap = { passed: 'green', failed: 'red' }
        return <Tag color={colorMap[v] || 'default'}>{v}</Tag>
      }
    },
    {
      title: '操作', key: 'action', width: 260,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record.key)}>详情</Button>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record.key)}>编辑</Button>
          <Button type="link" size="small" icon={<CopyOutlined />} onClick={() => handleCopy(record.key)}>复制</Button>
          {record.source === 'jira' && (
            <Button type="link" size="small" icon={<SyncOutlined />} onClick={() => handleSync(record.key)}>同步</Button>
          )}
          <Popconfirm title="确定删除此用例？" onConfirm={() => handleDelete(record.key)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      )
    },
  ]

  // 详情抽屉中格式化展示
  const renderDetailContent = () => {
    if (!caseDetail) return null
    const d = caseDetail
    const isJira = d.source === 'jira'

    return (
      <div>
        <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="Key">{d.key}</Descriptions.Item>
          <Descriptions.Item label="名称">{d.name || d.summary || ''}</Descriptions.Item>
          <Descriptions.Item label="来源">
            <Tag color={isJira ? 'blue' : 'orange'}>{isJira ? 'Jira' : '自定义'}</Tag>
          </Descriptions.Item>
          {d.priority && <Descriptions.Item label="优先级">{d.priority}</Descriptions.Item>}
          {d.description && <Descriptions.Item label="描述">{d.description}</Descriptions.Item>}
          {d.precondition && <Descriptions.Item label="前置条件">{d.precondition}</Descriptions.Item>}
          {d.created_at && <Descriptions.Item label="创建时间">{d.created_at}</Descriptions.Item>}
          {d.updated_at && <Descriptions.Item label="更新时间">{d.updated_at}</Descriptions.Item>}
        </Descriptions>

        {d.test_steps && d.test_steps.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>测试步骤</h4>
            <Table
              dataSource={d.test_steps.map((s, i) => ({ ...s, _idx: i }))}
              rowKey="_idx"
              size="small"
              pagination={false}
              columns={[
                { title: '序号', width: 60, render: (_, __, i) => i + 1 },
                { title: '步骤', dataIndex: 'step', key: 'step' },
                { title: '期望结果', dataIndex: 'expectedResult', key: 'expectedResult' },
              ]}
            />
          </div>
        )}

        {d.recorded_steps && d.recorded_steps.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4>录制步骤 ({d.recorded_steps.length} 步)</h4>
            <pre style={{ fontSize: 12, maxHeight: 300, overflow: 'auto', background: '#f5f5f5', padding: 8, borderRadius: 4 }}>
              {JSON.stringify(d.recorded_steps, null, 2)}
            </pre>
          </div>
        )}
      </div>
    )
  }

  // 用例表单字段（创建和编辑共用）
  const renderCaseFormFields = (isEdit = false) => (
    <>
      <Form.Item label="用例名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
        <Input placeholder="用例名称" disabled={isEdit && editingCase?.source === 'jira'} />
      </Form.Item>
      <Form.Item label="描述" name="description">
        <Input.TextArea rows={2} placeholder="用例描述" disabled={isEdit && editingCase?.source === 'jira'} />
      </Form.Item>
      <Form.Item label="前置条件" name="precondition">
        <Input.TextArea rows={2} placeholder="前置条件" />
      </Form.Item>
      <Form.Item label="测试步骤">
        <TestStepsField />
      </Form.Item>
    </>
  )

  return (
    <div>
      <h2>用例管理</h2>

      <Card>
        <Space style={{ marginBottom: 16 }} wrap>
          <Search placeholder="搜索用例" allowClear onSearch={setKeyword} style={{ width: 250 }} />
          <Select
            placeholder="来源筛选"
            allowClear
            style={{ width: 120 }}
            onChange={(v) => setSourceFilter(v || '')}
            options={[
              { label: '全部', value: '' },
              { label: 'Jira', value: 'jira' },
              { label: '自定义', value: 'custom' },
            ]}
          />
          <Button icon={<ImportOutlined />} onClick={() => setJqlModal(true)}>JQL 导入</Button>
          <Button icon={<ImportOutlined />} onClick={() => setKeyModal(true)}>单条导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModal(true)}>新建用例</Button>
        </Space>

        <Table
          columns={columns}
          dataSource={cases}
          rowKey="key"
          loading={loading}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal title="JQL 导入" open={jqlModal} onCancel={() => setJqlModal(false)} onOk={() => jqlForm.submit()} destroyOnClose>
        <Form form={jqlForm} onFinish={handleJqlImport} layout="vertical">
          <Form.Item label="JQL 查询语句" name="jql" rules={[{ required: true, message: '请输入 JQL' }]}>
            <Input.TextArea rows={3} placeholder='project = TV AND type = "Test Case"' />
          </Form.Item>
        </Form>
      </Modal>

      <Modal title="单条导入" open={keyModal} onCancel={() => setKeyModal(false)} onOk={() => keyForm.submit()} destroyOnClose>
        <Form form={keyForm} onFinish={handleKeyImport} layout="vertical">
          <Form.Item label="Jira Key" name="key" rules={[{ required: true, message: '请输入 Jira Key' }]}>
            <Input placeholder="PROJ-101" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 新建用例 */}
      <Modal title="新建用例" open={createModal} onCancel={() => setCreateModal(false)} onOk={() => createForm.submit()} destroyOnClose width={640}>
        <Form form={createForm} onFinish={handleCreate} layout="vertical">
          {renderCaseFormFields(false)}
        </Form>
      </Modal>

      {/* 编辑用例 */}
      <Modal
        title={`编辑用例 ${editingCase?.key || ''}`}
        open={editModal}
        onCancel={() => { setEditModal(false); setEditingCase(null); editForm.resetFields() }}
        onOk={() => editForm.submit()}
        destroyOnClose
        width={640}
      >
        <Form form={editForm} onFinish={handleEditSubmit} layout="vertical">
          {renderCaseFormFields(true)}
        </Form>
      </Modal>

      <Drawer title="用例详情" open={detailDrawer} onClose={() => setDetailDrawer(false)} width={600}>
        {renderDetailContent()}
      </Drawer>
    </div>
  )
}
