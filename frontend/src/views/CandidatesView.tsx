import { useEffect, useState } from 'react'
import { api, type CandidateDetail, type CandidateRow } from '../api'

function DetailPanel({ id }: { id: string }) {
  const [detail, setDetail] = useState<CandidateDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDetail(null)
    setError(null)
    api.candidate(id).then(setDetail).catch((e) => setError(String(e.message ?? e)))
  }, [id])

  if (error) return <div className="detail detail-error">Couldn't load this profile: {error}</div>
  if (!detail) return <div className="detail"><div className="skeleton" style={{ width: '60%' }} /></div>

  const p = detail.profile
  return (
    <div className="detail">
      {p.summary && <p className="detail-summary">{p.summary}</p>}
      {p.skills.length > 0 && (
        <div className="detail-block">
          <span className="detail-label">Skills</span>
          <div className="chips">
            {p.skills.map((s) => (
              <span key={s} className="chip">
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
      {p.education.length > 0 && (
        <div className="detail-block">
          <span className="detail-label">Education</span>
          {p.education.map((e, i) => (
            <p key={i} className="detail-line">
              {e.degree}
              {e.school ? `, ${e.school}` : ''}
              {e.year ? ` (${e.year})` : ''}
            </p>
          ))}
        </div>
      )}
      {p.languages.length > 0 && (
        <div className="detail-block">
          <span className="detail-label">Languages</span>
          <p className="detail-line">{p.languages.join(' · ')}</p>
        </div>
      )}
      {p.certifications.length > 0 && (
        <div className="detail-block">
          <span className="detail-label">Certifications</span>
          {p.certifications.map((c) => (
            <p key={c} className="detail-line">
              {c}
            </p>
          ))}
        </div>
      )}
      <p className="detail-file">
        Source: <span className="mono">{detail.filename}</span> · {detail.num_chunks} chunks indexed
      </p>
    </div>
  )
}

export default function CandidatesView() {
  const [rows, setRows] = useState<CandidateRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [openId, setOpenId] = useState<string | null>(null)

  useEffect(() => {
    api
      .candidates()
      .then((r) => setRows(r.candidates))
      .catch((e) => setError(String(e.message ?? e)))
  }, [])

  const filtered = rows?.filter((r) => {
    const q = query.trim().toLowerCase()
    if (!q) return true
    return `${r.name} ${r.current_title} ${r.location}`.toLowerCase().includes(q)
  })

  return (
    <div className="page">
      <header className="page-head">
        <h1>Candidates</h1>
        <input
          type="search"
          className="search"
          placeholder="Filter by name, title, or location"
          aria-label="Filter candidates"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </header>

      {error && <p className="notice notice-error">Couldn't load candidates: {error}</p>}

      {!rows && !error && (
        <div className="table">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="skeleton row-skeleton" />
          ))}
        </div>
      )}

      {rows && rows.length === 0 && (
        <div className="empty">
          <h2>No candidates yet</h2>
          <p>Upload a few CVs and each candidate shows up here with an extracted profile.</p>
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <div className="table" role="list">
          <div className="table-head" aria-hidden="true">
            <span>Name</span>
            <span>Title</span>
            <span className="num">Experience</span>
            <span>Location</span>
          </div>
          {filtered.map((r) => (
            <div key={r.candidate_id} role="listitem">
              <button
                type="button"
                className={`table-row${openId === r.candidate_id ? ' is-open' : ''}`}
                aria-expanded={openId === r.candidate_id}
                onClick={() => setOpenId(openId === r.candidate_id ? null : r.candidate_id)}
              >
                <span className="cell-name">{r.name}</span>
                <span>{r.current_title || '—'}</span>
                <span className="num">
                  {r.years_experience ? `${r.years_experience} yr${r.years_experience === 1 ? '' : 's'}` : '—'}
                </span>
                <span>{r.location || '—'}</span>
              </button>
              {openId === r.candidate_id && <DetailPanel id={r.candidate_id} />}
            </div>
          ))}
        </div>
      )}

      {rows && rows.length > 0 && filtered && filtered.length === 0 && (
        <p className="notice">No candidates match “{query}”.</p>
      )}
    </div>
  )
}
