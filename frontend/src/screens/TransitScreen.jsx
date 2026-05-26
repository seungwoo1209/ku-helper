import { useState } from 'react';
import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';
import { updateNotification, immediateSendTransit } from '../api/notifications';

const TransitScreen = ({ state, setState, onEdit, onAdd }) => {
  const rules = state.transit.rules;
  const [sending, setSending] = useState({});

  function sendLabel(id) {
    const st = sending[id];
    if (st === 'sending') return '발송 중…';
    if (st === 'ok') return '✓ 발송됨';
    if (st === 'rate') return '1분 후 재시도';
    if (st === 'err') return '오류';
    return '지금 발송 →';
  }

  async function handleSendNow(rule) {
    setSending(s => ({ ...s, [rule.id]: 'sending' }));
    try {
      await immediateSendTransit(rule.config.station_name, rule.config.line);
      setSending(s => ({ ...s, [rule.id]: 'ok' }));
    } catch (e) {
      setSending(s => ({ ...s, [rule.id]: e.message === 'RATE_LIMITED' ? 'rate' : 'err' }));
    }
    setTimeout(() => setSending(s => { const n = { ...s }; delete n[rule.id]; return n; }), 3000);
  }

  async function handleToggle(id, enabled) {
    setState(s => ({
      ...s,
      transit: { ...s.transit, rules: s.transit.rules.map(x => x.id === id ? { ...x, on: enabled } : x) },
    }));
    try {
      await updateNotification('transit', id, { enabled });
    } catch {
      setState(s => ({
        ...s,
        transit: { ...s.transit, rules: s.transit.rules.map(x => x.id === id ? { ...x, on: !enabled } : x) },
      }));
    }
  }

  return (
    <>
      <div className="page-intro">
        <p>
          역과 노선, 방향, 도착 N분 전 또는 정기 간격을 조합해 알림 규칙을 만듭니다.
          조건이 충족되면 디스코드 DM으로 도착 정보·지연 정보가 함께 전송됩니다.
        </p>
      </div>

      <SectionHead title="규칙" meta={`${rules.length}개 · ${rules.filter(r => r.on).length}개 활성`} />
      <div className="rules">
        {rules.length === 0 && <div className="hint" style={{ padding: '20px 0' }}>등록된 교통 알림이 없습니다.</div>}
        {rules.map((r, i) => (
          <div key={r.id}>
            <RuleRow idx={i + 1} title={r.name} sub={r.sub} conds={r.conds}
                     on={r.on}
                     onToggle={(v) => handleToggle(r.id, v)}
                     onEdit={() => onEdit(r)} />
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: -4, marginBottom: 8 }}>
              <button className="link" onClick={() => handleSendNow(r)} disabled={!!sending[r.id]}>
                {sendLabel(r.id)}
              </button>
            </div>
          </div>
        ))}
      </div>
      <button className="add-rule" onClick={onAdd}>
        <span className="plus">+</span> 새 교통 알림 규칙 만들기
      </button>

      <div className="divider"></div>
      <SectionHead title="DM 미리보기" meta="신촌역 · 2호선 내선순환 · 도착 3분 전" />
      <EmbedPreview
        kind="교통 · subway"
        title="신촌역 · 2호선 · 내선순환 도착 예정"
        sub="08:24 도착 · 3분 전 발송됨. 다음 열차는 08:31 도착 예정입니다."
        fields={[
          { k: "도착", v: "3분 후" },
          { k: "지연", v: "0분" },
        ]}
        footnote="campus 알리미 · 2026.05.13 08:21:04"
      />
    </>
  );
};

export default TransitScreen;
