import { Ico, Icons } from './ui';

const NAV = [
  { id: "dashboard", label: "대시보드", icon: "dashboard" },
  { id: "transit",   label: "교통 알림", icon: "transit",   count: 3 },
  { id: "lunch",     label: "점심 알림", icon: "lunch",     count: 2 },
  { id: "library",   label: "도서관 알림", icon: "library", count: 3 },
  { id: "history",   label: "발송 이력", icon: "history" },
  { id: "settings",  label: "설정",     icon: "settings" },
];

const Sidebar = ({ route, setRoute, user, onLogout }) => {
  const initial = user?.discord_username?.[0]?.toUpperCase() ?? '?';
  const username = user?.discord_username ?? '알 수 없음';

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark"></span>
        <span className="brand-name">campus<b>알리미</b></span>
      </div>

      <div className="nav-group">
        <div className="nav-section-label">Workspace</div>
        <div className="nav">
          {NAV.slice(0, 4).map(item => (
            <button key={item.id}
                    className="nav-item"
                    aria-current={route === item.id ? "page" : undefined}
                    onClick={() => setRoute(item.id)}>
              <Ico d={Icons[item.icon]} />
              <span>{item.label}</span>
              {item.count != null && <span className="count">{item.count}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="nav-group">
        <div className="nav-section-label">Records</div>
        <div className="nav">
          {NAV.slice(4).map(item => (
            <button key={item.id}
                    className="nav-item"
                    aria-current={route === item.id ? "page" : undefined}
                    onClick={() => setRoute(item.id)}>
              <Ico d={Icons[item.icon]} />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="sidebar-foot">
        <div className="user">
          <div className="avatar" style={{ background: '#5865F2', color: '#fff' }}>{initial}</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="name">{username}</div>
            <div className="handle">Discord</div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              title="로그아웃"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-50)', fontSize: 14, padding: '2px 4px' }}
            >
              ↩
            </button>
          )}
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
