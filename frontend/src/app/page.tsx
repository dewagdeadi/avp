'use client'

import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

export default function Home() {
  const [url, setUrl] = useState('')
  const [jobId, setJobId] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [progress, setProgress] = useState<number>(0)
  const [videoUrl, setVideoUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!url || isSubmitting) return
    
    setIsSubmitting(true)
    setError(null)
    setStatus('Starting...')
    setProgress(5)
    
    try {
      const res = await fetch(`${API}/api/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ youtube_url: url })
      })
      
      const data = await res.json()
      if (data.job_id) {
        setJobId(data.job_id)
      } else {
        setError('Failed to start processing.')
        setIsSubmitting(false)
      }
    } catch {
      setError('Could not connect to the backend. Make sure the backend is running on port 8000.')
      setIsSubmitting(false)
    }
  }

  // Poll for status
  useEffect(() => {
    if (!jobId || status === 'completed' || status === 'failed') return

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/status/${jobId}`)
        const data = await res.json()
        
        setStatus(data.status)
        setProgress(data.progress)
        
        if (data.status === 'completed') {
          setVideoUrl(`${API}${data.url}`)
          setIsSubmitting(false)
          clearInterval(interval)
        } else if (data.status === 'failed') {
          setError(data.error || 'Processing failed')
          setIsSubmitting(false)
          clearInterval(interval)
        }
      } catch {
        // Silently retry
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [jobId, status])

  const reset = () => {
    setJobId(null)
    setVideoUrl(null)
    setUrl('')
    setStatus(null)
    setProgress(0)
    setError(null)
    setIsSubmitting(false)
  }

  const statusLabels: Record<string, string> = {
    'queued': '⏳ Queued...',
    'downloading': '📥 Downloading video...',
    'analyzing_audio': '🎵 Finding the best moments...',
    'tracking_faces': '👤 Tracking faces & cropping 9:16...',
    'generating_captions': '💬 Generating subtitles with AI...',
    'rendering_final': '🎬 Rendering final video...',
    'generating_thumbnail': '🖼️ Creating thumbnail...',
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0a0a0a 0%, #1a0a2e 30%, #16213e 60%, #0a0a0a 100%)',
      color: '#fff',
      fontFamily: "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif",
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Animated background orbs */}
      <div style={{
        position: 'absolute', top: '10%', left: '20%',
        width: '400px', height: '400px',
        background: 'radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)',
        borderRadius: '50%',
        filter: 'blur(60px)',
        animation: 'pulse 4s ease-in-out infinite alternate',
      }}/>
      <div style={{
        position: 'absolute', bottom: '10%', right: '15%',
        width: '500px', height: '500px',
        background: 'radial-gradient(circle, rgba(236,72,153,0.12) 0%, transparent 70%)',
        borderRadius: '50%',
        filter: 'blur(80px)',
        animation: 'pulse 5s ease-in-out infinite alternate-reverse',
      }}/>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
        @keyframes pulse { from { opacity: 0.5; transform: scale(1); } to { opacity: 1; transform: scale(1.1); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes progressPulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
      `}</style>

      <div style={{ position: 'relative', zIndex: 10, maxWidth: '800px', width: '100%', textAlign: 'center' }}>
        
        {/* Logo / Title */}
        {!videoUrl && (
          <div style={{ animation: 'fadeIn 0.6s ease-out' }}>
            <h1 style={{
              fontSize: 'clamp(2.5rem, 6vw, 4rem)',
              fontWeight: 900,
              lineHeight: 1.1,
              marginBottom: '1rem',
              background: 'linear-gradient(135deg, #fff 0%, #c084fc 50%, #ec4899 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.03em',
            }}>
              Viral Shorts<br />in Seconds
            </h1>
            <p style={{
              fontSize: '1.1rem',
              color: 'rgba(255,255,255,0.55)',
              maxWidth: '600px',
              margin: '0 auto 2.5rem',
              lineHeight: 1.6,
            }}>
              Paste a YouTube link. Our AI finds the best hooks, crops to 9:16, tracks faces, and adds dynamic captions — automatically.
            </p>
          </div>
        )}

        {/* Input Form */}
        {!jobId && !videoUrl && (
          <form onSubmit={handleSubmit} style={{ animation: 'fadeIn 0.8s ease-out' }}>
            <div style={{
              display: 'flex',
              gap: '0.75rem',
              flexDirection: 'column',
            }}>
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://www.youtube.com/watch?v=..."
                style={{
                  padding: '1rem 1.5rem',
                  borderRadius: '16px',
                  border: '1px solid rgba(255,255,255,0.1)',
                  background: 'rgba(255,255,255,0.05)',
                  backdropFilter: 'blur(20px)',
                  color: '#fff',
                  fontSize: '1rem',
                  outline: 'none',
                  transition: 'all 0.3s',
                  boxShadow: '0 4px 30px rgba(0,0,0,0.3)',
                }}
                onFocus={(e) => {
                  e.target.style.borderColor = 'rgba(139,92,246,0.5)'
                  e.target.style.boxShadow = '0 0 30px rgba(139,92,246,0.15)'
                }}
                onBlur={(e) => {
                  e.target.style.borderColor = 'rgba(255,255,255,0.1)'
                  e.target.style.boxShadow = '0 4px 30px rgba(0,0,0,0.3)'
                }}
              />
              <button
                type="submit"
                disabled={isSubmitting || !url}
                style={{
                  padding: '1rem 2rem',
                  borderRadius: '16px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)',
                  color: '#fff',
                  fontSize: '1.05rem',
                  fontWeight: 700,
                  cursor: isSubmitting || !url ? 'not-allowed' : 'pointer',
                  opacity: isSubmitting || !url ? 0.5 : 1,
                  transition: 'all 0.3s',
                  boxShadow: '0 8px 30px rgba(139,92,246,0.3)',
                  letterSpacing: '0.02em',
                }}
              >
                {isSubmitting ? '⏳ Processing...' : '✨ Generate Magic'}
              </button>
            </div>
          </form>
        )}

        {/* Progress Section */}
        {jobId && status !== 'completed' && status !== 'failed' && (
          <div style={{
            animation: 'fadeIn 0.5s ease-out',
            background: 'rgba(255,255,255,0.03)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '24px',
            padding: '2.5rem',
            backdropFilter: 'blur(20px)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
            marginTop: '1rem',
          }}>
            <div style={{
              fontSize: '0.85rem',
              fontWeight: 600,
              color: 'rgba(255,255,255,0.4)',
              textTransform: 'uppercase',
              letterSpacing: '0.15em',
              marginBottom: '1.5rem',
            }}>
              AI is working...
            </div>

            <div style={{
              fontSize: '1.2rem',
              fontWeight: 600,
              color: '#c084fc',
              marginBottom: '1.5rem',
              animation: 'progressPulse 2s ease-in-out infinite',
            }}>
              {statusLabels[status || ''] || status?.replace(/_/g, ' ') || 'Starting...'}
            </div>

            {/* Progress bar */}
            <div style={{
              height: '8px',
              background: 'rgba(255,255,255,0.06)',
              borderRadius: '999px',
              overflow: 'hidden',
              marginBottom: '1rem',
            }}>
              <div style={{
                height: '100%',
                width: `${progress}%`,
                background: 'linear-gradient(90deg, #8b5cf6, #ec4899, #f59e0b)',
                backgroundSize: '200% 100%',
                animation: 'shimmer 2s linear infinite',
                borderRadius: '999px',
                transition: 'width 0.5s ease-out',
              }}/>
            </div>

            <div style={{
              fontSize: '0.9rem',
              color: 'rgba(255,255,255,0.3)',
              fontWeight: 600,
            }}>
              {progress}%
            </div>

            {/* Step indicators */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(4, 1fr)',
              gap: '0.5rem',
              marginTop: '1.5rem',
            }}>
              {[
                { label: 'Download', threshold: 10 },
                { label: 'Find Peaks', threshold: 30 },
                { label: 'Face Track', threshold: 50 },
                { label: 'Captions', threshold: 70 },
              ].map((step) => (
                <div key={step.label} style={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  color: progress >= step.threshold ? '#c084fc' : 'rgba(255,255,255,0.2)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  transition: 'color 0.3s',
                }}>
                  {progress >= step.threshold ? '✓ ' : ''}{step.label}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.1)',
            border: '1px solid rgba(239,68,68,0.3)',
            borderRadius: '16px',
            padding: '1.25rem',
            marginTop: '1.5rem',
            color: '#fca5a5',
            fontSize: '0.95rem',
            animation: 'fadeIn 0.3s ease-out',
          }}>
            {error}
            <button onClick={reset} style={{
              marginLeft: '1rem',
              color: '#fff',
              textDecoration: 'underline',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '0.95rem',
            }}>Try Again</button>
          </div>
        )}

        {/* Completed - Video Player */}
        {videoUrl && (
          <div style={{
            animation: 'fadeIn 0.6s ease-out',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '2rem',
            marginTop: '1rem',
          }}>
            <h2 style={{
              fontSize: '2rem',
              fontWeight: 800,
              background: 'linear-gradient(135deg, #fff 0%, #f59e0b 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              Your viral short is ready! 🔥
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.5)', marginTop: '-1rem' }}>
              AI found the best moment, cropped to 9:16, and added captions.
            </p>

            {/* Phone frame video player */}
            <div style={{
              position: 'relative',
              borderRadius: '40px',
              border: '6px solid #1a1a2e',
              overflow: 'hidden',
              maxWidth: '300px',
              aspectRatio: '9/16',
              boxShadow: '0 30px 80px rgba(139,92,246,0.2), 0 0 0 1px rgba(255,255,255,0.05)',
              background: '#000',
            }}>
              <video
                src={videoUrl}
                controls
                loop
                autoPlay
                style={{ width: '100%', height: '100%', objectFit: 'cover' }}
              />
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', justifyContent: 'center' }}>
              <a
                href={videoUrl}
                download
                style={{
                  padding: '0.9rem 2rem',
                  borderRadius: '14px',
                  background: '#fff',
                  color: '#000',
                  fontWeight: 700,
                  textDecoration: 'none',
                  fontSize: '0.95rem',
                  boxShadow: '0 4px 20px rgba(255,255,255,0.1)',
                  transition: 'transform 0.2s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                ⬇️ Download Video
              </a>
              <button onClick={reset} style={{
                padding: '0.9rem 2rem',
                borderRadius: '14px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                color: '#fff',
                fontWeight: 600,
                cursor: 'pointer',
                fontSize: '0.95rem',
              }}>
                ✨ Create Another
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
