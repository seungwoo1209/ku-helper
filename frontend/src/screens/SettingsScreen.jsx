import { SectionHead, Btn, Toggle } from '../components/ui';

const SettingsScreen = ({ state, setState }) => {
  const days = state.settings.hours;
  return (
    <>
      <div className="page-intro">
        <p>알림을 수신할 시간대를 요일별로 지정합니다. 활성 구간 바깥에서 충족된 조건은 발송되지 않습니다.</p>
      </div>

      <SectionHead title="활성 시간대" meta="요일별 · 24시간" />
      {days.map((d) => (
        <div className="hours" key={d.label}>
          <span className="day">{d.label}</span>
          <div>
            <div className="track">
              <div className="fill" style={{ left: `${(d.from/24)*100}%`, width: `${((d.to - d.from)/24)*100}%` }}></div>
            </div>
            <div className="ticks">
              {[0,3,6,9,12,15,18,21].map(h => <span key={h}>{String(h).padStart(2,'0')}:00</span>)}
            </div>
          </div>
        </div>
      ))}

      <div className="divider"></div>

      <div className="two-col">
        <div>
          <SectionHead title="계정" />
          <div className="rules">
            <div className="rule">
              <div className="idx">01</div>
              <div className="main-col">
                <h3>디스코드 연결</h3>
                <div className="sub">서지원 · seojiwon#4912 · 5월 8일 인증 갱신</div>
                <div className="conds">
                  <span className="cond"><span className="k">SCOPE</span> identify · guilds.join</span>
                  <span className="cond"><span className="k">TOKEN</span> refresh · 7d</span>
                </div>
              </div>
              <div className="right">
                <Btn>재인증</Btn>
              </div>
            </div>
            <div className="rule">
              <div className="idx">02</div>
              <div className="main-col">
                <h3>계정 연결 해제</h3>
                <div className="sub">알림 설정, 발송 이력, Discord 토큰이 모두 삭제됩니다.</div>
              </div>
              <div className="right">
                <button className="btn" style={{ borderColor: "rgba(122,46,31,.4)", color: "var(--bad)" }}>연결 해제</button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <SectionHead title="DM 실패 대응" />
          <div className="rules">
            <div className="rule">
              <div className="idx">01</div>
              <div className="main-col">
                <h3>재시도 정책</h3>
                <div className="sub">지수 백오프 1초 · 2초 · 4초, 최대 3회.</div>
                <div className="conds">
                  <span className="cond"><span className="k">RETRY</span> 3</span>
                  <span className="cond"><span className="k">BACKOFF</span> 1s · 2s · 4s</span>
                </div>
              </div>
              <div className="right"><Toggle checked onChange={() => {}} /></div>
            </div>
            <div className="rule">
              <div className="idx">02</div>
              <div className="main-col">
                <h3>대시보드 실패 배너</h3>
                <div className="sub">발송 실패가 발생하면 상단에 배너로 안내합니다.</div>
              </div>
              <div className="right"><Toggle checked onChange={() => {}} /></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default SettingsScreen;
