import React, { useState, useEffect } from 'react'
import { Card, Table, Button, Space, Input, Select, Tag, Modal, Form, Drawer, message, Popconfirm, Descriptions } from 'antd'
import { PlusOutlined, ImportOutlined, SyncOutlined, DeleteOutlined, EyeOutlined } from '@ant-design/icons'
import { getCases, getCase, importByJql, importByKey, syncCase, createCase, deleteCase } from '../api'

const { Search } = Input

export default function CaseManagement() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [sourceFilter, setSourceFilter] = useState('')
  const [jqlModal, setJqlModal] = useState(false)
  const [keyModal, setKeyModal] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [detailDrawer, setDetailDrawer] = useState(false)
  const [caseDetail, setCaseDetail] = useState(null)
  const [jqlForm] = Form.useForm()
  const [keyForm] = Form.useForm()
  const [createForm] = Form.useForm()

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
      await createCase(values)
      message.success('用例创建成功')
      setCreateModal(false)
      createForm.resetFields()
      fetchCases()
    } catch (e) {
      message.error('创建失败: ' + (e.response?.data?.error || e.message))
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
      title: '操作', key: 'action', width: 200,
      render: (_, record) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewDetail(record.key)}>详情</Button>
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

      <Modal title="新建用例" open={createModal} onCancel={() => setCreateModal(false)} onOk={() => createForm.submit()} destroyOnClose>
        <Form form={createForm} onFinish={handleCreate} layout="vertical">
          <Form.Item label="用例名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="用例名称" />
          </Form.Item>
          <Form.Item label="描述" name="description">
            <Input.TextArea rows={3} placeholder="用例描述" />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer title="用例详情" open={detailDrawer} onClose={() => setDetailDrawer(false)} width={600}>
        {caseDetail && (
          <Descriptions column={1} bordered size="small">
            {Object.entries(caseDetail).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>
                {typeof v === 'object' ? <pre style={{ margin: 0, fontSize: 12 }}>{JSON.stringify(v, null, 2)}</pre> : String(v ?? '')}
              </Descriptions.Item>
            ))}
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}
