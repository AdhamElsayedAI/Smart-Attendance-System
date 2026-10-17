import { useCallback, useEffect, useState } from 'react'
import { api, type Session } from '../services/api'

export function useLiveSession() {
  const [session, setSession] = useState<Session | null>(null)
  const [error, setError] = useState<string | null>(null)
  const refresh = useCallback(async () => {
    try { setSession(await api.status()); setError(null) }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Connection lost') }
  }, [])

  useEffect(() => {
    let active = true
    let timer: number
    const poll = async () => {
      if (!active) return
      try {
        const next = await api.status()
        if (active) { setSession(next); setError(null) }
      } catch (cause) {
        if (active) setError(cause instanceof Error ? cause.message : 'Connection lost')
      } finally {
        if (active) timer = window.setTimeout(poll, 650)
      }
    }
    void poll()
    return () => { active = false; window.clearTimeout(timer) }
  }, [])
  return { session, error, refresh }
}

export function useCameraFrame(enabled: boolean) {
  const [frame, setFrame] = useState<string | null>(null)
  useEffect(() => {
    if (!enabled) { setFrame(null); return }
    let active = true
    let timer: number
    let currentUrl: string | null = null
    const poll = async () => {
      if (!active) return
      try {
        const response = await fetch('/api/session/frame', { cache: 'no-store' })
        if (response.ok) {
          const url = URL.createObjectURL(await response.blob())
          if (active) { setFrame(url); if (currentUrl) URL.revokeObjectURL(currentUrl); currentUrl = url }
          else URL.revokeObjectURL(url)
        }
      } catch { /* status poll reports camera failure */ }
      if (active) timer = window.setTimeout(poll, 230)
    }
    void poll()
    return () => { active = false; window.clearTimeout(timer); if (currentUrl) URL.revokeObjectURL(currentUrl) }
  }, [enabled])
  return frame
}
