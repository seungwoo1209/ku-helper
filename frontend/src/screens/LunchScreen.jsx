import { useState, useEffect, useCallback, useRef } from 'react';
import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';

/* ─── 오늘의 점심 데이터 페치 훅 ───────────────────────── */
function useTodayLunch() {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch('/api/lunch/today')
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, []);

  useEffect(() => { load(); }, [load]);

  return { data, loading, error, reload: load };
}

/* ─── 학식 카드 (코너 페이지네이션) ────────────────────── */
function CafeteriaCard({ cafeteria, loading, error, matchRef }) {
  const [idx, setIdx] = useState(0);

  if (loading) return (
    <div className="lunch-card lunch-card--paged" ref={matchRef}>
      <div className="lunch-card-shimmer" />
    </div>
  );

  if (error || !cafeteria) {
    return (
      <div className="lunch-card lunch-card--paged lunch-card--error" ref={matchRef}>
        <div className="lunch-card-label">오늘의 학식</div>
        <div className="lunch-card-empty">메뉴를 불러올 수 없습니다</div>
        {error && <div className="lunch-card-sub">{error}</div>}
      </div>
    );
  }

  const corners = cafeteria.corners ?? [];
  const hasData = !cafeteria.error && corners.length > 0;
  const corner  = corners[idx] ?? null;
  const total   = corners.length;

  const prev = () => setIdx(i => (i - 1 + total) % total);
  const next = () => setIdx(i => (i + 1) % total);

  return (
    <div className="lunch-card lunch-card--paged" ref={matchRef}>
      {/* 헤더 */}
      <div className="lunch-card-label">오늘의 학식</div>
      <div className="lunch-card-title">{cafeteria.cafeteria}</div>
      <div className="lunch-card-sub">{cafeteria.weekday}요일 · {cafeteria.date}</div>

      {/* 코너 콘텐츠 */}
      <div className="corner-paged-body">
        {!hasData || !corner ? (
          <div className="lunch-card-empty">{cafeteria.error ?? '메뉴 정보가 없습니다'}</div>
        ) : (
          <>
            <div className="corner-head">
              <span className="corner-name">{corner.name}</span>
              <span className="corner-meta">{corner.time} · {corner.meal}</span>
            </div>
            <ul className="lunch-menu-list">
              {corner.menus.map((item, j) => (
                <li key={j} className="lunch-menu-item">{item}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      {/* 페이지 네비게이션 */}
      {hasData && total > 1 && (
        <div className="corner-nav">
          <button className="corner-nav-btn" onClick={prev}>‹</button>
          <span className="corner-nav-pager">{idx + 1} / {total}</span>
          <button className="corner-nav-btn" onClick={next}>›</button>
        </div>
      )}
    </div>
  );
}

/* ─── 맛집 추천 카드 ────────────────────────────────────── */
function RestaurantsCard({ restaurants, loading, error, matchRef }) {
  if (loading) return <div className="lunch-card" ref={matchRef}><div className="lunch-card-shimmer" /></div>;

  if (error || !restaurants?.length) {
    return (
      <div className="lunch-card lunch-card--error" ref={matchRef}>
        <div className="lunch-card-label">추천 맛집</div>
        <div className="lunch-card-empty">추천 정보를 불러올 수 없습니다</div>
      </div>
    );
  }

  return (
    <div className="lunch-card" ref={matchRef}>
      <div className="lunch-card-label">오늘의 추천 맛집</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 8 }}>
        {restaurants.map((r, i) => (
          <div key={i} className="resto-row">
            <div className="resto-rank">{i + 1}</div>
            <div className="resto-body">
              <div className="resto-name">
                {r.link
                  ? <a href={r.link} target="_blank" rel="noopener noreferrer" className="resto-link">{r.name}</a>
                  : r.name}
                <span className="resto-cat">{r.category}</span>
              </div>
              {r.address && <div className="resto-address">{r.address}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── LunchScreen ────────────────────────────────────────── */
const LunchScreen = ({ state, setState, onEdit, onAdd }) => {
  const { data, loading, error, reload } = useTodayLunch();

  // 오른쪽 카드 높이를 측정해 왼쪽 카드에 동일하게 적용
  const rightRef = useRef(null);
  const leftRef  = useRef(null);

  useEffect(() => {
    if (!rightRef.current || !leftRef.current) return;
    const sync = () => {
      const h = rightRef.current.offsetHeight;
      if (h > 0) leftRef.current.style.height = h + 'px';
    };
    sync();
    const ro = new ResizeObserver(sync);
    ro.observe(rightRef.current);
    return () => ro.disconnect();
  }, [data]);

  const cafeteria   = data?.cafeteria;
  const restaurants = data?.restaurants;

  /* embed preview용 문자열 생성 */
  const previewSub = cafeteria && !cafeteria.error && cafeteria.menus.length > 0
    ? cafeteria.menus.slice(0, 3).join(' · ')
    : '학식 메뉴 로딩 중…';

  const previewFields = restaurants
    ? restaurants.map(r => ({ k: r.name, v: `${r.category}${r.address ? ' · ' + r.address : ''}` }))
    : [
        { k: "오늘의 추천", v: "소담 · 광진구 능동로" },
        { k: "추천 2",      v: "일미식당 · 광진구 화양동" },
        { k: "추천 3",      v: "건대닭갈비 · 광진구 동일로" },
      ];

  return (
    <>
      <div className="page-intro">
        <p>
          학식 메뉴를 자동 수집해 정해진 시간에 보내고, 예산 범위 내 주변 음식점을 함께 추천합니다.
          이전 추천 이력을 반영해 같은 식당이 반복되지 않도록 "오늘의 추천"을 강조합니다.
        </p>
      </div>

      {/* ── 오늘의 점심 라이브 패널 ── */}
      <div style={{ marginBottom: 48 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <SectionHead title="오늘의 점심" meta={loading ? '불러오는 중…' : error ? '오류' : '실시간'} />
          <button className="reload-btn" onClick={reload} disabled={loading} title="새로고침">
            <span style={{ display: 'inline-block', transform: loading ? 'rotate(360deg)' : 'none', transition: loading ? 'transform 0.6s linear' : 'none' }}>↻</span>
          </button>
        </div>
        <div className="lunch-live-grid">
          <CafeteriaCard cafeteria={cafeteria} loading={loading} error={error} matchRef={leftRef} />
          <RestaurantsCard restaurants={restaurants} loading={loading} error={error} matchRef={rightRef} />
        </div>
      </div>

      {/* ── 기존 알림 규칙 + 임베드 미리보기 ── */}
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
            title={`오늘의 학식 — ${cafeteria?.cafeteria ?? '본관 학생식당 A'}`}
            sub={`11:30 발송 · ${previewSub}`}
            fields={previewFields}
            footnote="네이버 지역 검색 · 리뷰 많은 순 50곳 중 무작위 3곳"
          />
          <div style={{ height: 12 }}></div>
          <div className="hint" style={{ padding: "10px 0", borderTop: "1px dashed var(--rule)" }}>
            추천 풀은 이전 30일 발송 이력을 반영해 중복을 회피합니다.
          </div>
        </div>
      </div>
    </>
  );
};

export default LunchScreen;
