import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import LoginScreen from './components/LoginScreen';
import DashboardScreen from './screens/DashboardScreen';
import TransitScreen from './screens/TransitScreen';
import LunchScreen from './screens/LunchScreen';
import LibraryScreen from './screens/LibraryScreen';
import HistoryScreen from './screens/HistoryScreen';
import SettingsScreen from './screens/SettingsScreen';
import RuleEditModal from './screens/RuleEditModal';
import { SAMPLE } from './data/sample';
import { listNotifications, buildStateFromNotifications, listNotificationHistory, buildHistoryFromResponse } from './api/notifications';
import { setTokens, getAccessToken, clearTokens, callRefresh, callLogout } from './api/auth';

const ROUTE_LABELS = {
  dashboard: "01 대시보드", transit: "02 교통", lunch: "03 점심",
  library: "04 도서관", history: "05 이력", settings: "06 설정",
};

async function fetchMe(token) {
  const res = await fetch('/api/v1/users/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return null;
  return res.json();
}

function App() {
  const [user, setUser]     = useState(null);   // { id, discord_id, discord_username, ... }
  const [authReady, setAuthReady] = useState(false);
  const [route, setRoute]   = useState("dashboard");
  const [state, setState]   = useState(SAMPLE);
  const [modal, setModal]   = useState(null);
  const [tweaksOpen, setTweaksOpen] = useState(false);

  // OAuth 콜백 처리 + 기존 token 복원
  useEffect(() => {
    async function init() {
      // 1. URL params에서 token 추출 (Discord OAuth 콜백 직후)
      const params = new URLSearchParams(window.location.search);
      const tokenFromUrl = params.get('access_token');
      const refreshFromUrl = params.get('refresh_token');
      if (tokenFromUrl) {
        setTokens(tokenFromUrl, refreshFromUrl);
        window.history.replaceState({}, '', window.location.pathname);
      }

      // 2. 저장된 access token으로 유저 정보 조회 (만료 시 refresh 1회 재시도)
      let token = getAccessToken();
      if (token) {
        let me = await fetchMe(token);
        if (!me) {
          const newToken = await callRefresh();
          if (newToken) me = await fetchMe(newToken);
        }
        if (me) {
          setUser(me);
          setState(s => ({
            ...s,
            transit: { rules: [] }, lunch: { rules: [] }, library: { rooms: [] }, history: [],
          }));
          try {
            const notifications = await listNotifications();
            setState(s => ({ ...s, ...buildStateFromNotifications(notifications) }));
          } catch (_) {}
          try {
            const history = await listNotificationHistory();
            setState(s => ({ ...s, history: buildHistoryFromResponse(history) }));
          } catch (_) {}
        } else {
          clearTokens();
        }
      }
      setAuthReady(true);
    }
    init();
  }, []);

  useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === '__activate_edit_mode') setTweaksOpen(true);
      else if (e.data?.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  async function logout() {
    await callLogout();
    setUser(null);
  }

  if (!authReady) return null; // 초기화 중 빈 화면
  if (!user) return (
    <LoginScreen onDevLogin={import.meta.env.DEV ? () => setUser({
      id: 0, discord_id: 0, discord_username: 'dev_user',
      created_at: new Date().toISOString(), updated_at: new Date().toISOString(),
    }) : undefined} />
  );

  const reloadNotifications = async () => {
    try {
      const notifications = await listNotifications();
      setState(s => ({ ...s, ...buildStateFromNotifications(notifications) }));
    } catch (_) {}
    try {
      const history = await listNotificationHistory();
      setState(s => ({ ...s, history: buildHistoryFromResponse(history) }));
    } catch (_) {}
  };

  const openRuleEditor = (kind, rule = null) => setModal({ kind, rule });
  const closeModal = () => setModal(null);

  let body;
  if (route === "dashboard") {
    body = <DashboardScreen state={state} setState={setState} openRule={(k) => setRoute(k)} />;
  } else if (route === "transit") {
    body = <TransitScreen state={state} setState={setState}
              onEdit={(r) => openRuleEditor('transit', r)}
              onAdd={() => openRuleEditor('transit', null)} />;
  } else if (route === "lunch") {
    body = <LunchScreen state={state} setState={setState}
              onEdit={(r) => openRuleEditor('lunch', r)}
              onAdd={() => openRuleEditor('lunch', null)} />;
  } else if (route === "library") {
    body = <LibraryScreen state={state} setState={setState}
              onEdit={(r) => openRuleEditor('library', r)}
              onAdd={() => openRuleEditor('library', null)} />;
  } else if (route === "history") {
    body = <HistoryScreen state={state} />;
  } else if (route === "settings") {
    body = <SettingsScreen state={state} setState={setState} />;
  }

  return (
    <div className="app">
      <Sidebar route={route} setRoute={setRoute} user={user} onLogout={logout} />
      <main className="main" data-screen-label={ROUTE_LABELS[route] || route}>
        <TopBar route={route} user={user} />
        {body}
      </main>

      <RuleEditModal
        open={!!modal}
        kind={modal?.kind}
        rule={modal?.rule}
        onClose={closeModal}
        onSave={async () => { await reloadNotifications(); closeModal(); }}
      />

      {tweaksOpen && (
        <TweaksMini
          route={route} setRoute={setRoute}
          onClose={() => {
            setTweaksOpen(false);
            window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*');
          }} />
      )}
    </div>
  );
}

const TweaksMini = ({ route, setRoute, onClose }) => (
  <div style={{
    position: 'fixed', right: 24, bottom: 24,
    width: 280, background: 'var(--paper)',
    border: '1px solid var(--rule)', borderRadius: 10,
    boxShadow: '0 12px 36px -12px rgba(17,38,17,.3)',
    zIndex: 100, overflow: 'hidden'
  }}>
    <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--rule)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--ink-50)' }}>Tweaks</span>
      <button onClick={onClose} style={{ background: 'none', border: 0, color: 'var(--ink-50)', cursor: 'pointer', fontSize: 16 }}>×</button>
    </div>
    <div style={{ padding: 14 }}>
      <div className="hint" style={{ marginBottom: 6 }}>화면</div>
      <div className="chips" style={{ marginBottom: 14 }}>
        {[['dashboard','대시보드'],['transit','교통'],['lunch','점심'],['library','도서관'],['history','이력'],['settings','설정']].map(([k, l]) => (
          <button key={k} className="chip" aria-pressed={route === k} onClick={() => setRoute(k)}>{l}</button>
        ))}
      </div>
    </div>
  </div>
);

export default App;
