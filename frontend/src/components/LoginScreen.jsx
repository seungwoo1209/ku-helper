const LoginScreen = ({ onLogin }) => (
  <div className="login">
    <div className="frame">
      <div className="left">
        <div className="brand" style={{ marginBottom: 12 }}>
          <span className="brand-mark"></span>
          <span className="brand-name">campus<b>알리미</b></span>
        </div>
        <div className="display">매일 살피던 정보를,<br/>한 곳에서.</div>
        <p className="lede">
          지하철 도착, 학식 메뉴, 도서관 잔여 좌석. 흩어진 정보를
          디스코드 DM으로 모아 보냅니다. 별도 앱 없이, 이미 쓰던 곳으로.
        </p>
        <div className="features">
          <span>교통 · 서울 공공 API 실시간</span>
          <span>점심 · 학식 + 음식점 추천</span>
          <span>도서관 · 임계값 감시 · 30s 이내</span>
          <span>모두 DM 임베드로 도착</span>
        </div>
      </div>
      <div className="right">
        <div>
          <h3>로그인</h3>
          <p>디스코드 계정만으로 시작합니다. 회원가입은 없습니다.</p>
          <button className="discord-btn" onClick={() => { window.location.href = '/api/v1/auth/discord/login'; }}>
            <svg width="18" height="14" viewBox="0 0 18 14" fill="currentColor">
              <path d="M15.2 1.3A14.2 14.2 0 0 0 11.6.3a10 10 0 0 0-.4.8 13 13 0 0 0-4.4 0 9 9 0 0 0-.4-.8C5.4.5 4.2.8 3 1.3 1 4 .4 6.6.7 9.2c1.4 1 2.7 1.7 4.1 2.1.3-.4.6-.9.8-1.4-.5-.2-1-.4-1.5-.7l.4-.3a9.4 9.4 0 0 0 8.2 0c.1.1.3.2.4.3-.5.3-1 .5-1.5.7.2.5.5 1 .8 1.4 1.4-.4 2.7-1.1 4.1-2.1.3-3-.5-5.6-2.3-7.9zM6 7.7c-.8 0-1.5-.7-1.5-1.7s.7-1.7 1.5-1.7c.9 0 1.5.7 1.5 1.7s-.6 1.7-1.5 1.7zm6 0c-.8 0-1.5-.7-1.5-1.7s.7-1.7 1.5-1.7c.9 0 1.5.7 1.5 1.7s-.6 1.7-1.5 1.7z"/>
            </svg>
            Discord로 계속하기
          </button>
          <div className="legal">로그인 시 캠퍼스 알리미 디스코드 서버에 자동 가입됩니다.</div>
        </div>
        <div>
          <div className="hint" style={{ marginBottom: 8 }}>요청 권한</div>
          <div className="chips">
            <span className="cond"><span className="k">SCOPE</span> identify</span>
            <span className="cond"><span className="k">SCOPE</span> guilds.join</span>
            <span className="cond"><span className="k">TOKEN</span> refresh 7d</span>
          </div>
        </div>
      </div>
    </div>
    <div className="fineprint">CAMPUS · ALARM · v0.9 · BUILD 2026.05.13</div>
  </div>
);

export default LoginScreen;
