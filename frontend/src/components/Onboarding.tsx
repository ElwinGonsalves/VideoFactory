import {Brain, FileSpreadsheet, FlaskConical, KeyRound, PlayCircle, Sparkles, Spline} from 'lucide-react';
import {useEffect, useId, useState} from 'react';
import {api, type Job, type Onboarding as OnboardingInfo} from '../lib/api';
import {navigate, useLocalFlag} from '../lib/hooks';
import {useStudio} from '../lib/studio';
import {EngineSpine} from './Engines';
import {Overlay} from './Overlay';
import {Button, Field, Input, Notice, cx} from './ui';

const STEPS = ['Meet the creature', 'Give it a brain', 'First spark'];

export function OnboardingModal() {
  const {onboardingOpen, setOnboardingOpen, engines, refreshEngines, act, watch, toast, setDemo} = useStudio();
  const [, setOnboarded] = useLocalFlag('vf-onboarded');
  const [step, setStep] = useState(0);
  const [info, setInfo] = useState<OnboardingInfo | null>(null);
  const [key, setKey] = useState('');
  const [saving, setSaving] = useState(false);
  const keyId = useId();

  useEffect(() => {
    if (!onboardingOpen) return;
    void refreshEngines(false);
    void api<OnboardingInfo>('/api/onboarding').then(setInfo).catch(() => undefined);
  }, [onboardingOpen, refreshEngines]);

  const close = () => {
    setOnboarded(true);
    setOnboardingOpen(false);
    setStep(0);
  };
  const saveKey = () =>
    act(async () => {
      if (!key.trim()) throw new Error('Paste your Gemini API key first.');
      setSaving(true);
      try {
        await api('/api/settings/secrets', {method: 'PUT', body: {GEMINI_API_KEY: key.trim()}});
        const job = await api<Job>('/api/settings/test-llm', {method: 'POST'});
        watch(job, 'Testing the brain', (s) => toast(s === 'done' ? 'It speaks. The brain is connected.' : 'The brain did not answer. See the log in Studio Activity.', s === 'done' ? 'ok' : 'err'));
        setKey('');
        setInfo((i) => (i ? {...i, key_set: true} : i));
        setStep(2);
      } finally {
        setSaving(false);
      }
    });
  const demo = () => {
    setDemo(true);
    setOnboarded(true);
    setOnboardingOpen(false);
    toast('Judge Demo Mode on. Samples are loaded; no API key needed.', 'ok');
    navigate('library', info?.demo.sample_short ? {item: info.demo.sample_short} : undefined);
  };

  const footer = (
    <>
      <span className="mr-auto text-xs text-fog tabular">Step {step + 1} of 3</span>
      {step > 0 ? <Button variant="ghost" onClick={() => setStep(step - 1)}>Back</Button> : <Button variant="ghost" onClick={close}>Skip setup</Button>}
      {step < 2 ? <Button data-autofocus variant="primary" onClick={() => setStep(step + 1)}>{step === 1 && !info?.key_set ? 'Continue without a key' : 'Next'}</Button> : <Button data-autofocus variant="primary" onClick={close}>Enter the lab</Button>}
    </>
  );

  return (
    <Overlay open={onboardingOpen} onClose={close} title="Wake the creature" description="Three steps, under five minutes." footer={footer} wide>
      <ol className="mb-5 grid grid-cols-3 gap-2" aria-label="Setup progress">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? 'step' : undefined} className={cx('rounded-md border px-2 py-1.5 text-center text-xs font-semibold', i === step ? 'border-pumpkin text-bone' : i < step ? 'border-volt/40 text-volt' : 'border-lab-600 text-fog')}>
            <span className="tabular">{i + 1}.</span> {s}
          </li>
        ))}
      </ol>

      {step === 0 ? (
        <div>
          <p className="mb-4 text-moss">
            video-factory is stitched together from open-source organs that run on this machine. Here is how each one is doing:
          </p>
          {engines ? <EngineSpine engines={engines.engines} compact /> : <p className="text-sm text-moss">Listening for a heartbeat…</p>}
          {engines && !engines.required_ok ? (
            <Notice tone="blood" title="A vital organ is missing">
              Run <code className="font-mono">python scripts\bootstrap.py</code> once, then reopen this guide from Settings.
            </Notice>
          ) : null}
        </div>
      ) : null}

      {step === 1 ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-lab-600 bg-lab-850 p-4">
            <div className="mb-3 flex items-center gap-2 text-bone">
              <Brain aria-hidden className="size-5 text-pumpkin" />
              <h3 className="font-semibold">Connect Gemini (free tier)</h3>
            </div>
            {info?.key_set ? (
              <Notice tone="volt" title="A Gemini key is already saved">Scripts, ideas and titles will work. You can change it in Settings.</Notice>
            ) : (
              <>
                <Field label="Gemini API key" htmlFor={keyId} hint={<>Free at <a className="text-pumpkin underline underline-offset-4" href="https://aistudio.google.com/api-keys" target="_blank" rel="noopener noreferrer">aistudio.google.com</a>. Stored only in your local <code className="font-mono">.env</code>.</>}>
                  <Input id={keyId} type="password" name="gemini-key" spellCheck={false} placeholder="AIza…" value={key} onChange={(e) => setKey(e.target.value)} />
                </Field>
                <Button className="mt-3" variant="secondary" icon={KeyRound} loading={saving} onClick={saveKey}>Save &amp; Test Key</Button>
              </>
            )}
          </div>
          <div className="rounded-lg border border-dashed border-volt/50 bg-volt-deep/20 p-4">
            <div className="mb-3 flex items-center gap-2 text-bone">
              <FlaskConical aria-hidden className="size-5 text-volt" />
              <h3 className="font-semibold">1-Click Judge Demo Mode</h3>
            </div>
            <p className="text-sm text-moss">
              No key needed. Opens {info?.demo.sample_short ? 'a finished sample Short in the Library' : 'the sample project, ready to render without a key'}, the sample Style Blueprint in Ideas, and a validated sample batch in Batch.
            </p>
            <Button className="mt-3" variant="primary" icon={PlayCircle} onClick={demo}>Start Judge Demo</Button>
          </div>
        </div>
      ) : null}

      {step === 2 ? (
        <div>
          <p className="mb-4 text-moss">Pick where the first spark goes. You can do all three later.</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              {icon: Sparkles, title: 'Write from an idea', body: 'Type a topic, pick a style, render.', go: () => navigate('create')},
              {icon: Spline, title: 'Learn a style', body: 'Brainstorm or read a reference video.', go: () => navigate('ideas')},
              {icon: FileSpreadsheet, title: 'Queue a batch', body: 'Drop an Excel sheet of videos.', go: () => navigate('batch')},
            ].map((c) => (
              <button key={c.title} type="button" onClick={() => { c.go(); close(); }} className="flex min-h-28 flex-col items-start gap-2 rounded-lg border border-lab-600 bg-lab-850 p-4 text-left transition-[border-color,box-shadow] duration-200 hover:border-pumpkin/70 hover:shadow-[0_0_24px_-8px_rgb(255_166_77/0.5)]">
                <c.icon aria-hidden className="size-5 text-pumpkin" />
                <span className="font-semibold text-bone">{c.title}</span>
                <span className="text-sm text-moss">{c.body}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </Overlay>
  );
}
