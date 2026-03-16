import React, { useState, useEffect } from 'react'
import { Card, Form, Input, Select, Button, Space, Alert, Descriptions, message, Divider, Spin } from 'antd'
import { ReloadOutlined, CheckCircleOutlined, SearchOutlined } from '@ant-design/icons'
import { getConfig, updateConfig, getCaptureDevices, getInputDevices, checkDevice, getAdbDevices, getJiraConfig, saveJiraConfig } from '../api'

export default function DeviceConfig() {
  const [config, setConfig] = useState(null)
  const [captureDevices, setCaptureDevices] = useState([])
  const [inputDevices, setInputDevices] = useState([])
  const [deviceCheckResult, setDeviceCheckResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [checkLoading, setCheckLoading] = useState(false)
  const [adbDevices, setAdbDevices] = useState([])
  const [detectLoading, setDetectLoading] = useState(false)
  const [jiraForm] = Form.useForm()
  const [configForm] = Form.useForm()

  const fetchConfig = async () => {
    try {
      const res = await getConfig()
      const data = res.data?.data || res.data
      setConfig(data)
      configForm.setFieldsValue(data)
    } catch (e) {
      message.error('获取配置失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const fetchCaptureDevices = async () => {
    try {
      const res = await getCaptureDevices()
      const devices = res.data?.data || res.data?.devices || []
      setCaptureDevices(Array.isArray(devices) ? devices : [])
    } catch (e) {
      message.error('获取采集卡设备列表失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const fetchJiraConfig = async () => {
    try {
      const res = await getJiraConfig()
      const data = res.data?.data || res.data
      jiraForm.setFieldsValue(data)
    } catch (e) {
      // Jira 配置可能不存在，不报错
    }
  }

  const fetchInputDevices = async () => {
    try {
      const res = await getInputDevices()
      const devices = res.data?.data || []
      setInputDevices(Array.isArray(devices) ? devices : [])
    } catch (e) {
      // TV 未连接时静默失败
    }
  }

  useEffect(() => {
    fetchConfig()
    fetchCaptureDevices()
    fetchJiraConfig()
  }, [])

  const handleUpdateConfig = async (values) => {
    setLoading(true)
    try {
      await updateConfig(values)
      message.success('配置已更新')
      fetchConfig()
    } catch (e) {
      message.error('更新配置失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setLoading(false)
    }
  }

  const handleDeviceChange = async (deviceId) => {
    try {
      await updateConfig({ device_id: deviceId })
      message.success('采集卡设备已切换')
      fetchConfig()
    } catch (e) {
      message.error('切换采集卡失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleCheckDevice = async () => {
    setCheckLoading(true)
    setDeviceCheckResult(null)
    try {
      const res = await checkDevice()
      const data = res.data
      setDeviceCheckResult(data)
    } catch (e) {
      setDeviceCheckResult({ success: false, error: e.response?.data?.error || e.message })
    } finally {
      setCheckLoading(false)
    }
  }

  const handleDetectDevices = async () => {
    setDetectLoading(true)
    try {
      const res = await getAdbDevices()
      const devices = res.data?.data || []
      setAdbDevices(devices)
      if (devices.length === 0) {
        message.warning('未检测到已连接的 ADB 设备')
      } else {
        message.success(`检测到 ${devices.length} 个设备`)
      }
    } catch (e) {
      message.error('检测设备失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setDetectLoading(false)
    }
  }

  const handleSelectDevice = async (serial) => {
    try {
      await updateConfig({ tv_ip: serial })
      message.success('已选择设备 ' + serial)
      fetchConfig()
    } catch (e) {
      message.error('选择设备失败: ' + (e.response?.data?.error || e.message))
    }
  }

  const handleSaveJira = async (values) => {
    try {
      await saveJiraConfig(values)
      message.success('Jira 配置已保存')
    } catch (e) {
      message.error('保存 Jira 配置失败: ' + (e.response?.data?.error || e.message))
    }
  }

  return (
    <div>
      <h2>设备配置</h2>

      <Card title="采集卡设备选择" style={{ marginBottom: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <div>
            <span style={{ marginRight: 12, fontWeight: 'bold', fontSize: 15 }}>选择采集卡设备：</span>
            <Select
              style={{ width: 400 }}
              placeholder="请选择采集卡设备"
              value={config?.device_id}
              onChange={handleDeviceChange}
              options={captureDevices.map((d, i) => ({
                label: d.name || d.label || `设备 ${d.index ?? i}`,
                value: d.index ?? d.id ?? i,
              }))}
            />
            <Button icon={<ReloadOutlined />} onClick={fetchCaptureDevices} style={{ marginLeft: 8 }}>
              刷新设备列表
            </Button>
          </div>
        </Space>
      </Card>

      <Card title="TV 设备配置" style={{ marginBottom: 16 }}>
        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 12, fontWeight: 'bold' }}>自动检测设备：</span>
          <Button icon={<SearchOutlined />} onClick={handleDetectDevices} loading={detectLoading}>
            检测已连接设备
          </Button>
          {adbDevices.length > 0 && (
            <Select
              style={{ width: 360, marginLeft: 12 }}
              placeholder="选择已连接的设备"
              value={config?.tv_ip || undefined}
              onChange={handleSelectDevice}
              options={adbDevices.map(d => ({
                label: `${d.serial} (${d.type === 'usb' ? 'USB' : '网络'} - ${d.status === 'device' ? '已连接' : d.status})`,
                value: d.serial,
                disabled: d.status !== 'device',
              }))}
            />
          )}
          <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
            通过 USB 或网线连接设备后点击检测，可自动识别设备，无需手动输入 IP
          </div>
        </div>

        <Form form={configForm} layout="inline" onFinish={handleUpdateConfig}>
          <Form.Item label="设备地址" name="tv_ip">
            <Input placeholder="IP 地址（如 192.168.x.x:5555）或设备序列号" style={{ width: 320 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>保存配置</Button>
          </Form.Item>
        </Form>

        <Divider />

        <div style={{ marginBottom: 16 }}>
          <span style={{ marginRight: 12, fontWeight: 'bold' }}>遥控器输入设备：</span>
          <Select
            style={{ width: 400 }}
            placeholder="自动选择（优先 IR/remote 设备）"
            value={config?.key_event_device || undefined}
            allowClear
            onChange={async (val) => {
              try {
                await updateConfig({ key_event_device: val || '' })
                message.success('输入设备已更新')
                fetchConfig()
              } catch (e) {
                message.error('更新失败: ' + (e.response?.data?.error || e.message))
              }
            }}
            options={inputDevices.map(d => ({
              label: `${d.path} (${d.name})`,
              value: d.path,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={fetchInputDevices} style={{ marginLeft: 8 }}>
            获取设备列表
          </Button>
          <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>
            留空则自动选择（优先 IR Receiver 类设备，排除触屏/鼠标设备）
          </div>
        </div>

        <Space>
          <Button type="default" icon={<CheckCircleOutlined />} onClick={handleCheckDevice} loading={checkLoading}>
            检查设备连接
          </Button>
        </Space>

        {deviceCheckResult && (
          <Alert
            style={{ marginTop: 16 }}
            type={deviceCheckResult.success ? 'success' : 'error'}
            message={deviceCheckResult.success ? '设备连接正常' : '设备连接失败'}
            description={deviceCheckResult.error || deviceCheckResult.message || JSON.stringify(deviceCheckResult.data)}
            showIcon
          />
        )}
      </Card>

      <Card title="实时预览" style={{ marginBottom: 16 }}>
        <img
          src="/api/tv/stream"
          alt="TV 实时画面"
          style={{ maxWidth: '100%', maxHeight: 480, border: '1px solid #d9d9d9', borderRadius: 4, background: '#000' }}
        />
      </Card>

      <Card title="Jira 配置">
        <Form form={jiraForm} layout="vertical" onFinish={handleSaveJira} style={{ maxWidth: 500 }}>
          <Form.Item label="Jira Base URL" name="base_url">
            <Input placeholder="https://jira.example.com" />
          </Form.Item>
          <Form.Item label="Authorization" name="authorization">
            <Input.Password placeholder="Basic xxxxxxxx 或 Bearer token" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">保存 Jira 配置</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}
