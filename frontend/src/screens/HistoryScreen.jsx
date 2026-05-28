import { useState, useMemo } from 'react';

const HistoryScreen = ({ state }) => {
  const [tab, setTab] = useState('all');
  const rows = useMemo(() => {
    return state.history.filter(r => tab === 'all' || r.kind.toLowerCase().includes(tab));
  }, [tab, state.history]);

  return (
    <>
      <div className="page-intro">
        <p>최근 30일 발송 이력을 조회합니다. 카테고리별 필터와 성공/실패 상태가 함께 표시됩니다.</p>
      </div>

      <div className="history-controls">
        <div className="tabs">
          {[['all','전체'],['transit','교통'],['lunch','점심'],['library','도서관'],['admin','시스템']].map(([k, label]) => (
            <button key={k} aria-pressed={tab === k} onClick={() => setTab(k)}>{label}</button>
          ))}
        </div>
        <span className="hint">총 {rows.length}건</span>
      </div>

      <div className="feed-list">
        {rows.map((f, i) => (
          <div className="feed-item" key={i}>
            <span className="time">{f.time}</span>
            <span className="kind" data-cat={f.kind.toLowerCase()}><span className="kdot"></span>{f.kind}</span>
            <span className="body">{f.title} <span className="muted">— {f.detail}</span></span>
            <span className={"status" + (f.fail ? " fail" : "")}>{f.fail ? "FAILED" : "SENT"}</span>
          </div>
        ))}
      </div>
    </>
  );
};

export default HistoryScreen;
