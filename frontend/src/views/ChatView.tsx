import { Fragment, useEffect, useRef, useState } from 'react'
import { api, type Citation } from '../api'

interface Message {
  role: 'user' | 'assistant'
  text: string
  citations?: Citation[]
  latencyMs?: number
  isError?: boolean
}

const SUGGESTIONS = [
  'Who has the most Python experience?',
  'Which candidates would fit a senior DevOps role?',
  'Tell me about Fatima Al-Sayed',
]

/** Render answer text, turning [n] markers into buttons that highlight their source. */
function AnswerText({
  text,
  citations,
  onCite,
}: {
  text: string
  citations: Citation[]
  onCite: (n: number) => void
}) {
  const known = new Set(citations.map((c) => c.n))
  const cleaned = text.replace(/^\s*[*-]\s+/gm, '•  ').replace(/^#+\s+/gm, '')
  const parts = cleaned.split(/(\[\d+\])/g)
  return (
    <>
      {parts.map((part, i) => {
        const match = /^\[(\d+)\]$/.exec(part)
        if (match && known.has(Number(match[1]))) {
          const n = Number(match[1])
          return (
            <button
              key={i}
              type="button"
              className="cite"
              onClick={() => onCite(n)}
              aria-label={`Show source ${n}`}
            >
              {n}
            </button>
          )
        }
        // Preserve the model's line breaks and simple **bold** / bullet formatting.
        return (
          <Fragment key={i}>
            {part.split(/(\*\*[^*]+\*\*)/g).map((seg, j) => {
              const bold = /^\*\*([^*]+)\*\*$/.exec(seg)
              return bold ? <strong key={j}>{bold[1]}</strong> : <Fragment key={j}>{seg}</Fragment>
            })}
          </Fragment>
        )
      })}
    </>
  )
}

function Sources({ citations, activeN }: { citations: Citation[]; activeN: number | null }) {
  const [open, setOpen] = useState(false)
  const shown = open ? citations : citations.filter((c) => c.n === activeN)
  return (
    <div className="sources">
      <button type="button" className="sources-toggle" onClick={() => setOpen(!open)}>
        {open ? 'Hide sources' : `Sources (${citations.length})`}
      </button>
      {shown.map((c) => (
        <div key={c.n} className={`source-card${c.n === activeN ? ' is-active' : ''}`} id={`src-${c.n}`}>
          <div className="source-head">
            <span className="source-ref">[{c.n}]</span>
            <span className="source-who">{c.candidate_name}</span>
            <span className="source-where">
              {c.section ?? 'CV'} · {c.filename}
              {c.page ? ` · p.${c.page}` : ''}
            </span>
          </div>
          <p className="source-snippet">{c.snippet}</p>
        </div>
      ))}
    </div>
  )
}

export default function ChatView({ hasCandidates }: { hasCandidates: boolean }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [activeCite, setActiveCite] = useState<{ msg: number; n: number } | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, sending])

  async function send(text: string) {
    const message = text.trim()
    if (!message || sending) return
    setInput('')
    setActiveCite(null)
    setMessages((m) => [...m, { role: 'user', text: message }])
    setSending(true)
    try {
      const r = await api.chat(message, sessionId)
      setSessionId(r.session_id)
      setMessages((m) => [
        ...m,
        { role: 'assistant', text: r.answer, citations: r.citations, latencyMs: r.latency_ms },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: 'assistant',
          text: `Couldn't get an answer: ${err instanceof Error ? err.message : err}. Try again.`,
          isError: true,
        },
      ])
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 ? (
          <div className="chat-empty">
            <h1>Ask about your candidates</h1>
            <p>
              {hasCandidates
                ? 'Answers come straight from the uploaded CVs, with numbered references you can check.'
                : 'No CVs indexed yet — upload a few first, then ask away.'}
            </p>
            {hasCandidates && (
              <div className="suggestions">
                {SUGGESTIONS.map((s) => (
                  <button key={s} type="button" className="suggestion" onClick={() => send(s)}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="thread">
            {messages.map((msg, i) =>
              msg.role === 'user' ? (
                <div key={i} className="msg msg-user">
                  {msg.text}
                </div>
              ) : (
                <div key={i} className={`msg msg-assistant${msg.isError ? ' is-error' : ''}`}>
                  <div className="msg-body">
                    {msg.citations ? (
                      <AnswerText
                        text={msg.text}
                        citations={msg.citations}
                        onCite={(n) =>
                          setActiveCite((prev) =>
                            prev?.msg === i && prev.n === n ? null : { msg: i, n },
                          )
                        }
                      />
                    ) : (
                      msg.text
                    )}
                  </div>
                  {msg.citations && msg.citations.length > 0 && (
                    <Sources citations={msg.citations} activeN={activeCite?.msg === i ? activeCite.n : null} />
                  )}
                  {msg.latencyMs !== undefined && (
                    <div className="msg-meta">{(msg.latencyMs / 1000).toFixed(1)}s</div>
                  )}
                </div>
              ),
            )}
            {sending && (
              <div className="msg msg-assistant">
                <span className="thinking" aria-label="Waiting for answer">
                  <i />
                  <i />
                  <i />
                </span>
              </div>
            )}
          </div>
        )}
      </div>

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={hasCandidates ? 'Ask about the candidates…' : 'Upload CVs first, then ask…'}
          aria-label="Your question"
          disabled={sending}
        />
        <button type="submit" disabled={sending || !input.trim()}>
          {sending ? 'Thinking…' : 'Ask'}
        </button>
      </form>
    </div>
  )
}
