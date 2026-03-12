import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'AI Video Processor',
  description: 'Convert YouTube Links to Viral 9:16 Shorts',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen">
        {children}
      </body>
    </html>
  )
}
