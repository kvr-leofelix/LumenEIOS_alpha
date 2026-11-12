import { FormEvent, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { MessageCircle, Mic, Square, Volume2, X } from 'lucide-react';
import { Button } from '../common/Button';
import { apiClient, type AssistantReply, type AssistantTurn } from '../../lib/apiClient';
import type { Role } from '../../types';

interface Recognition {
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
}

type Entry = AssistantTurn & Pick<Partial<AssistantReply>, 'links'>;
const examples: Partial<Record<Role, string[]>> = {
  admin: ['Compare overall competency across schools', 'Open audit logs'],
  student: ['Explain my competency scores', 'Open my answer sheets'],
  teacher: ['Where does my class need support?', 'Open the assessment studio'],
  principal: ['Compare curriculum completion by class', 'Open school subscriptions'],
  parent: ['Explain my child’s competency scores', 'Open child progress'],
};

export function AssistantPanel({ role }: { role: Role }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState('');
  const [messages, setMessages] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState('');
  const recognition = useRef<Recognition | null>(null);
  const pending = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const launcher = useRef<HTMLButtonElement>(null);
  const log = useRef<HTMLDivElement>(null);
  const voice = window as Window & {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  const SpeechRecognition = voice.SpeechRecognition ?? voice.webkitSpeechRecognition;

  useEffect(() => () => {
    pending.current?.abort();
    recognition.current?.abort();
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    if (open) input.current?.focus();
  }, [open]);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [messages, busy, open]);

  function close() {
    recognition.current?.abort();
    window.speechSynthesis?.cancel();
    setOpen(false);
    requestAnimationFrame(() => launcher.current?.focus());
  }

  function toggleMic() {
    if (recognition.current) {
      recognition.current.stop();
      return;
    }
    if (!SpeechRecognition) return;
    window.speechSynthesis?.cancel();
    setNotice('');
    const capture = new SpeechRecognition();
    capture.onresult = ({ results }) => {
      setDraft(Array.from(results, result => result[0].transcript).join(' ').slice(0, 2000));
      input.current?.focus();
    };
    capture.onerror = () => setNotice('Speech recognition was interrupted. Try again or type your question.');
    capture.onend = () => {
      recognition.current = null;
      setListening(false);
    };
    try {
      capture.start();
      recognition.current = capture;
      setListening(true);
    } catch {
      setNotice('The microphone could not start. You can type your question.');
    }
  }

  async function send(event: FormEvent) {
    event.preventDefault();
    const message = draft.trim();
    if (!message || pending.current || recognition.current) return;
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setDraft('');
    setNotice('');
    const history = messages.slice(-8).map(({ role, content }) => ({ role, content }));
    setMessages([...messages, { role: 'user', content: message }]);
    try {
      const reply = await apiClient.assistant.chat(message, history, controller.signal);
      setMessages(entries => [...entries, {
        role: 'assistant', content: reply.answer, links: reply.links,
      }]);
    } catch (error) {
      if (!controller.signal.aborted) {
        setMessages(messages);
        setDraft(current => current || message);
        setNotice(error instanceof Error ? error.message : 'Could not reach the assistant.');
      }
    } finally {
      pending.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <div className="fixed bottom-4 right-4 z-40 sm:bottom-6 sm:right-6">
      {!open ? (
        <button ref={launcher} type="button" onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-full bg-navy-800 px-4 py-3 text-sm font-semibold text-white shadow-lg hover:bg-navy-900"><MessageCircle size={18} />
          Ask LumenEIOS
        </button>
      ) : (
        <section aria-label="LumenEIOS assistant" onKeyDown={event => { if (event.key === 'Escape') close(); }}
          className="flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl border border-surface-border bg-surface-card shadow-2xl sm:w-96">
          <header className="flex items-center justify-between bg-navy-800 px-4 py-3 text-white">
            <h2 className="font-semibold">Ask LumenEIOS</h2>
            <button type="button" onClick={close} aria-label="Close assistant" className="rounded p-1 hover:bg-navy-700">
              <X size={20} />
            </button>
          </header>
          <div ref={log} role="log" aria-label="Conversation" className="h-72 min-h-0 space-y-3 overflow-y-auto p-4 text-sm">
            {!messages.length && examples[role]?.map(example => (
              <Button key={example} size="sm" variant="secondary" onClick={() => { setDraft(example); input.current?.focus(); }}>
                {example}
              </Button>
            ))}
            {messages.map(({ role: author, content, links }, index) => (
              <div key={index} className={author === 'user' ? 'ml-8 rounded-lg bg-navy-800 p-3 text-white' : 'mr-4 rounded-lg bg-surface-bg p-3 text-content-primary'}>
                <p className="whitespace-pre-wrap break-words">{content}</p>
                {links?.map(link => (
                  <Link key={link.path} to={link.path} onClick={close} className="mt-2 block font-semibold underline">
                    Open {link.label}
                  </Link>
                ))}
                {author === 'assistant' && 'speechSynthesis' in window && (
                  <button type="button" aria-label="Read answer aloud" className="mt-2 rounded p-1 text-content-secondary"
                    onClick={() => {
                      window.speechSynthesis.cancel();
                      window.speechSynthesis.speak(new SpeechSynthesisUtterance(content));
                    }}>
                    <Volume2 size={16} />
                  </button>
                )}
              </div>
            ))}
            {busy && <p className="text-content-secondary">Preparing an answer…</p>}
          </div>
          <form onSubmit={send} className="border-t border-surface-border p-3">
            {(notice || listening) && <p role="status" className="mb-2 text-sm text-content-secondary">{listening ? 'Listening…' : notice}</p>}
            <div className="flex items-center gap-2">
              <input ref={input} value={draft} onChange={event => setDraft(event.target.value)} maxLength={2000}
                aria-label="Your question" placeholder="Ask a question"
                className="min-w-0 flex-1 rounded-lg border border-surface-border bg-surface-bg px-3 py-2 text-sm text-content-primary" />
              {SpeechRecognition && (
                <button type="button" onClick={toggleMic} disabled={busy} aria-pressed={listening}
                  title="Your browser may use an online speech recognition service"
                  aria-label={listening ? 'Stop dictation' : 'Dictate question'}
                  className="rounded-lg border border-surface-border p-2 text-content-primary disabled:opacity-50">
                  {listening ? <Square size={18} /> : <Mic size={18} />}
                </button>
              )}
              <Button type="submit" size="sm" disabled={!draft.trim() || busy || listening}>Send</Button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}

