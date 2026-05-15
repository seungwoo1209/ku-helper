import { StatusPill } from './ui';

const HEADINGS = {
  dashboard: { crumb: "Workspace / Dashboard",     en: "Good morning,",          ko: "서지원님" },
  transit:   { crumb: "Workspace / Transit",       en: "지하철 알림",             ko: "" },
  lunch:     { crumb: "Workspace / Lunch",         en: "학식 & 주변 추천",        ko: "" },
  library:   { crumb: "Workspace / Library",       en: "도서관 잔여석 감시",      ko: "" },
  history:   { crumb: "Records / History",         en: "발송 이력",               ko: "" },
  settings:  { crumb: "Records / Preferences",     en: "환경 설정",               ko: "" },
};

const TopBar = ({ route }) => {
  const h = HEADINGS[route];
  return (
    <div className="topbar">
      <div>
        <div className="crumb">{h.crumb}</div>
        <h1>{h.en} {h.ko && <span className="ko">{h.ko}</span>}</h1>
      </div>
      <StatusPill>시스템 정상 · DM 큐 0</StatusPill>
    </div>
  );
};

export default TopBar;
