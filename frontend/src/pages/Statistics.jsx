import React, { useState, useEffect } from 'react'
import { Card, Row, Col, Statistic, Table, Tag, Select, Space, message } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, PlayCircleOutlined, ClockCircleOutlined, StopOutlined, FolderOutlined } from '@ant-design/icons'
import { getStats, getModules } from '../api'

export default function Statistics() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(false)
  const [modules, setModules] = useState([])
  const [moduleFilter, setModuleFilter] = useState(undefined)

  const fetchStats = async () => {
    setLoading(true)
    try {
      const res = await getStats()
      setStats(res.data?.data || res.data)
    } catch (e) {
      message.error('获取统计数据失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setLoading(false)
    }
  }

  const fetchModules = async () => {
    try {
      const res = await getModules()
      setModules(res.data?.data || [])
    } catch (e) { /* ignore */ }
  }

  useEffect(() => { fetchStats(); fetchModules() }, [])

  const rawSummary = stats?.summary || {}
  const caseStats = stats?.case_stats || []
  const recentResults = stats?.recent_results || []

  const filterByModule = (list) => {
    if (moduleFilter === undefined) return list
    if (moduleFilter === '__none__') return list.filter(r => !r.module)
    return list.filter(r => r.module === moduleFilter)
  }

  // 根据模块筛选重新计算汇总指标
  const summary = (() => {
    if (moduleFilter === undefined) return rawSummary
    const filtered = filterByModule(caseStats)
    const totalRuns = filtered.reduce((s, c) => s + c.total, 0)
    const passed = filtered.reduce((s, c) => s + c.passed, 0)
    const failed = filtered.reduce((s, c) => s + c.failed, 0)
    const aborted = totalRuns - passed - failed
    const filteredRecent = filterByModule(recentResults)
    const totalDuration = filteredRecent.reduce((s, r) => s + (r.duration || 0), 0)
    return {
      total_runs: totalRuns,
      pass_rate: totalRuns > 0 ? passed / totalRuns : 0,
      fail_rate: totalRuns > 0 ? failed / totalRuns : 0,
      abort_rate: totalRuns > 0 ? aborted / totalRuns : 0,
      avg_duration: totalRuns > 0 ? Math.round(totalDuration / totalRuns) : 0,
    }
  })()

  const caseColumns = [
    { title: '用例 Key', dataIndex: 'case_key', key: 'case_key' },
    {
      title: '模块', dataIndex: 'module', key: 'module', width: 120,
      render: (v) => v ? <Tag icon={<FolderOutlined />}>{v}</Tag> : <span style={{ color: '#ccc' }}>-</span>
    },
    { title: '总次数', dataIndex: 'total', key: 'total', width: 80 },
    { title: '通过', dataIndex: 'passed', key: 'passed', width: 80 },
    { title: '失败', dataIndex: 'failed', key: 'failed', width: 80 },
    {
      title: '通过率', dataIndex: 'pass_rate', key: 'pass_rate', width: 100,
      render: (v) => v != null ? `${(v * 100).toFixed(1)}%` : '-'
    },
  ]

  const recentColumns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
    { title: '用例', dataIndex: 'case_key', key: 'case_key' },
    {
      title: '模块', dataIndex: 'module', key: 'module', width: 120,
      render: (v) => v ? <Tag icon={<FolderOutlined />}>{v}</Tag> : <span style={{ color: '#ccc' }}>-</span>
    },
    { title: '执行人', dataIndex: 'executor', key: 'executor', width: 100 },
    {
      title: '结果', dataIndex: 'result', key: 'result', width: 80,
      render: (v) => <Tag color={v === 'passed' ? 'green' : v === 'failed' ? 'red' : 'default'}>{v || '-'}</Tag>
    },
    { title: '时长', dataIndex: 'duration', key: 'duration', width: 100, render: (v) => v ? `${v}s` : '-' },
  ]

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>统计报表</h2>

      <Space style={{ marginBottom: 16 }}>
        <span>模块筛选：</span>
        <Select
          placeholder="全部模块"
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 160 }}
          value={moduleFilter}
          onChange={(v) => setModuleFilter(v)}
          options={[...modules.map(m => ({ label: m, value: m })), { label: '未分组', value: '__none__' }]}
        />
      </Space>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card>
            <Statistic title="总回放次数" value={summary.total_runs || 0} prefix={<PlayCircleOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="通过率" value={summary.pass_rate != null ? (summary.pass_rate * 100).toFixed(1) : 0} suffix="%" prefix={<CheckCircleOutlined />} valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="失败率" value={summary.fail_rate != null ? (summary.fail_rate * 100).toFixed(1) : 0} suffix="%" prefix={<CloseCircleOutlined />} valueStyle={{ color: '#cf1322' }} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="中断率" value={summary.abort_rate != null ? (summary.abort_rate * 100).toFixed(1) : 0} suffix="%" prefix={<StopOutlined />} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic title="平均时长" value={summary.avg_duration || 0} suffix="s" prefix={<ClockCircleOutlined />} />
          </Card>
        </Col>
      </Row>

      <Card title="各用例统计" style={{ marginBottom: 16 }}>
        <Table
          columns={caseColumns}
          dataSource={filterByModule(caseStats)}
          rowKey="case_key"
          loading={loading}
          size="small"
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Card title="最近回放记录">
        <Table
          columns={recentColumns}
          dataSource={filterByModule(recentResults)}
          rowKey={(r) => r.timestamp || Math.random()}
          loading={loading}
          size="small"
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  )
}
