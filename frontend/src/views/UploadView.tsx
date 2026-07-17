import { useRef, useState } from 'react'
import { api, type UploadResult } from '../api'

interface QueueItem {
  file: File
  status: 'queued' | 'uploading' | 'ok' | 'error'
  result?: UploadResult
}

const ACCEPTED = ['.pdf', '.docx']

export default function UploadView({ onIngested }: { onIngested: () => void }) {
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [busy, setBusy] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function addFiles(files: FileList | File[]) {
    const fresh = [...files]
      .filter((f) => ACCEPTED.some((ext) => f.name.toLowerCase().endsWith(ext)))
      .map<QueueItem>((file) => ({ file, status: 'queued' }))
    if (fresh.length) setQueue((q) => [...q, ...fresh])
  }

  async function uploadAll() {
    setBusy(true)
    // Sequential on purpose: one Gemini extraction per file keeps free-tier
    // rate limits happy and gives per-file progress.
    for (let i = 0; i < queue.length; i++) {
      if (queue[i].status !== 'queued') continue
      setQueue((q) => q.map((item, j) => (j === i ? { ...item, status: 'uploading' } : item)))
      try {
        const result = await api.uploadOne(queue[i].file)
        setQueue((q) =>
          q.map((item, j) =>
            j === i ? { ...item, status: result.status === 'ok' ? 'ok' : 'error', result } : item,
          ),
        )
        if (result.status === 'ok') onIngested()
      } catch (err) {
        setQueue((q) =>
          q.map((item, j) =>
            j === i
              ? {
                  ...item,
                  status: 'error',
                  result: {
                    filename: queue[i].file.name,
                    status: 'error',
                    detail: err instanceof Error ? err.message : String(err),
                  },
                }
              : item,
          ),
        )
      }
    }
    setBusy(false)
  }

  const pending = queue.filter((q) => q.status === 'queued').length

  return (
    <div className="page page-narrow">
      <header className="page-head">
        <h1>Upload CVs</h1>
      </header>

      <div
        className={`dropzone${dragOver ? ' is-over' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          addFiles(e.dataTransfer.files)
        }}
      >
        <p className="drop-lead">Drop PDF or DOCX files here</p>
        <p className="drop-sub">
          Each CV is parsed, profiled, and indexed for search. Re-uploading a file replaces its
          earlier version. Uploads stay private to this browser — other visitors never see them.
        </p>
        <button type="button" className="btn-secondary" onClick={() => inputRef.current?.click()}>
          Choose files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED.join(',')}
          multiple
          hidden
          onChange={(e) => {
            if (e.target.files) addFiles(e.target.files)
            e.target.value = ''
          }}
        />
      </div>

      {queue.length > 0 && (
        <>
          <ul className="queue">
            {queue.map((item, i) => (
              <li key={`${item.file.name}-${i}`} className={`queue-item st-${item.status}`}>
                <span className="queue-file mono">{item.file.name}</span>
                <span className="queue-status">
                  {item.status === 'queued' && 'Ready'}
                  {item.status === 'uploading' && (
                    <span className="thinking" aria-label="Uploading">
                      <i />
                      <i />
                      <i />
                    </span>
                  )}
                  {item.status === 'ok' &&
                    `${item.result?.name} · ${item.result?.chunks_indexed} chunks`}
                  {item.status === 'error' && (item.result?.detail ?? 'Failed')}
                </span>
              </li>
            ))}
          </ul>
          <div className="queue-actions">
            <button type="button" onClick={uploadAll} disabled={busy || pending === 0}>
              {busy ? 'Ingesting…' : `Ingest ${pending} file${pending === 1 ? '' : 's'}`}
            </button>
            {!busy && queue.some((q) => q.status !== 'queued') && (
              <button type="button" className="btn-secondary" onClick={() => setQueue([])}>
                Clear list
              </button>
            )}
          </div>
        </>
      )}
    </div>
  )
}
