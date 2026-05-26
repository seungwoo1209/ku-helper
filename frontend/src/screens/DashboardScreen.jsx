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

function libraryRows(rooms) {
  const active = rooms.filter(r => r.on).slice(0, 2);
  if (!active.length) return [{ left: '등록된 도서관 알림 없음', when: '–' }];
  return active.map(r => ({
    left: r.name,
    when: r.config?.urgent_threshold ? '긴급' : '임계',
  }));
}

function todayKST() {
  const d = new Date(Date.now() + 9 * 60 * 60 * 1000);
  return `${String(d.getUTCMonth() + 1).padStart(2, '0')}-${String(d.getUTCDate()).padStart(2, '0')}`;
}

function computeStats(state) {
  const { transit, lunch, library, history } = state;
  const today = todayKST();

  const todayHistory = history.filter(h => h.time.startsWith(today));
  const todaySent    = todayHistory.filter(h => !h.fail).length;

  const successCount = history.filter(h => !h.fail).length;
  const successRate  = history.length > 0
    ? (successCount / history.length * 100).toFixed(1) + '%'
    : '–';

  const activeRules = transit.rules.filter(r => r.on).length
    + lunch.rules.filter(r => r.on).length
    + library.rooms.filter(r => r.on).length;

  const lastSync = history.length > 0 ? history[0].time.split(' ')[1] : '–';

  const todayCount = (kind) => todayHistory.filter(h => h.kind === kind && !h.fail).length;

  const captionParts = [
    todayCount('TRANSIT') && `교통 ${todayCount('TRANSIT')}건`,
    todayCount('LUNCH')   && `점심 ${todayCount('LUNCH')}건`,
    todayCount('LIBRARY') && `도서관 ${todayCount('LIBRARY')}건`,
  ].filter(Boolean);
  const caption = captionParts.length > 0
    ? `오늘 ${captionParts.join(', ')} 발송되었습니다.`
    : '오늘 발송된 알림이 없습니다.';

  const lastSentOf = (kind) => {
    const item = history.find(h => h.kind === kind);
    return item ? `마지막 발송 · ${item.time}` : '발송 이력 없음';
  };

  return { todaySent, successRate, activeRules, lastSync, caption, lastSentOf };
}

const CatCard = ({ num, name, summaryNum, unit, sub, rows, checked, onToggle, onOpen, catKey, lastSentLabel }) => (
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
      <span className="hint">{lastSentLabel}</span>
    </div>
  </div>
);

const DashboardScreen = ({ state, setState, openRule }) => {
  const { transit, lunch, library, history } = state;
  const { todaySent, successRate, activeRules, lastSync, caption, lastSentOf } = computeStats(state);

  async function handleCategoryToggle(category, rulesKey, enabled) {
    const rules = state[category][rulesKey];
    setState(s => ({
      ...s,
      [category]: {
        ...s[category],
        [rulesKey]: s[category][rulesKey].map(r => ({ ...r, on: enabled })),
      },
    }));
    const results = await Promise.allSettled(
      rules.map(r => updateNotification(category, r.id, { enabled }))
    );
    if (results.some(r => r.status === 'rejected')) {
      setState(s => ({
        ...s,
        [category]: { ...s[category], [rulesKey]: rules },
      }));
    }
  }

  return (
    <>
      <div className="hero">
        <div className="hero-stat">
          <div className="label">오늘의 발송</div>
          <div className="figure">
            {todaySent}<sup>건</sup>
          </div>
          <div className="caption">{caption}</div>
        </div>
        <div className="hero-side">
          <div className="row"><span className="k">활성 알림 규칙</span><span className="v">{activeRules}개</span></div>
          <div className="row"><span className="k">최근 발송</span><span className="v">{history.length}건</span></div>
          <div className="row"><span className="k">발송 성공률</span><span className="v">{successRate}</span></div>
          <div className="row"><span className="k">마지막 동기화</span><span className="v muted">{lastSync}</span></div>
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
          lastSentLabel={lastSentOf('TRANSIT')}
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
          lastSentLabel={lastSentOf('LUNCH')}
        />
        <CatCard
          catKey="library" num="03" name="도서관"
          summaryNum={library.rooms.filter(r => r.on).length} unit="열람실 감시"
          sub="잔여석 임계값 · 30초 이내 발송"
          rows={libraryRows(library.rooms)}
          checked={library.rooms.some(r => r.on)}
          onToggle={(v) => handleCategoryToggle('library', 'rooms', v)}
          onOpen={() => openRule('library')}
          lastSentLabel={lastSentOf('LIBRARY')}
        />
      </div>

      <div className="feed">
        <SectionHead title="최근 알림" meta={`${history.length}건`} />
        <div className="feed-list">
          {history.map((f, i) => (
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
