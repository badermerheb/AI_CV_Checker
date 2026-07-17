export interface Citation {
  n: number
  candidate_id: string
  candidate_name: string
  filename: string
  section: string | null
  page: number | null
  score: number | null
  snippet: string
}

export interface ChatResponse {
  session_id: string
  answer: string
  citations: Citation[]
  latency_ms: number
}

export interface CandidateRow {
  candidate_id: string
  name: string
  current_title: string
  years_experience: number
  location: string
  summary: string
  filename: string
  num_chunks: number
  created_at: string
}

export interface EducationItem {
  degree: string
  school: string
  year: string
}

export interface CandidateProfile {
  name: string
  current_title: string
  years_experience: number
  location: string
  skills: string[]
  education: EducationItem[]
  languages: string[]
  certifications: string[]
  summary: string
}

export interface CandidateDetail extends CandidateRow {
  profile: CandidateProfile
}

export interface UploadResult {
  filename: string
  status: 'ok' | 'error'
  detail?: string
  candidate_id?: string
  name?: string
  title?: string
  chunks_indexed?: number
}

export interface Stats {
  candidates: number
  chunks_indexed: number
}

// Same-origin by default (dev proxy / single-container deploy); set VITE_API_BASE
// at build time when the frontend is hosted separately (e.g. Vercel -> Render).
const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

// Anonymous per-browser workspace: uploads are private to this browser and layered
// on top of the shared read-only demo corpus. No login needed.
function workspaceId(): string {
  let id = localStorage.getItem('workspace_id')
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem('workspace_id', id)
  }
  return id
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/api${path}`, {
    ...init,
    headers: { ...init?.headers, 'X-Workspace-Id': workspaceId() },
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch {
      /* keep the status text */
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  chat(message: string, sessionId: string | null): Promise<ChatResponse> {
    return request('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    })
  },

  candidates(): Promise<{ candidates: CandidateRow[] }> {
    return request('/candidates')
  },

  candidate(id: string): Promise<CandidateDetail> {
    return request(`/candidates/${id}`)
  },

  async uploadOne(file: File): Promise<UploadResult> {
    const form = new FormData()
    form.append('files', file)
    const { results } = await request<{ results: UploadResult[] }>('/upload', {
      method: 'POST',
      body: form,
    })
    return results[0]
  },

  stats(): Promise<Stats> {
    return request('/stats')
  },
}
