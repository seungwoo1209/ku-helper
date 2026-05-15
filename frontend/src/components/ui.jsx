export const Ico = ({ d, size = 14, sw = 1.4 }) => (
  <svg className="ico" width={size} height={size} viewBox="0 0 16 16" fill="none"
       stroke="currentColor" strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">
    {typeof d === 'string' ? <path d={d} /> : d}
  </svg>
);

export const Icons = {
  dashboard: <><rect x="2" y="2" width="5" height="5"/><rect x="9" y="2" width="5" height="3"/><rect x="9" y="7" width="5" height="7"/><rect x="2" y="9" width="5" height="5"/></>,
  transit:   <><circle cx="8" cy="8" r="5.5"/><path d="M5.5 8h5M8 5.5v5"/></>,
  lunch:     <><path d="M3 3v4a3 3 0 0 0 6 0V3M6 3v10"/><path d="M11 3c1.5 0 2 1 2 2.5S12.5 8 11 8v5"/></>,
  library:   <><path d="M3 3h3v10H3zM7 4h3v9H7zM11 5l2 .5L11.5 13l-2-.5z"/></>,
  history:   <><path d="M8 3a5 5 0 1 0 4.6 7"/><path d="M13 3v3h-3M8 5.5V8l1.5 1.5"/></>,
  settings:  <><circle cx="8" cy="8" r="2"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></>,
  admin:     <><path d="M8 1.5l5.5 2v4c0 3.2-2.4 5.6-5.5 7-3.1-1.4-5.5-3.8-5.5-7v-4z"/><path d="M6 8l1.5 1.5L10.5 6.5"/></>,
  bell:      <><path d="M4 11V7a4 4 0 0 1 8 0v4l1 1.5H3z"/><path d="M6.5 13.5a1.5 1.5 0 0 0 3 0"/></>,
  plus:      <><path d="M8 3v10M3 8h10"/></>,
  arrow:     <><path d="M3 8h10M9 4l4 4-4 4"/></>,
  chevron:   <><path d="M6 4l4 4-4 4"/></>,
  more:      <><circle cx="3" cy="8" r=".6"/><circle cx="8" cy="8" r=".6"/><circle cx="13" cy="8" r=".6"/></>,
  check:     <><path d="M3 8.5l3 3 7-7"/></>,
};

export const Toggle = ({ checked, onChange }) => (
  <button type="button" className="toggle" aria-checked={checked}
          role="switch" onClick={() => onChange(!checked)} />
);

export const Btn = ({ children, primary, onClick, type = "button" }) => (
  <button type={type} className={"btn " + (primary ? "primary" : "")} onClick={onClick}>
    {children}
  </button>
);

export const StatusPill = ({ children }) => (
  <span className="status-pill"><span className="dot"></span>{children}</span>
);

export const SectionHead = ({ title, meta }) => (
  <div className="section-head">
    <h2>{title}</h2>
    {meta && <span className="meta">{meta}</span>}
  </div>
);

export const Modal = ({ open, onClose, crumb, title, children, footer }) => {
  if (!open) return null;
  return (
    <div className="modal-scrim" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true">
        <div className="modal-head">
          {crumb && <div className="crumb">{crumb}</div>}
          <h3>{title}</h3>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
};

export const Field = ({ label, children }) => (
  <div className="field">
    <label>{label}</label>
    {children}
  </div>
);

export const Chips = ({ options, value, onChange, multi = true }) => (
  <div className="chips">
    {options.map(o => {
      const active = multi ? value.includes(o.value) : value === o.value;
      return (
        <button key={o.value} type="button" className="chip" aria-pressed={active}
                onClick={() => {
                  if (multi) {
                    onChange(active ? value.filter(v => v !== o.value) : [...value, o.value]);
                  } else {
                    onChange(o.value);
                  }
                }}>
          {o.label}
        </button>
      );
    })}
  </div>
);

export const EmbedPreview = ({ kind = "교통", title, sub, fields = [], footnote, urgent }) => (
  <div className="embed-preview">
    <div className="head">
      <span>Discord · DM 미리보기</span>
      <span>{kind}</span>
    </div>
    <div className={"body" + (urgent ? " urgent" : "")}>
      <div className="title">{title}</div>
      <div className="sub">{sub}</div>
      {fields.length > 0 && (
        <div className="fields">
          {fields.map((f, i) => (
            <div key={i}>
              <div className="k">{f.k}</div>
              <div className="v">{f.v}</div>
            </div>
          ))}
        </div>
      )}
    </div>
    <div className="foot">{footnote}</div>
  </div>
);
