import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';

const TransitScreen = ({ state, setState, onEdit, onAdd }) => {
  const rules = state.transit.rules;
  return (
    <>
      <div className="page-intro">
        <p>
          역과 노선, 방향, 도착 N분 전 또는 정기 간격을 조합해 알림 규칙을 만듭니다.
          조건이 충족되면 디스코드 DM으로 도착 정보·혼잡도·지연 정보가 함께 전송됩니다.
        </p>
      </div>

      <SectionHead title="규칙" meta={`${rules.length}개 · ${rules.filter(r => r.on).length}개 활성`} />
      <div className="rules">
        {rules.map((r, i) => (
          <RuleRow key={r.id} idx={i + 1} title={r.name} sub={r.sub} conds={r.conds}
                   on={r.on}
                   onToggle={(v) => setState(s => ({
                     ...s,
                     transit: { ...s.transit, rules: s.transit.rules.map(x => x.id === r.id ? { ...x, on: v } : x) }
                   }))}
                   onEdit={() => onEdit(r)} />
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
          { k: "혼잡도", v: "보통" },
          { k: "지연", v: "0분" },
        ]}
        footnote="campus 알리미 · 2026.05.13 08:21:04"
      />
    </>
  );
};

export default TransitScreen;
