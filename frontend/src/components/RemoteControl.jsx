import React, { useState, useCallback } from 'react'
import { message } from 'antd'
import { sendKey } from '../api'

const RC = {
  bg: '#1a1a2e',
  bgLight: '#16213e',
  accent: '#0f3460',
  text: '#e0e0e0',
  textDim: '#888',
  highlight: '#e94560',
  dpadBg: '#222244',
  dpadCenter: '#e94560',
  radius: 16,
}

const btnBase = {
  border: 'none',
  cursor: 'pointer',
  fontFamily: 'inherit',
  transition: 'all 0.1s',
  userSelect: 'none',
  outline: 'none',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
}

const smallBtn = {
  ...btnBase,
  background: RC.accent,
  color: RC.text,
  borderRadius: 6,
  padding: '6px 0',
  fontSize: 11,
  fontWeight: 500,
  minWidth: 0,
  width: '100%',
}

const numBtn = {
  ...btnBase,
  background: RC.bgLight,
  color: RC.text,
  borderRadius: 8,
  width: 48,
  height: 40,
  fontSize: 16,
  fontWeight: 600,
}

const funcBtn = {
  ...btnBase,
  background: RC.accent,
  color: RC.text,
  borderRadius: 8,
  padding: '8px 0',
  fontSize: 11,
  fontWeight: 500,
  width: '100%',
}

export default function RemoteControl({ style }) {
  const [sending, setSending] = useState(null)

  const handleKey = useCallback(async (key) => {
    if (sending) return
    setSending(key)
    try {
      await sendKey(key)
    } catch (e) {
      message.error('发送失败: ' + (e.response?.data?.error || e.message))
    } finally {
      setTimeout(() => setSending(null), 100)
    }
  }, [sending])

  const KeyBtn = ({ k, label, btnStyle, size }) => {
    const isActive = sending === k
    const s = {
      ...(btnStyle || smallBtn),
      ...(size ? { width: size, height: size } : {}),
      opacity: isActive ? 0.6 : 1,
      transform: isActive ? 'scale(0.95)' : 'scale(1)',
    }
    return (
      <button style={s} onClick={() => handleKey(k)}
        onMouseDown={e => e.currentTarget.style.transform = 'scale(0.92)'}
        onMouseUp={e => e.currentTarget.style.transform = 'scale(1)'}
        onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
      >
        {label || k}
      </button>
    )
  }

  // 方向键（十字布局）
  const DPad = () => {
    const outer = 160
    const center = 52
    const arrowBtn = (key, label, pos) => {
      const positions = {
        top: { top: 4, left: '50%', transform: 'translateX(-50%)' },
        bottom: { bottom: 4, left: '50%', transform: 'translateX(-50%)' },
        left: { left: 4, top: '50%', transform: 'translateY(-50%)' },
        right: { right: 4, top: '50%', transform: 'translateY(-50%)' },
      }
      return (
        <button
          style={{
            ...btnBase,
            position: 'absolute',
            ...positions[pos],
            width: pos === 'top' || pos === 'bottom' ? 52 : 44,
            height: pos === 'top' || pos === 'bottom' ? 44 : 52,
            background: 'transparent',
            color: RC.text,
            fontSize: 20,
            borderRadius: 8,
          }}
          onClick={() => handleKey(key)}
          onMouseDown={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)' }}
          onMouseUp={e => { e.currentTarget.style.background = 'transparent' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent' }}
        >
          {label}
        </button>
      )
    }
    return (
      <div style={{
        position: 'relative', width: outer, height: outer, margin: '0 auto',
        borderRadius: '50%', background: RC.dpadBg,
      }}>
        {arrowBtn('UP', '\u25B2', 'top')}
        {arrowBtn('DOWN', '\u25BC', 'bottom')}
        {arrowBtn('LEFT', '\u25C0', 'left')}
        {arrowBtn('RIGHT', '\u25B6', 'right')}
        <button
          style={{
            ...btnBase,
            position: 'absolute',
            top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            width: center, height: center,
            borderRadius: '50%', background: RC.dpadCenter,
            color: '#fff', fontSize: 12, fontWeight: 700,
          }}
          onClick={() => handleKey('ENTER')}
          onMouseDown={e => { e.currentTarget.style.opacity = '0.7' }}
          onMouseUp={e => { e.currentTarget.style.opacity = '1' }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
        >
          OK
        </button>
      </div>
    )
  }

  const Separator = () => <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '10px 0' }} />

  return (
    <div style={{
      width: 220,
      background: RC.bg,
      borderRadius: RC.radius,
      padding: '16px 14px',
      display: 'flex',
      flexDirection: 'column',
      gap: 10,
      boxShadow: '0 4px 24px rgba(0,0,0,0.3)',
      flexShrink: 0,
      ...style,
    }}>
      {/* 电源 + SOURCE */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
        <button
          style={{ ...funcBtn, background: RC.highlight, flex: 1 }}
          onClick={() => handleKey('POWER')}
          onMouseDown={e => { e.currentTarget.style.opacity = '0.7' }}
          onMouseUp={e => { e.currentTarget.style.opacity = '1' }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
        >
          POWER
        </button>
        <KeyBtn k="SOURCE" label="SOURCE" btnStyle={{ ...funcBtn, flex: 1 }} />
      </div>

      <Separator />

      {/* 方向键 */}
      <DPad />

      {/* 功能键 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6 }}>
        <KeyBtn k="HOME" label="HOME" btnStyle={funcBtn} />
        <KeyBtn k="MENU" label="MENU" btnStyle={funcBtn} />
        <KeyBtn k="BACK" label="BACK" btnStyle={funcBtn} />
        <KeyBtn k="SETTING" label="SET" btnStyle={funcBtn} />
      </div>

      <Separator />

      {/* 音量 / 静音 / 频道 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <KeyBtn k="VOLUME_UP" label="VOL+" btnStyle={smallBtn} />
          <KeyBtn k="VOLUME_DOWN" label="VOL-" btnStyle={smallBtn} />
        </div>
        <KeyBtn k="MUTE" label="MUTE" btnStyle={{
          ...btnBase, background: RC.bgLight, color: RC.textDim,
          borderRadius: '50%', width: 44, height: 44, fontSize: 10,
          margin: '0 auto',
        }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <KeyBtn k="CHANNEL_UP" label="CH+" btnStyle={smallBtn} />
          <KeyBtn k="CHANNEL_DOWN" label="CH-" btnStyle={smallBtn} />
        </div>
      </div>

      <Separator />

      {/* 数字键盘 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 4, justifyItems: 'center' }}>
        {['1','2','3','4','5','6','7','8','9'].map(n => (
          <KeyBtn key={n} k={n} label={n} btnStyle={numBtn} />
        ))}
        <div />
        <KeyBtn k="0" label="0" btnStyle={numBtn} />
        <div />
      </div>

      <Separator />

      {/* 媒体控制 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
        <KeyBtn k="REWIND" label="&#x23EA;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
        <KeyBtn k="PLAY_PAUSE" label="&#x23EF;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
        <KeyBtn k="FAST_FORWARD" label="&#x23E9;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
      </div>
    </div>
  )
}
