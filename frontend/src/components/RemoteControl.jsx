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

function RemotePanel() {
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

  const DPad = () => {
    const outer = 150
    const center = 48
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
            ...btnBase, position: 'absolute', ...positions[pos],
            width: pos === 'top' || pos === 'bottom' ? 48 : 42,
            height: pos === 'top' || pos === 'bottom' ? 42 : 48,
            background: 'transparent', color: RC.text, fontSize: 18, borderRadius: 8,
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
            ...btnBase, position: 'absolute',
            top: '50%', left: '50%', transform: 'translate(-50%, -50%)',
            width: center, height: center,
            borderRadius: '50%', background: RC.dpadCenter,
            color: '#fff', fontSize: 11, fontWeight: 700,
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

  const Sep = () => <div style={{ height: 1, background: 'rgba(255,255,255,0.06)', margin: '8px 0' }} />

  return (
    <div style={{
      width: 210, background: RC.bg, borderRadius: 14,
      padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {/* 电源 + SOURCE */}
      <div style={{ display: 'flex', gap: 6 }}>
        <button
          style={{ ...funcBtn, background: RC.highlight, flex: 1 }}
          onClick={() => handleKey('POWER')}
          onMouseDown={e => { e.currentTarget.style.opacity = '0.7' }}
          onMouseUp={e => { e.currentTarget.style.opacity = '1' }}
          onMouseLeave={e => { e.currentTarget.style.opacity = '1' }}
        >POWER</button>
        <KeyBtn k="SOURCE" label="SOURCE" btnStyle={{ ...funcBtn, flex: 1 }} />
      </div>

      <Sep />
      <DPad />

      {/* 功能键 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 5 }}>
        <KeyBtn k="HOME" label="HOME" btnStyle={funcBtn} />
        <KeyBtn k="MENU" label="MENU" btnStyle={funcBtn} />
        <KeyBtn k="BACK" label="BACK" btnStyle={funcBtn} />
        <KeyBtn k="SETTING" label="SET" btnStyle={funcBtn} />
      </div>

      <Sep />

      {/* 音量 / 静音 / 频道 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 5, alignItems: 'center' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <KeyBtn k="VOLUME_UP" label="VOL+" btnStyle={smallBtn} />
          <KeyBtn k="VOLUME_DOWN" label="VOL-" btnStyle={smallBtn} />
        </div>
        <KeyBtn k="MUTE" label="MUTE" btnStyle={{
          ...btnBase, background: RC.bgLight, color: RC.textDim,
          borderRadius: '50%', width: 40, height: 40, fontSize: 10, margin: '0 auto',
        }} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          <KeyBtn k="CHANNEL_UP" label="CH+" btnStyle={smallBtn} />
          <KeyBtn k="CHANNEL_DOWN" label="CH-" btnStyle={smallBtn} />
        </div>
      </div>

      <Sep />

      {/* 数字键盘 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 3, justifyItems: 'center' }}>
        {['1','2','3','4','5','6','7','8','9'].map(n => (
          <KeyBtn key={n} k={n} label={n} btnStyle={numBtn} />
        ))}
        <div />
        <KeyBtn k="0" label="0" btnStyle={numBtn} />
        <div />
      </div>

      <Sep />

      {/* 媒体控制 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 5 }}>
        <KeyBtn k="REWIND" label="&#x23EA;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
        <KeyBtn k="PLAY_PAUSE" label="&#x23EF;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
        <KeyBtn k="FAST_FORWARD" label="&#x23E9;" btnStyle={{ ...funcBtn, fontSize: 16 }} />
      </div>
    </div>
  )
}

/**
 * 悬浮遥控器：右下角悬浮按钮，点击展开遥控器面板
 */
export default function RemoteControl() {
  const [open, setOpen] = useState(false)

  return (
    <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1000 }}>
      {/* 遥控器面板 */}
      {open && (
        <div style={{
          position: 'absolute', bottom: 60, right: 0,
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
          borderRadius: 14,
          animation: 'fadeInUp 0.2s ease-out',
        }}>
          <RemotePanel />
        </div>
      )}

      {/* 悬浮按钮 */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: 48, height: 48, borderRadius: '50%',
          background: open ? RC.highlight : '#1a1a2e',
          color: '#fff', border: '2px solid rgba(255,255,255,0.15)',
          cursor: 'pointer', fontSize: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          transition: 'all 0.2s',
        }}
        title={open ? '收起遥控器' : '打开遥控器'}
      >
        {open ? '\u2716' : '\uD83D\uDCF1'}
      </button>

      <style>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
