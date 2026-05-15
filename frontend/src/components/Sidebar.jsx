import { Ico, Icons } from './ui';

const NAV = [
  { id: "dashboard", label: "대시보드", icon: "dashboard" },
  { id: "transit",   label: "교통 알림", icon: "transit",   count: 3 },
  { id: "lunch",     label: "점심 알림", icon: "lunch",     count: 2 },
  { id: "library",   label: "도서관 알림", icon: "library", count: 3 },
  { id: "history",   label: "발송 이력", icon: "history" },
  { id: "settings",  label: "설정",     icon: "settings" },
];

const Sidebar = ({ route, setRoute }) => (
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
        <div className="avatar">서</div>
        <div>
          <div className="name">서지원</div>
          <div className="handle">seojiwon · #4912</div>
        </div>
      </div>
    </div>
  </aside>
);

export default Sidebar;
