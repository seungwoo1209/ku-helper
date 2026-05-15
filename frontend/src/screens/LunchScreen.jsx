import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';

const LunchScreen = ({ state, setState, onEdit, onAdd }) => (
  <>
    <div className="page-intro">
      <p>
        학식 메뉴를 자동 수집해 정해진 시간에 보내고, 예산 범위 내 주변 음식점을 함께 추천합니다.
        이전 추천 이력을 반영해 같은 식당이 반복되지 않도록 "오늘의 추천"을 강조합니다.
      </p>
    </div>

    <div className="two-col">
      <div>
        <SectionHead title="알림 시각 & 식당" meta="평일 기준" />
        <div className="rules">
          {state.lunch.rules.map((r, i) => (
            <RuleRow key={r.id} idx={i + 1} title={r.name} sub={r.sub} conds={r.conds}
                     on={r.on}
                     onToggle={(v) => setState(s => ({
                       ...s,
                       lunch: { ...s.lunch, rules: s.lunch.rules.map(x => x.id === r.id ? { ...x, on: v } : x) }
                     }))}
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
          sub="11:30 발송 · 김치찌개 · 닭갈비덮밥 · 모듬쌈 (₩5,500). 오늘의 추천은 '소담'입니다."
          fields={[
            { k: "오늘의 추천", v: "소담 · 비빔국수" },
            { k: "거리", v: "도보 3분" },
            { k: "가격", v: "₩7,500" },
          ]}
          footnote="추천 풀 12곳 · 예산 ₩9,000 이하"
        />
        <div style={{ height: 12 }}></div>
        <div className="hint" style={{ padding: "10px 0", borderTop: "1px dashed var(--rule)" }}>
          추천 풀은 이전 30일 발송 이력을 반영해 중복을 회피합니다.
        </div>
      </div>
    </div>
  </>
);

export default LunchScreen;
