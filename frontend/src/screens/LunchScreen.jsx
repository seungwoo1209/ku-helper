import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';
import { updateNotification } from '../api/notifications';

const fmtTime = (t) => (t ? t.slice(0, 5) : '');

const PREVIEW_FIELDS = [
  { k: '오늘의 추천', v: '소담 · 광진구 능동로' },
  { k: '추천 2',      v: '일미식당 · 광진구 화양동' },
  { k: '추천 3',      v: '건대닭갈비 · 광진구 동일로' },
];

const LunchScreen = ({ state, setState, onEdit, onAdd }) => {
  async function handleToggle(id, enabled) {
    setState(s => ({
      ...s,
      lunch: { ...s.lunch, rules: s.lunch.rules.map(x => x.id === id ? { ...x, on: enabled } : x) },
    }));
    try {
      await updateNotification('lunch', id, { enabled });
    } catch {
      setState(s => ({
        ...s,
        lunch: { ...s.lunch, rules: s.lunch.rules.map(x => x.id === id ? { ...x, on: !enabled } : x) },
      }));
    }
  }

  const activeRule = state.lunch.rules.find(r => r.on) ?? state.lunch.rules[0];
  const notifyAt = activeRule
    ? fmtTime(activeRule.config?.notify_at ?? '11:30')
    : '11:30';

  return (
    <>
      <div className="page-intro">
        <p>
          학식 메뉴와 예산 범위 내 주변 음식점을 정해진 시간에 디스코드 DM으로 보내드립니다.
        </p>
      </div>

      <div className="two-col">
        <div>
          <SectionHead title="알림 시각 & 식당" meta="평일 기준" />
          <div className="rules">
            {state.lunch.rules.length === 0 && (
              <div className="hint" style={{ padding: '20px 0' }}>등록된 점심 알림이 없습니다.</div>
            )}
            {state.lunch.rules.map((r, i) => (
              <RuleRow key={r.id} idx={i + 1} title={r.name} sub={r.sub} conds={r.conds}
                on={r.on}
                onToggle={(v) => handleToggle(r.id, v)}
                onEdit={() => onEdit(r)} />
            ))}
          </div>
          <button className="add-rule" onClick={onAdd}>
            <span className="plus">+</span> 새 점심 알림 만들기
          </button>
        </div>
        <div>
          <SectionHead title="DM 미리보기" />
          <EmbedPreview
            kind="점심 · lunch"
            title="오늘의 학식 — 본관 학생식당 A"
            sub={`${notifyAt} 발송 · 사골우거지해장국 · 고추잡채덮밥 · 쌀국수`}
            fields={PREVIEW_FIELDS}
            footnote="네이버 지역 검색 · 리뷰 많은 순 50곳 중 무작위 3곳"
          />
          <div style={{ height: 12 }} />
          <div className="hint" style={{ padding: '10px 0', borderTop: '1px dashed var(--rule)' }}>
            추천 풀은 이전 30일 발송 이력을 반영해 중복을 회피합니다.
          </div>
        </div>
      </div>
    </>
  );
};

export default LunchScreen;
