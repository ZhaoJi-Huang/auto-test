import React, { useState, useEffect, useCallback } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Modal, Button, Space, Tag, Tooltip, message } from 'antd'
import {
  SettingOutlined, VideoCameraOutlined, ImportOutlined,
  PlayCircleOutlined, OrderedListOutlined, BarChartOutlined,
  BranchesOutlined, CheckCircleOutlined, CloseCircleOutlined,
  ExclamationCircleOutlined, LoadingOutlined, ReloadOutlined
} from '@ant-design/icons'
import { getHealth, updateConfig, getConfig } from './api'

import DeviceConfig from './pages/DeviceConfig'
import CaseManagement from './pages/CaseManagement'
import Recording from './pages/Recording'
import Replay from './pages/Replay'
import TestPlan from './pages/TestPlan'
import Statistics from './pages/Statistics'
import GitCollab from './pages/GitCollab'
import RemoteControl from './components/RemoteControl'

const { Sider, Header, Content } = Layout

const menuItems = [
  { key: '/', icon: <SettingOutlined />, label: '设备配置' },
  { key: '/cases', icon: <ImportOutlined />, label: '用例管理' },
  { key: '/recording', icon: <VideoCameraOutlined />, label: '录制' },
  { key: '/replay', icon: <PlayCircleOutlined />, label: '回放' },
  { key: '/plans', icon: <OrderedListOutlined />, label: '测试计划' },
  { key: '/stats', icon: <BarChartOutlined />, label: '统计报表' },
  { key: '/git', icon: <BranchesOutlined />, label: 'Git 协作' },
]

