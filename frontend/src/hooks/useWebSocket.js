import { useEffect, useRef, useState, useCallback } from 'react'

export function useWebSocket(cameraId) {
  const [frame, setFrame] = useState(null)       // { frame_b64, detections, fps, timestamp }
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const reconnectTimer = useRef(null)

  const connect = useCallback(() => {
    if (!cameraId) return
    const wsBase = window.location.hostname === 'localhost' ? `ws://${window.location.host}` : `wss://${window.location.host}`
    const ws = new WebSocket(`${wsBase}/ws/${cameraId}`)
    wsRef.current = ws

    ws.onopen = () => setConnected(true)

    ws.onmessage = (e) => {
      try {
        setFrame(JSON.parse(e.data))
      } catch { /* ignore malformed */ }
    }

    ws.onclose = () => {
      setConnected(false)
      // auto-reconnect after 3 seconds
      reconnectTimer.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => ws.close()
  }, [cameraId])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { frame, connected }
}
