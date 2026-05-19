import { SectionHead, Toggle } from '../components/ui';

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
          rows={[
            { left: "신촌 2호선 — 등굣길", when: "월–금 08:25" },
            { left: "강남 9호선 — 자취", when: "매 15분 18:00–19:30" },
          ]}
          checked={transit.on}
          onToggle={(v) => setState(s => ({ ...s, transit: { ...s.transit, on: v } }))}
          onOpen={() => openRule('transit')}
        />
        <CatCard
          catKey="lunch" num="02" name="점심"
          summaryNum="11:30" unit="발송"
          sub="학식 크롤링 · 음식점 3+ 추천"
          rows={[
            { left: "학생식당 A · 본관", when: "평일 11:30" },
            { left: "주변 음식점 — ₩9,000 이하", when: "조건 활성" },
          ]}
          checked={lunch.on}
          onToggle={(v) => setState(s => ({ ...s, lunch: { ...s.lunch, on: v } }))}
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
          checked={library.on}
          onToggle={(v) => setState(s => ({ ...s, library: { ...s.library, on: v } }))}
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
