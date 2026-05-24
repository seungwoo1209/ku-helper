import { SectionHead, Toggle } from '../components/ui';
import { updateNotification } from '../api/notifications';
import { fmtTime } from '../utils/time';

function transitRows(rules) {
  const active = rules.filter(r => r.on).slice(0, 2);
  if (!active.length) return [{ left: '등록된 교통 알림 없음', when: '–' }];
  return active.map(r => {
    const c = r.config;
    const when = c?.mode === 'recurring'
      ? `매 ${c.repeat_interval_minutes}분 ${fmtTime(c.start_time)}–${fmtTime(c.end_time)}`
      : c?.minutes_before ? `도착 ${c.minutes_before}분 전` : r.sub;
    return { left: r.name, when };
  });
}

function lunchRows(rules) {
  const active = rules.filter(r => r.on).slice(0, 2);
  if (!active.length) return [{ left: '등록된 점심 알림 없음', when: '–' }];
  return active.map(r => ({
    left: `추천 ${r.config?.recommend_count ?? 3}곳`,
    when: `평일 ${fmtTime(r.config?.notify_at ?? '')}`,
  }));
}

const CatCard = ({ num, name, summaryNum, unit, sub, rows, checked, onToggle, onOpen, catKey }) => (
  <div className="cat" data-cat={catKey}>
    <div className="cat-head">
      <div className="cat-title">
        <span className="num">{String(num).padStart(2, '0')}</span>
        <span className="name">{name}</span>
      </div>
      <Toggle checked={checked} onChange={onToggle} />
    </div>
    <div className="cat-summary">{summaryNum}<span className="unit">{unit}</span></div>
    <div className="cat-sub">{sub}</div>
    <div className="cat-list">
      {rows.map((r, i) => (
        <div className="cat-row" key={i}>
          <span>{r.left}</span>
          <span className="when">{r.when}</span>
        </div>
      ))}
    </div>
    <div className="cat-foot">
      <button className="link" onClick={onOpen}>규칙 관리 →</button>
      <span className="hint">마지막 발송 · 32분 전</span>
    </div>
  </div>
);

const DashboardScreen = ({ state, setState, openRule }) => {
  const { transit, lunch, library, feed } = state;

  /* 카테고리 토글 → 해당 카테고리 전체 규칙 bulk enable/disable */
  async function handleCategoryToggle(category, rulesKey, enabled) {
    const rules = state[category][rulesKey];
    // 낙관적 업데이트
    setState(s => ({
      ...s,
      [category]: {
        ...s[category],
        [rulesKey]: s[category][rulesKey].map(r => ({ ...r, on: enabled })),
      },
    }));
    // 백엔드 동기화 — 하나라도 실패하면 낙관적 업데이트 롤백
    const results = await Promise.allSettled(
      rules.map(r => updateNotification(category, r.id, { enabled }))
    );
    if (results.some(r => r.status === 'rejected')) {
      setState(s => ({
        ...s,
        [category]: {
          ...s[category],
          [rulesKey]: rules,
        },
      }));
    }
  }

  return (
    <>
      <div className="hero">
        <div className="hero-stat">
          <div className="label">오늘의 발송</div>
          <div className="figure">
            12<sup>건</sup>
            <span className="small">/ 14 예정</span>
          </div>
          <div className="caption">
            오전 8시 이후 지하철 알림 8건, 학식 1건, 도서관 임계값 알림 3건이 정상 발송되었습니다.
            남은 알림은 활성 시간대(07:30–22:00) 내에 처리됩니다.
          </div>
        </div>
        <div className="hero-side">
          <div className="row"><span className="k">활성 알림 규칙</span><span className="v">9개</span></div>
          <div className="row"><span className="k">이번 주 발송</span><span className="v">68건</span></div>
          <div className="row"><span className="k">발송 성공률</span><span className="v">99.2%</span></div>
          <div className="row"><span className="k">크롤러 상태</span><span className="v">정상 · 4/4</span></div>
          <div className="row"><span className="k">마지막 동기화</span><span className="v muted">11:42:08</span></div>
        </div>
      </div>

      <SectionHead title="알림 카테고리" meta="3종 / discord DM" />
      <div className="cats">
        <CatCard
          catKey="transit" num="01" name="교통"
          summaryNum={transit.rules.filter(r => r.on).length} unit="규칙 활성"
          sub="서울 공공 API · 1분 갱신"
          rows={transitRows(transit.rules)}
          checked={transit.rules.some(r => r.on)}
          onToggle={(v) => handleCategoryToggle('transit', 'rules', v)}
          onOpen={() => openRule('transit')}
        />
        <CatCard
          catKey="lunch" num="02" name="점심"
          summaryNum={fmtTime(lunch.rules.find(r => r.on)?.config?.notify_at ?? lunch.rules[0]?.config?.notify_at ?? '–')}
          unit="발송"
          sub="학식 크롤링 · 음식점 3+ 추천"
          rows={lunchRows(lunch.rules)}
          checked={lunch.rules.some(r => r.on)}
          onToggle={(v) => handleCategoryToggle('lunch', 'rules', v)}
          onOpen={() => openRule('lunch')}
        />
        <CatCard
          catKey="library" num="03" name="도서관"
          summaryNum={library.rooms.length} unit="열람실 감시"
          sub="잔여석 임계값 · 30초 이내 발송"
          rows={[
            { left: "제 1 열람실 — 20석 이하", when: "임계" },
            { left: "제 4 열람실 — 8석 이하 (긴급)", when: "긴급" },
          ]}
          checked={library.rooms.some(r => r.on)}
          onToggle={(v) => handleCategoryToggle('library', 'rooms', v)}
          onOpen={() => openRule('library')}
        />
      </div>

      <div className="feed">
        <SectionHead title="최근 알림" meta="최근 24시간 · 12건" />
        <div className="feed-list">
          {feed.map((f, i) => (
            <div className="feed-item" key={i}>
              <span className="time">{f.time}</span>
              <span className="kind" data-cat={f.kind.toLowerCase()}><span className="kdot"></span>{f.kind}</span>
              <span className="body">{f.title} <span className="muted">— {f.detail}</span></span>
              <span className={"status" + (f.fail ? " fail" : "")}>{f.fail ? "FAILED" : "SENT"}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

export default DashboardScreen;
