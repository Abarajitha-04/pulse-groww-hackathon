import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { clearChatHistory, fetchChatHistory, sendChatMessage } from '../api/chat'
import type { ChatMessage } from '../api/types'

/**
 * A grounded Q&A assistant over the user's own watchlist data — not a
 * general chatbot. See app/services/chat_service.py for the
 * anti-hallucination + "not a financial advisor" design this UI is a
 * thin client for.
 */
export function ChatWidget() {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const queryClient = useQueryClient()
  const scrollRef = useRef<HTMLDivElement>(null)

  const historyQuery = useQuery({
    queryKey: ['chat-history'],
    queryFn: fetchChatHistory,
    enabled: open,
  })

  const sendMutation = useMutation({
    mutationFn: (message: string) => sendChatMessage(message),
    onMutate: async (message: string) => {
      const optimisticUser: ChatMessage = { role: 'user', content: message, created_at: new Date().toISOString() }
      queryClient.setQueryData<ChatMessage[]>(['chat-history'], (prev) => [...(prev ?? []), optimisticUser])
    },
    onSuccess: (res) => {
      const assistantMsg: ChatMessage = { role: 'assistant', content: res.reply, created_at: new Date().toISOString() }
      queryClient.setQueryData<ChatMessage[]>(['chat-history'], (prev) => [...(prev ?? []), assistantMsg])
    },
  })

  const clearMutation = useMutation({
    mutationFn: clearChatHistory,
    onSuccess: () => queryClient.setQueryData<ChatMessage[]>(['chat-history'], []),
  })

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [historyQuery.data, sendMutation.isPending])

  function handleSend() {
    const message = draft.trim()
    if (!message || sendMutation.isPending) return
    setDraft('')
    sendMutation.mutate(message)
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-40 rounded-full bg-blue-600 px-4 py-3 text-sm font-medium text-white shadow-lg hover:bg-blue-700"
        aria-label="Open watchlist assistant"
      >
        Ask Pulse
      </button>
    )
  }

  const messages = historyQuery.data ?? []

  return (
    <div className="fixed bottom-5 right-5 z-40 flex h-[28rem] w-80 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <div>
          <p className="text-sm font-semibold">Watchlist assistant</p>
          <p className="text-[11px] text-slate-400">Answers from your live data — not investment advice.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => clearMutation.mutate()}
            className="text-[11px] text-slate-400 hover:text-rose-600"
            title="Clear conversation"
          >
            Clear
          </button>
          <button onClick={() => setOpen(false)} className="text-slate-400 hover:text-slate-600" aria-label="Close">
            ✕
          </button>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {historyQuery.isLoading && <p className="text-xs text-slate-400">Loading…</p>}
        {!historyQuery.isLoading && messages.length === 0 && (
          <p className="text-xs text-slate-400">
            Ask me things like "what moved today?" or "why did RELIANCE jump?" — I'll only tell you what's actually
            in your data.
          </p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {sendMutation.isPending && <p className="text-xs text-slate-400">Thinking…</p>}
      </div>

      <div className="flex gap-2 border-t border-slate-100 p-3 dark:border-slate-800">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask about your watchlist…"
          className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-blue-500 dark:border-slate-700 dark:bg-slate-800"
        />
        <button
          onClick={handleSend}
          disabled={sendMutation.isPending || !draft.trim()}
          className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white disabled:opacity-40"
        >
          Send
        </button>
      </div>
    </div>
  )
}
