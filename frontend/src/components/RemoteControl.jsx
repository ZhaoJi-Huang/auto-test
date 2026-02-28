import React, { useState, useCallback } from 'react'
import { message } from 'antd'
import { sendKey } from '../api'

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

  const Btn = ({ k, label, style: extra, className }) => {
    const isActive = sending === k
    return (
      <button
        className={`rc-btn ${className || ''} ${isActive ? 'rc-active' : ''}`}
        style={extra}
        onClick={() => handleKey(k)}
      >
        {label || k}
      </button>
    )
  }

  return (
    <div className="rc-panel">
      {/* 电源 + 信号源 */}
      <div className="rc-row">
        <Btn k="POWER" label="⏻" className="rc-power" />
        <Btn k="SOURCE" label="SOURCE" className="rc-func" style={{ flex: 1 }} />
      </div>

      {/* 方向键 */}
      <div className="rc-dpad">
        <button className="rc-dpad-arrow rc-dpad-up" onClick={() => handleKey('UP')}>
          <svg width="20" height="12" viewBox="0 0 20 12"><path d="M10 0L20 12H0z" fill="currentColor"/></svg>
        </button>
        <button className="rc-dpad-arrow rc-dpad-left" onClick={() => handleKey('LEFT')}>
          <svg width="12" height="20" viewBox="0 0 12 20"><path d="M0 10L12 0v20z" fill="currentColor"/></svg>
        </button>
        <button className="rc-dpad-ok" onClick={() => handleKey('ENTER')}>OK</button>
        <button className="rc-dpad-arrow rc-dpad-right" onClick={() => handleKey('RIGHT')}>
          <svg width="12" height="20" viewBox="0 0 12 20"><path d="M12 10L0 0v20z" fill="currentColor"/></svg>
        </button>
        <button className="rc-dpad-arrow rc-dpad-down" onClick={() => handleKey('DOWN')}>
          <svg width="20" height="12" viewBox="0 0 20 12"><path d="M10 12L0 0h20z" fill="currentColor"/></svg>
        </button>
      </div>

      {/* 功能键 */}
      <div className="rc-func-row">
        <Btn k="HOME" label="⌂" className="rc-func-icon" />
        <Btn k="BACK" label="↩" className="rc-func-icon" />
        <Btn k="MENU" label="☰" className="rc-func-icon" />
        <Btn k="SETTING" label="⚙" className="rc-func-icon" />
      </div>

      {/* 音量 / 静音 / 频道 */}
      <div className="rc-vol-ch">
        <div className="rc-rocker">
          <Btn k="VOLUME_UP" label="+" className="rc-rocker-btn" />
          <span className="rc-rocker-label">VOL</span>
          <Btn k="VOLUME_DOWN" label="−" className="rc-rocker-btn" />
        </div>
        <Btn k="MUTE" label="🔇" className="rc-mute" />
        <div className="rc-rocker">
          <Btn k="CHANNEL_UP" label="+" className="rc-rocker-btn" />
          <span className="rc-rocker-label">CH</span>
          <Btn k="CHANNEL_DOWN" label="−" className="rc-rocker-btn" />
        </div>
      </div>

      {/* 数字键盘 */}
      <div className="rc-numpad">
        {['1','2','3','4','5','6','7','8','9'].map(n => (
          <Btn key={n} k={n} label={n} className="rc-num" />
        ))}
        <div />
        <Btn k="0" label="0" className="rc-num" />
        <div />
      </div>

      {/* 媒体控制 */}
      <div className="rc-media">
        <Btn k="REWIND" label="⏪" className="rc-media-btn" />
        <Btn k="PLAY_PAUSE" label="⏯" className="rc-media-btn" />
        <Btn k="FAST_FORWARD" label="⏩" className="rc-media-btn" />
      </div>
    </div>
  )
}

