import { useState, useEffect } from 'react';
import { Modal, Field, Btn } from '../components/ui';
import { createNotification, updateNotification, deleteNotification } from '../api/notifications';
import { fmtTime } from '../utils/time';

/* ── Transit 폼 ─────────────────────────────────── */
function TransitForm({ config, onChange }) {
  const c = config;
  const set = (key, val) => onChange({ ...c, [key]: val });

  return (
    <>
      <div className="field-row">
        <Field label="역명">
          <input className="input" value={c.station_name} onChange={e => set('station_name', e.target.value)} placeholder="예) 신촌" />
        </Field>
        <Field label="노선">
          <select className="select" value={c.line} onChange={e => set('line', e.target.value)}>
            {['1호선','2호선','3호선','4호선','5호선','6호선','7호선','8호선','9호선'].map(l => <option key={l}>{l}</option>)}
          </select>
        </Field>
      </div>
      <Field label="알림 방식">
        <div style={{ display: 'flex', gap: 8 }}>
          {[['arrival','도착 N분 전'],['recurring','정기 간격']].map(([v, l]) => (
            <button key={v} type="button" className="chip"
              aria-pressed={c.mode === v}
              onClick={() => set('mode', v)}>{l}</button>
          ))}
        </div>
      </Field>
      {c.mode === 'arrival' ? (
        <>
          <div className="field-row">
            <Field label="방향">
              <select className="select" value={c.direction} onChange={e => set('direction', e.target.value)}>
                {['상행','하행','내선','외선'].map(d => <option key={d}>{d}</option>)}
              </select>
            </Field>
            <Field label="도착 몇 분 전">
              <input className="input" type="number" min={1} max={120}
                value={c.minutes_before} onChange={e => set('minutes_before', Number(e.target.value))} />
            </Field>
          </div>
        </>
      ) : (
        <div className="field-row">
          <Field label="시작 시각"><input className="input" type="time" value={fmtTime(c.start_time)} onChange={e => set('start_time', e.target.value)} /></Field>
          <Field label="종료 시각"><input className="input" type="time" value={fmtTime(c.end_time)} onChange={e => set('end_time', e.target.value)} /></Field>
          <Field label="반복 간격 (분)">
            <input className="input" type="number" min={1} max={180}
              value={c.repeat_interval_minutes} onChange={e => set('repeat_interval_minutes', Number(e.target.value))} />
          </Field>
        </div>
      )}
      <Field label="혼잡도 포함">
        <div style={{ display: 'flex', gap: 8 }}>
          {[['true','포함'],['false','제외']].map(([v, l]) => (
            <button key={v} type="button" className="chip"
              aria-pressed={String(c.include_congestion) === v}
              onClick={() => set('include_congestion', v === 'true')}>{l}</button>
          ))}
        </div>
      </Field>
    </>
  );
}

/* ── Lunch 폼 ───────────────────────────────────── */
function LunchForm({ config, onChange }) {
  const c = config;
  const set = (key, val) => onChange({ ...c, [key]: val });

  return (
    <>
      <div className="field-row">
        <Field label="발송 시각">
          <input className="input" type="time" value={fmtTime(c.notify_at)} onChange={e => set('notify_at', e.target.value)} />
        </Field>
        <Field label="추천 음식점 수 (1–10)">
          <input className="input" type="number" min={1} max={10}
            value={c.recommend_count} onChange={e => set('recommend_count', Number(e.target.value))} />
        </Field>
      </div>
      <Field label="주변 음식점 최대 가격 (선택)">
        <input className="input" type="number" min={0} placeholder="예) 9000 (빈칸이면 제한 없음)"
          value={c.max_price ?? ''} onChange={e => set('max_price', e.target.value ? Number(e.target.value) : null)} />
      </Field>
      <Field label="오늘의 추천 강조">
        <div style={{ display: 'flex', gap: 8 }}>
          {[['true','켜기'],['false','끄기']].map(([v, l]) => (
            <button key={v} type="button" className="chip"
              aria-pressed={String(c.highlight_today_pick) === v}
              onClick={() => set('highlight_today_pick', v === 'true')}>{l}</button>
          ))}
        </div>
      </Field>
    </>
  );
}