// 健康检查结果的状态标签
function HealthIndicator({ health, loading, onCheck }) {
  if (loading) {
    return <Tag icon={<LoadingOutlined />} color="processing">检查中...</Tag>
  }
  if (!health) {
    return (
      <Tooltip title="点击检查系统状态">
        <Tag style={{ cursor: 'pointer' }} onClick={onCheck} color="default">未检查</Tag>
      </Tooltip>
    )
  }

  const adb = health.checks?.adb_device?.status
  const cc = health.checks?.capture_card?.status

  const allOk = adb === 'connected' && cc === 'running'
  const hasIssue = adb === 'disconnected' || cc === 'stopped' || cc === 'error'

  return (
    <Tooltip title={
      <div>
        <div>ADB 设备: {adb === 'connected' ? '已连接' : adb === 'not_configured' ? '未配置' : '断开'}</div>
        <div>采集卡: {cc === 'running' ? '运行中' : '未启动'}</div>
        <div>磁盘剩余: {health.checks?.disk_free_mb ? `${health.checks.disk_free_mb} MB` : '未知'}</div>
        <div style={{ marginTop: 4, fontSize: 12, opacity: 0.7 }}>点击重新检查</div>
      </div>
    }>
      <Tag
        style={{ cursor: 'pointer' }}
        onClick={onCheck}
        icon={allOk ? <CheckCircleOutlined /> : hasIssue ? <CloseCircleOutlined /> : <ExclamationCircleOutlined />}
        color={allOk ? 'success' : hasIssue ? 'error' : 'warning'}
      >
        {allOk ? '系统正常' : '系统异常'}
      </Tag>
    </Tooltip>
  )
}

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [health, setHealth] = useState(null)
  const [healthLoading, setHealthLoading] = useState(false)
  const [reconnectVisible, setReconnectVisible] = useState(false)
  const [reconnecting, setReconnecting] = useState(false)

  const runHealthCheck = useCallback(async (showOk = false) => {
    setHealthLoading(true)
    try {
      const res = await getHealth()
      const data = res.data
      setHealth(data)

      const adb = data?.checks?.adb_device?.status
      const cc = data?.checks?.capture_card?.status
      const hasIssue = adb === 'disconnected' || cc === 'stopped' || cc === 'error'

      if (hasIssue) {
        setReconnectVisible(true)
      } else if (showOk) {
        message.success('系统状态正常')
      }
    } catch (e) {
      setHealth(null)
      message.error('健康检查失败: 无法连接后端服务')
    } finally {
      setHealthLoading(false)
    }
  }, [])

  // 进入应用时自动检查
  useEffect(() => {
    runHealthCheck()
  }, [])

  // 重连操作
  const handleReconnect = async () => {
    setReconnecting(true)
    try {
      // 获取当前配置中的 IP，触发重新连接
      const cfgRes = await getConfig()
      const tvIp = cfgRes.data?.tv_ip
      if (!tvIp) {
        message.warning('未配置设备 IP，请前往设备配置页设置')
        setReconnectVisible(false)
        navigate('/')
        setReconnecting(false)
        return
      }
      // 重新提交当前配置（后端会自动执行 adb connect）
      await updateConfig({ tv_ip: tvIp })
      // 再次检查
      const res = await getHealth()
      const data = res.data
      setHealth(data)

      const adb = data?.checks?.adb_device?.status
      if (adb === 'connected') {
        message.success('设备重连成功')
        setReconnectVisible(false)
      } else {
        message.error('重连失败，请检查设备网络连接')
      }
    } catch (e) {
      message.error('重连失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setReconnecting(false)
    }
  }

  // 生成异常详情描述
  const getIssueDescriptions = () => {
    if (!health?.checks) return []
    const issues = []
    const adb = health.checks.adb_device
    const cc = health.checks.capture_card
    if (adb?.status === 'disconnected') {
      issues.push(`ADB 设备断开${adb.detail ? `（${adb.detail}）` : ''}`)
    }
    if (adb?.status === 'not_configured') {
      issues.push('未配置设备 IP')
    }
    if (cc?.status === 'stopped') {
      issues.push('视频采集卡未启动')
    }
    if (cc?.status === 'error') {
      issues.push(`视频采集卡异常${cc.detail ? `（${cc.detail}）` : ''}`)
    }
    if (health.checks.disk_free_mb !== null && health.checks.disk_free_mb < 500) {
      issues.push(`磁盘空间不足（剩余 ${health.checks.disk_free_mb} MB）`)
    }
    return issues
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider width={200} theme="dark">
        <div style={{ height: 48, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold', fontSize: 16 }}>
          TV 自动化测试
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
        <div style={{ position: 'absolute', bottom: 16, width: '100%', display: 'flex', justifyContent: 'center' }}>
          <HealthIndicator health={health} loading={healthLoading} onCheck={() => runHealthCheck(true)} />
        </div>
      </Sider>
      <Layout>
        <Content style={{ padding: 24, background: '#f5f5f5', overflow: 'auto' }}>
          <Routes>
            <Route path="/" element={<DeviceConfig />} />
            <Route path="/cases" element={<CaseManagement />} />
            <Route path="/recording" element={<Recording onPreCheck={runHealthCheck} health={health} />} />
            <Route path="/replay" element={<Replay onPreCheck={runHealthCheck} health={health} />} />
            <Route path="/plans" element={<TestPlan />} />
            <Route path="/stats" element={<Statistics />} />
            <Route path="/git" element={<GitCollab />} />
          </Routes>
          {['/', '/recording', '/replay'].includes(location.pathname) && <RemoteControl />}
        </Content>
      </Layout>

      {/* 系统异常弹窗 */}
      <Modal
        title={<span><ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />系统状态异常</span>}
        open={reconnectVisible}
        onCancel={() => setReconnectVisible(false)}
        footer={[
          <Button key="close" onClick={() => setReconnectVisible(false)}>忽略</Button>,
          <Button key="config" onClick={() => { setReconnectVisible(false); navigate('/') }}>
            前往配置
          </Button>,
          <Button key="reconnect" type="primary" icon={<ReloadOutlined />} loading={reconnecting} onClick={handleReconnect}>
            尝试重连
          </Button>,
        ]}
      >
        <div style={{ marginBottom: 16 }}>检测到以下问题：</div>
        <ul style={{ paddingLeft: 20 }}>
          {getIssueDescriptions().map((desc, i) => (
            <li key={i} style={{ marginBottom: 8, color: '#ff4d4f' }}>{desc}</li>
          ))}
        </ul>
        <div style={{ marginTop: 16, color: '#888', fontSize: 13 }}>
          请检查设备网络连接和采集卡接线，然后点击"尝试重连"
        </div>
      </Modal>
    </Layout>
  )
}