export default function RemoteControl() {
  const [open, setOpen] = useState(false)

  return (
    <div style={{ position: 'fixed', right: 24, bottom: 24, zIndex: 1000 }}>
      {open && (
        <div style={{
          position: 'absolute', bottom: 56, right: 0,
          animation: 'rcFadeIn 0.25s ease-out',
        }}>
          <RemotePanel />
        </div>
      )}

      <button
        className="rc-fab"
        onClick={() => setOpen(v => !v)}
        data-open={open}
        title={open ? '收起遥控器' : '打开遥控器'}
      >
        {open ? '✕' : '📱'}
      </button>

      <style>{`
        @keyframes rcFadeIn {
          from { opacity: 0; transform: translateY(8px) scale(0.96); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }

        .rc-panel {
          width: 220px;
          background: linear-gradient(145deg, #1e1e2e, #2a2a3e);
          border-radius: 20px;
          padding: 16px 14px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          box-shadow: 0 12px 40px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.06);
          backdrop-filter: blur(20px);
        }

        .rc-btn {
          border: none;
          cursor: pointer;
          font-family: inherit;
          transition: all 0.15s ease;
          user-select: none;
          outline: none;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .rc-btn:hover { filter: brightness(1.2); }
        .rc-btn.rc-active { opacity: 0.5; transform: scale(0.92) !important; }

        /* 电源 + 信号源 */
        .rc-row {
          display: flex;
          gap: 8px;
        }
        .rc-power {
          width: 42px;
          height: 34px;
          border-radius: 10px;
          background: linear-gradient(135deg, #ef4444, #dc2626);
          color: #fff;
          font-size: 18px;
          box-shadow: 0 2px 8px rgba(239,68,68,0.3);
        }
        .rc-power:hover { box-shadow: 0 4px 16px rgba(239,68,68,0.5); }
        .rc-func {
          height: 34px;
          border-radius: 10px;
          background: rgba(255,255,255,0.07);
          color: rgba(255,255,255,0.7);
          font-size: 11px;
          font-weight: 500;
          letter-spacing: 0.5px;
        }
        .rc-func:hover { background: rgba(255,255,255,0.12); }

        /* 方向键 */
        .rc-dpad {
          position: relative;
          width: 152px;
          height: 152px;
          margin: 4px auto;
          border-radius: 50%;
          background: radial-gradient(circle at center, transparent 30px, rgba(255,255,255,0.04) 31px, rgba(255,255,255,0.04) 100%);
          border: 1px solid rgba(255,255,255,0.06);
        }
        .rc-dpad-arrow {
          position: absolute;
          border: none;
          background: transparent;
          color: rgba(255,255,255,0.45);
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
          outline: none;
          border-radius: 8px;
          padding: 8px;
        }
        .rc-dpad-arrow:hover { color: rgba(255,255,255,0.8); background: rgba(255,255,255,0.08); }
        .rc-dpad-arrow:active { color: #fff; background: rgba(255,255,255,0.12); }
        .rc-dpad-up { top: 6px; left: 50%; transform: translateX(-50%); width: 52px; height: 40px; }
        .rc-dpad-down { bottom: 6px; left: 50%; transform: translateX(-50%); width: 52px; height: 40px; }
        .rc-dpad-left { left: 6px; top: 50%; transform: translateY(-50%); width: 40px; height: 52px; }
        .rc-dpad-right { right: 6px; top: 50%; transform: translateY(-50%); width: 40px; height: 52px; }
        .rc-dpad-ok {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          width: 50px;
          height: 50px;
          border-radius: 50%;
          border: none;
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: #fff;
          font-size: 12px;
          font-weight: 700;
          letter-spacing: 1px;
          cursor: pointer;
          transition: all 0.15s;
          outline: none;
          box-shadow: 0 2px 12px rgba(99,102,241,0.35);
        }
        .rc-dpad-ok:hover { box-shadow: 0 4px 20px rgba(99,102,241,0.5); transform: translate(-50%, -50%) scale(1.05); }
        .rc-dpad-ok:active { transform: translate(-50%, -50%) scale(0.95); }

        /* 功能键行 */
        .rc-func-row {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 6px;
        }
        .rc-func-icon {
          height: 36px;
          border-radius: 10px;
          background: rgba(255,255,255,0.05);
          color: rgba(255,255,255,0.55);
          font-size: 16px;
        }
        .rc-func-icon:hover { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.85); }

        /* 音量 / 频道 */
        .rc-vol-ch {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
        }
        .rc-rocker {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          flex: 1;
        }
        .rc-rocker-btn {
          width: 100%;
          height: 28px;
          border-radius: 8px;
          background: rgba(255,255,255,0.06);
          color: rgba(255,255,255,0.6);
          font-size: 16px;
          font-weight: 300;
        }
        .rc-rocker-btn:hover { background: rgba(255,255,255,0.12); }
        .rc-rocker-label {
          font-size: 9px;
          color: rgba(255,255,255,0.3);
          text-transform: uppercase;
          letter-spacing: 1px;
          padding: 1px 0;
        }
        .rc-mute {
          width: 38px;
          height: 38px;
          border-radius: 50%;
          background: rgba(255,255,255,0.05);
          color: rgba(255,255,255,0.4);
          font-size: 14px;
          flex-shrink: 0;
        }
        .rc-mute:hover { background: rgba(255,255,255,0.1); }

        /* 数字键盘 */
        .rc-numpad {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 4px;
          justify-items: center;
        }
        .rc-num {
          width: 48px;
          height: 36px;
          border-radius: 10px;
          background: rgba(255,255,255,0.04);
          color: rgba(255,255,255,0.65);
          font-size: 15px;
          font-weight: 500;
        }
        .rc-num:hover { background: rgba(255,255,255,0.1); color: #fff; }

        /* 媒体控制 */
        .rc-media {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 6px;
        }
        .rc-media-btn {
          height: 34px;
          border-radius: 10px;
          background: rgba(255,255,255,0.04);
          color: rgba(255,255,255,0.45);
          font-size: 16px;
        }
        .rc-media-btn:hover { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.8); }

        /* 悬浮按钮 */
        .rc-fab {
          width: 48px;
          height: 48px;
          border-radius: 50%;
          border: none;
          cursor: pointer;
          font-size: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
          outline: none;
          background: linear-gradient(135deg, #6366f1, #4f46e5);
          color: #fff;
          box-shadow: 0 4px 20px rgba(99,102,241,0.4);
        }
        .rc-fab:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(99,102,241,0.5); }
        .rc-fab[data-open="true"] {
          background: linear-gradient(135deg, #ef4444, #dc2626);
          box-shadow: 0 4px 20px rgba(239,68,68,0.4);
        }
        .rc-fab[data-open="true"]:hover { box-shadow: 0 6px 28px rgba(239,68,68,0.5); }
      `}</style>
    </div>
  )
}
