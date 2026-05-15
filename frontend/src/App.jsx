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

const ROUTE_LABELS = {
  dashboard: "01 대시보드", transit: "02 교통", lunch: "03 점심",
  library: "04 도서관", history: "05 이력", settings: "06 설정",
};

function App() {
  const [authed, setAuthed] = useState(false);
  const [route, setRoute]   = useState("dashboard");
  const [state, setState]   = useState(SAMPLE);
  const [modal, setModal]   = useState(null);
  const [tweaksOpen, setTweaksOpen] = useState(false);

  useEffect(() => {
    const onMsg = (e) => {
      if (e.data?.type === '__activate_edit_mode') setTweaksOpen(true);
      else if (e.data?.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);

  if (!authed) return <LoginScreen onLogin={() => setAuthed(true)} />;

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
      <Sidebar route={route} setRoute={setRoute} />
      <main className="main" data-screen-label={ROUTE_LABELS[route] || route}>
        <TopBar route={route} />
        {body}
      </main>

      <RuleEditModal
        open={!!modal}
        kind={modal?.kind}
        rule={modal?.rule}
        onClose={closeModal}
        onSave={() => closeModal()}
      />

      {tweaksOpen && (
        <TweaksMini
          route={route} setRoute={setRoute}
          authed={authed} setAuthed={setAuthed}
          onClose={() => {
            setTweaksOpen(false);
            window.parent.postMessage({ type: '__edit_mode_dismissed' }, '*');
          }} />
      )}
    </div>
  );
}

const TweaksMini = ({ route, setRoute, authed, setAuthed, onClose }) => (
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
      <div className="hint" style={{ marginBottom: 6 }}>인증 상태</div>
      <div className="chips">
        <button className="chip" aria-pressed={authed} onClick={() => setAuthed(true)}>로그인 후</button>
        <button className="chip" aria-pressed={!authed} onClick={() => setAuthed(false)}>로그인 화면</button>
      </div>
    </div>
  </div>
);

export default App;
