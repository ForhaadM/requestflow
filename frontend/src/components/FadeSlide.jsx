import { useEffect, useState } from 'react'

// Keeps children mounted for the exit transition instead of unmounting
// instantly, so `show` toggling true/false both animate over the same
// duration as the claim toggle switch (300ms).
export function FadeSlide({ show, children }) {
  const [mounted, setMounted] = useState(show)
  const [visible, setVisible] = useState(show)

  useEffect(() => {
    if (show) {
      setMounted(true)
      const id = requestAnimationFrame(() => setVisible(true))
      return () => cancelAnimationFrame(id)
    }
    setVisible(false)
    const timeout = setTimeout(() => setMounted(false), 300)
    return () => clearTimeout(timeout)
  }, [show])

  if (!mounted) return null

  return (
    <div
      className={`transition-all duration-300 ease-in-out ${
        visible ? 'translate-y-0 opacity-100' : '-translate-y-1 opacity-0'
      }`}
    >
      {children}
    </div>
  )
}
