import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import type { ImportApplyResponse, ImportProjectPreview } from '../types'
import { Modal } from './Modal'
import { useToast } from './Toast'

/**
 * Scan a local directory and import folders as projects.
 *
 * Flow: path → Scan (dry run, writes nothing) → review/select → Apply → done.
 * Re-scanning a known folder re-syncs it (new todos only), which the preview
 * states up front so "Import" is never a surprise.
 */

type Phase = 'form' | 'preview' | 'done'

function CheckIcon() {
  return (
    <svg
      width="22"
      height="22"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M5 13l4.5 4.5L19 7.5" />
    </svg>
  )
}

function plural(n: number, one: string, many = `${one}s`) {
  return `${n} ${n === 1 ? one : many}`
}

export function ImportDialog({
  open,
  onClose,
  onImported,
}: {
  open: boolean
  onClose: () => void
  /** Fired after a successful apply so the caller can refresh its list. */
  onImported: (result: ImportApplyResponse) => void
}) {
  const { toast } = useToast()

  const [phase, setPhase] = useState<Phase>('form')
  const [rootPath, setRootPath] = useState('')
  const [rootHint, setRootHint] = useState('')
  const [scanning, setScanning] = useState(false)
  const [applying, setApplying] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [previews, setPreviews] = useState<ImportProjectPreview[]>([])
  const [skipped, setSkipped] = useState<number>(0)
  const [scanErrors, setScanErrors] = useState<
    Array<{ folder: string; error: string }>
  >([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [result, setResult] = useState<ImportApplyResponse | null>(null)
  const [useAi, setUseAi] = useState(true)
  const [aiStatus, setAiStatus] = useState<string | null>(null)
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set())
  const pathRef = useRef<HTMLInputElement>(null)

  // Pre-fill the configured root the first time the dialog opens.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    void api
      .importRoots()
      .then((r) => {
        if (cancelled) return
        setRootHint(r.default_root)
        setRootPath((prev) => prev || r.default_root)
      })
      .catch(() => {
        /* non-fatal — the user can still type a path */
      })
    return () => {
      cancelled = true
    }
  }, [open])

  // Reset back to a clean form after the dialog has closed.
  useEffect(() => {
    if (open) return
    const t = window.setTimeout(() => {
      setPhase('form')
      setPreviews([])
      setSelected(new Set())
      setResult(null)
      setError(null)
      setScanErrors([])
      setSkipped(0)
      setAiStatus(null)
      setExpandedFiles(new Set())
    }, 240)
    return () => window.clearTimeout(t)
  }, [open])

  const scan = useCallback(async () => {
    setScanning(true)
    setError(null)
    try {
      const res = await api.importScan(rootPath.trim() || undefined, useAi)
      setPreviews(res.projects)
      setSkipped(res.skipped.length)
      setScanErrors(res.errors)
      setRootPath(res.root_path)
      if (res.ai_status) {
        const a = res.ai_status
        setAiStatus(
          a.llm_active
            ? `Groq · ${a.model || 'model'}`
            : a.configured
              ? 'AI idle (stub mode)'
              : 'No GROQ_API_KEY — heuristic scan only',
        )
      } else {
        setAiStatus(null)
      }
      // Preselect everything that would actually add something.
      setSelected(
        new Set(
          res.projects
            .filter(
              (p) =>
                (p.new_story_count ?? p.story_count) > 0 || !!p.brief,
            )
            .map((p) => p.folder),
        ),
      )
      setPhase('preview')
      if (res.projects.length === 0) {
        setError('No project folders found in that directory.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Scan failed')
    } finally {
      setScanning(false)
    }
  }, [rootPath, useAi])

  const apply = useCallback(async () => {
    if (selected.size === 0) return
    setApplying(true)
    setError(null)
    try {
      const res = await api.importApply(
        rootPath.trim() || undefined,
        [...selected],
        useAi,
      )
      setResult(res)
      setPhase('done')
      const created = res.projects_created
      const resynced = res.projects_resynced
      const parts: string[] = []
      if (created) parts.push(`Imported ${plural(created, 'project')}`)
      if (resynced) parts.push(`re-synced ${plural(resynced, 'project')}`)
      parts.push(`${plural(res.stories_created, 'story', 'stories')}`)
      toast(parts.join(', '))
      onImported(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setApplying(false)
    }
  }, [selected, rootPath, useAi, toast, onImported])

  const toggleFiles = (folder: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev)
      if (next.has(folder)) next.delete(folder)
      else next.add(folder)
      return next
    })
  }

  const toggle = (folder: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(folder)) next.delete(folder)
      else next.add(folder)
      return next
    })
  }

  const importable = previews.filter(
    (p) => (p.new_story_count ?? p.story_count) > 0 || p.brief,
  )
  const allSelected =
    importable.length > 0 && importable.every((p) => selected.has(p.folder))
  const selectedStories = previews
    .filter((p) => selected.has(p.folder))
    .reduce((n, p) => n + (p.new_story_count ?? p.story_count), 0)

  const busy = scanning || applying

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!busy) onClose()
      }}
      labelledBy="import-title"
      wide
    >
      <div className="modal-head">
        <h2 id="import-title" className="page-title">
          Import from folder
        </h2>
        <p className="page-sub">
          {phase === 'done'
            ? 'Import complete.'
            : 'Scan project folders, pack key source files, and optionally send them to Groq for brief + backlog analysis.'}
        </p>
      </div>

      {phase === 'done' && result ? (
        <>
          <div className="modal-body">
            <div className="import-done">
              <span className="import-done-mark">
                <CheckIcon />
              </span>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>
                  {result.projects_created > 0
                    ? `Imported ${plural(result.projects_created, 'project')}`
                    : 'Nothing new to create'}
                </div>
                <div
                  style={{
                    fontSize: 12.5,
                    color: 'var(--text-muted)',
                    marginTop: 3,
                  }}
                >
                  {plural(result.stories_created, 'story', 'stories')} added
                  {result.projects_resynced > 0 &&
                    ` · ${plural(result.projects_resynced, 'project')} re-synced`}
                </div>
              </div>
            </div>

            {result.imported.length > 0 && (
              <div className="import-list">
                {result.imported.map((r, i) => (
                  <div
                    key={r.source_path}
                    className="import-item"
                    style={{ ['--i' as string]: i }}
                  >
                    <div className="import-item-head">
                      <div style={{ minWidth: 0 }}>
                        <div className="import-item-name">{r.name}</div>
                        <div className="import-item-path">{r.source_path}</div>
                      </div>
                      <div className="import-item-pills">
                        <span className="pill pill-points">
                          +{r.stories_created}
                        </span>
                        {r.resynced && (
                          <span className="pill pill-muted">re-synced</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {result.errors.length > 0 && (
              <div style={{ display: 'grid', gap: 4 }}>
                {result.errors.map((e) => (
                  <div key={e.folder} className="import-error">
                    <strong>{e.folder}</strong> — {e.error}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="modal-foot">
            <button
              type="button"
              className="btn"
              onClick={() => {
                setPhase('form')
                setResult(null)
              }}
            >
              Import more
            </button>
            <button type="button" className="btn btn-primary" onClick={onClose}>
              Done
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="modal-body">
            <div className="import-toolbar">
              <label className="label">
                Projects directory
                <input
                  ref={pathRef}
                  className="input input-mono"
                  value={rootPath}
                  onChange={(e) => setRootPath(e.target.value)}
                  placeholder={rootHint || '/path/to/Projects'}
                  spellCheck={false}
                  disabled={busy}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      void scan()
                    }
                  }}
                />
              </label>
              <button
                type="button"
                className="btn"
                onClick={() => void scan()}
                disabled={busy}
              >
                {scanning && <span className="spinner" aria-hidden />}
                {scanning
                  ? useAi
                    ? 'Scanning + AI…'
                    : 'Scanning…'
                  : phase === 'preview'
                    ? 'Re-scan'
                    : 'Scan'}
              </button>
            </div>

            <label className="check" style={{ fontSize: 12.5 }}>
              <input
                type="checkbox"
                checked={useAi}
                disabled={busy}
                onChange={(e) => setUseAi(e.target.checked)}
              />
              Send key files to Groq (true AI analysis of each folder)
            </label>

            {aiStatus && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                AI: {aiStatus}
              </div>
            )}

            {rootHint && rootPath.trim() !== rootHint && (
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Default: <code>{rootHint}</code> — scanning is limited to this
                directory (set <code>PROJECTS_ROOT</code> to change it).
              </div>
            )}

            {error && <div className="alert">{error}</div>}

            {scanning && (
              <div className="import-list" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <div
                    key={i}
                    className="import-item"
                    style={{ ['--i' as string]: i }}
                  >
                    <div style={{ display: 'grid', gap: 6 }}>
                      <div className="skeleton" style={{ width: '46%' }} />
                      <div className="skeleton" style={{ width: '72%' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}

            {!scanning && phase === 'preview' && previews.length > 0 && (
              <>
                <div className="import-summary">
                  <label className="check">
                    <input
                      type="checkbox"
                      checked={allSelected}
                      onChange={() =>
                        setSelected(
                          allSelected
                            ? new Set()
                            : new Set(importable.map((p) => p.folder)),
                        )
                      }
                    />
                    Select all
                  </label>
                  <span style={{ marginLeft: 'auto' }}>
                    {selected.size} of {previews.length} selected ·{' '}
                    {plural(selectedStories, 'story', 'stories')}
                  </span>
                </div>

                <div className="import-list">
                  {previews.map((p, i) => {
                    const checked = selected.has(p.folder)
                    const known = p.existing_project_id != null
                    const fresh = p.new_story_count ?? p.story_count
                    const nothingToDo = fresh === 0 && !p.brief
                    return (
                      <div
                        key={p.source_path}
                        className={[
                          'import-item',
                          checked ? 'is-checked' : '',
                          known ? 'is-known' : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                        style={{ ['--i' as string]: i }}
                      >
                        <div className="import-item-head">
                          <label
                            className="check"
                            style={{ alignItems: 'flex-start', minWidth: 0 }}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              disabled={nothingToDo}
                              onChange={() => toggle(p.folder)}
                            />
                            <span style={{ minWidth: 0 }}>
                              <span className="import-item-name">{p.name}</span>
                              <span className="import-item-path">
                                {p.source_path}
                              </span>
                            </span>
                          </label>
                          <div className="import-item-pills">
                            {known && (
                              <span className="pill pill-muted">
                                already imported
                              </span>
                            )}
                            {p.ai_used && (
                              <span className="pill pill-progress">AI</span>
                            )}
                            {p.epic_count > 0 && (
                              <span className="pill pill-muted">
                                {plural(p.epic_count, 'epic')}
                              </span>
                            )}
                            <span className="pill pill-points">
                              {known
                                ? `+${fresh} new`
                                : plural(p.story_count, 'story', 'stories')}
                            </span>
                          </div>
                        </div>

                        {p.brief && (
                          <div
                            className="truncate"
                            style={{
                              fontSize: 12,
                              color: 'var(--text-muted)',
                            }}
                            title={p.brief}
                          >
                            {p.brief}
                          </div>
                        )}

                        {p.ai_analysis && (
                          <div
                            style={{
                              fontSize: 12,
                              color: 'var(--text-secondary)',
                              lineHeight: 1.45,
                            }}
                          >
                            <strong style={{ fontWeight: 600 }}>
                              AI analysis:{' '}
                            </strong>
                            {p.ai_analysis}
                          </div>
                        )}

                        {p.tech_stack && p.tech_stack.length > 0 && (
                          <div
                            style={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              gap: 4,
                            }}
                          >
                            {p.tech_stack.map((t) => (
                              <span key={t} className="pill pill-muted">
                                {t}
                              </span>
                            ))}
                          </div>
                        )}

                        {p.sample_titles.length > 0 && (
                          <ul className="import-samples">
                            {p.sample_titles.map((t) => (
                              <li key={t} className="truncate" title={t}>
                                {t}
                              </li>
                            ))}
                            {p.story_count > p.sample_titles.length && (
                              <li style={{ color: 'var(--text-muted)' }}>
                                +{p.story_count - p.sample_titles.length} more…
                              </li>
                            )}
                          </ul>
                        )}

                        {(p.story_sources.length > 0 || p.brief_source) && (
                          <div
                            style={{ fontSize: 11, color: 'var(--text-muted)' }}
                          >
                            from{' '}
                            {[p.brief_source, ...p.story_sources]
                              .filter(Boolean)
                              .join(', ')}
                            {p.ai_agent ? ` · ${p.ai_agent}` : ''}
                          </div>
                        )}

                        {p.codebase_context &&
                          p.codebase_context.file_count > 0 && (
                            <div style={{ fontSize: 11.5 }}>
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                style={{ padding: '2px 6px', fontSize: 11 }}
                                onClick={() => toggleFiles(p.folder)}
                              >
                                {expandedFiles.has(p.folder) ? 'Hide' : 'Show'}{' '}
                                {p.codebase_context.file_count} files sent to AI
                                {' · '}
                                {Math.round(
                                  (p.codebase_context.total_chars || 0) / 1000,
                                )}
                                k chars
                              </button>
                              {expandedFiles.has(p.folder) && (
                                <div
                                  style={{
                                    marginTop: 6,
                                    padding: 8,
                                    borderRadius: 8,
                                    background: 'var(--surface-2, var(--bg-elevated))',
                                    border: '1px solid var(--border)',
                                    maxHeight: 160,
                                    overflow: 'auto',
                                    fontFamily: 'var(--font-mono, ui-monospace, monospace)',
                                    fontSize: 11,
                                    color: 'var(--text-muted)',
                                  }}
                                >
                                  <div style={{ marginBottom: 4 }}>
                                    {p.codebase_context.note}
                                  </div>
                                  <ul
                                    style={{
                                      margin: 0,
                                      paddingLeft: 16,
                                    }}
                                  >
                                    {p.codebase_context.file_paths.map((fp) => (
                                      <li key={fp}>{fp}</li>
                                    ))}
                                  </ul>
                                  {p.codebase_context.tree_preview && (
                                    <pre
                                      style={{
                                        margin: '8px 0 0',
                                        whiteSpace: 'pre-wrap',
                                        fontSize: 10.5,
                                      }}
                                    >
                                      {p.codebase_context.tree_preview.slice(
                                        0,
                                        1200,
                                      )}
                                    </pre>
                                  )}
                                </div>
                              )}
                            </div>
                          )}

                        {p.llm_error && (
                          <div
                            style={{
                              fontSize: 11,
                              color: 'var(--danger, #c44)',
                            }}
                          >
                            AI note: {p.llm_error}
                          </div>
                        )}

                        {nothingToDo && (
                          <div
                            style={{ fontSize: 11, color: 'var(--text-muted)' }}
                          >
                            No brief or todos found — nothing to import.
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>

                {(skipped > 0 || scanErrors.length > 0) && (
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {skipped > 0 && `${skipped} folder(s) ignored`}
                    {skipped > 0 && scanErrors.length > 0 && ' · '}
                    {scanErrors.length > 0 &&
                      `${scanErrors.length} could not be read`}
                  </div>
                )}
              </>
            )}
          </div>

          <div className="modal-foot">
            {phase === 'preview' && previews.length > 0 && (
              <span
                style={{
                  marginRight: 'auto',
                  fontSize: 12,
                  color: 'var(--text-muted)',
                }}
              >
                {rootPath}
              </span>
            )}
            <button
              type="button"
              className="btn"
              onClick={onClose}
              disabled={busy}
            >
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || phase !== 'preview' || selected.size === 0}
              onClick={() => void apply()}
            >
              {applying && <span className="spinner" aria-hidden />}
              {applying
                ? 'Importing…'
                : selected.size > 0
                  ? `Import ${plural(selected.size, 'project')}`
                  : 'Import'}
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
