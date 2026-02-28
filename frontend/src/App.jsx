import React from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu } from 'antd'
import {
  SettingOutlined, VideoCameraOutlined, ImportOutlined,
  PlayCircleOutlined, OrderedListOutlined, BarChartOutlined,
  BranchesOutlined
} from '@ant-design/icons'

import DeviceConfig from './pages/DeviceConfig'
import CaseManagement from './pages/CaseManagement'
import Recording from './pages/Recording'
import Replay from './pages/Replay'
import TestPlan from './pages/TestPlan'
import Statistics from './pages/Statistics'
import GitCollab from './pages/GitCollab'
import RemoteControl from './components/RemoteControl'

const { Sider, Content } = Layout

const menuItems = [
  { key: '/', icon: <SettingOutlined />, label: '设备配置' },
  { key: '/cases', icon: <ImportOutlined />, label: '用例管理' },
  { key: '/recording', icon: <VideoCameraOutlined />, label: '录制' },
  { key: '/replay', icon: <PlayCircleOutlined />, label: '回放' },
  { key: '/plans', icon: <OrderedListOutlined />, label: '测试计划' },
  { key: '/stats', icon: <BarChartOutlined />, label: '统计报表' },
  { key: '/git', icon: <BranchesOutlined />, label: 'Git 协作' },
]

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()

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
      </Sider>
      <Layout>
        <Content style={{ padding: 24, background: '#f5f5f5', overflow: 'auto' }}>
          <Routes>
            <Route path="/" element={<DeviceConfig />} />
            <Route path="/cases" element={<CaseManagement />} />
            <Route path="/recording" element={<Recording />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="/plans" element={<TestPlan />} />
            <Route path="/stats" element={<Statistics />} />
            <Route path="/git" element={<GitCollab />} />
          </Routes>
          {['/', '/recording', '/replay'].includes(location.pathname) && <RemoteControl />}
        </Content>
      </Layout>
    </Layout>
  )
}