/* ── Library 폼 ─────────────────────────────────── */
const READING_ROOMS = ['제1열람실','제2열람실','제3열람실','제4열람실','대학원열람실'];

function LibraryForm({ config, onChange }) {
  const c = config;
  const set = (key, val) => onChange({ ...c, [key]: val });

  return (
    <>
      <Field label="열람실">
        <select className="select" value={c.reading_room_id} onChange={e => set('reading_room_id', e.target.value)}>
          {READING_ROOMS.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
      </Field>
      <div className="field-row">
        <Field label="알림 임계값 (잔여 좌석)">
          <input className="input" type="number" min={0}
            value={c.threshold} onChange={e => set('threshold', Number(e.target.value))} />
        </Field>
        <Field label="긴급 임계값 (선택)">
          <input className="input" type="number" min={0} placeholder="빈칸이면 없음"
            value={c.urgent_threshold ?? ''} onChange={e => set('urgent_threshold', e.target.value ? Number(e.target.value) : null)} />
        </Field>
      </div>
    </>
  );
}

/* ── 기본 config 초기값 ──────────────────────────── */
function defaultConfig(kind, existing) {
  if (existing) return kind === 'transit' ? { direction: '상행', ...existing } : { ...existing };
  if (kind === 'transit') return { mode: 'arrival', station_name: '', line: '2호선', direction: '상행', minutes_before: 3, include_congestion: true, start_time: '08:00', end_time: '09:30', repeat_interval_minutes: 15 };
  if (kind === 'lunch')   return { notify_at: '11:30', max_price: null, recommend_count: 3, highlight_today_pick: true };
  if (kind === 'library') return { reading_room_id: READING_ROOMS[0], threshold: 20, urgent_threshold: null };
  return {};
}

/* ── RuleEditModal ──────────────────────────────── */
const RuleEditModal = ({ open, rule, onClose, onSave, kind }) => {
  const [config, setConfig] = useState(() => defaultConfig(kind, rule?.config));
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    setConfig(defaultConfig(kind, rule?.config));
    setError(null);
  }, [open, rule, kind]);

  const typeMap = { transit: 'TRANSIT', lunch: 'LUNCH', library: 'LIBRARY' };

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      if (rule?.id) {
        await updateNotification(kind, rule.id, { config });
      } else {
        await createNotification({ type: typeMap[kind], enabled: true, config });
      }
      await onSave();
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!rule?.id) return;
    setDeleting(true);
    setError(null);
    try {
      await deleteNotification(rule.id);
      await onSave();
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(false);
    }
  }

  const crumb = kind === 'transit' ? '교통 알림' : kind === 'lunch' ? '점심 알림' : '도서관 알림';

  return (
    <Modal open={open} onClose={onClose} crumb={crumb} title={rule ? '규칙 편집' : '새 규칙'}
      footer={<>
        {rule?.id && (
          <Btn onClick={handleDelete} disabled={deleting || saving}
               style={{ marginRight: 'auto', color: 'var(--bad)' }}>
            {deleting ? '삭제 중…' : '삭제'}
          </Btn>
        )}
        <Btn onClick={onClose} disabled={saving || deleting}>취소</Btn>
        <Btn primary onClick={handleSave} disabled={saving || deleting}>
          {saving ? '저장 중…' : '저장'}
        </Btn>
      </>}>
      {kind === 'transit' && <TransitForm config={config} onChange={setConfig} />}
      {kind === 'lunch'   && <LunchForm   config={config} onChange={setConfig} />}
      {kind === 'library' && <LibraryForm config={config} onChange={setConfig} />}
      {error && <div style={{ color: 'var(--bad)', fontSize: 13, marginTop: 8 }}>오류: {error}</div>}
    </Modal>
  );
};

export default RuleEditModal;
