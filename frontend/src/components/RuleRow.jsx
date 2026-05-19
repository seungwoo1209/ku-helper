import { Toggle } from './ui';

const RuleRow = ({ idx, title, sub, conds, on, onToggle, onEdit }) => (
  <div className="rule">
    <div className="idx">{String(idx).padStart(2, '0')}</div>
    <div className="main-col">
      <h3>{title}</h3>
      <div className="sub">{sub}</div>
      <div className="conds">
        {conds.map((c, i) => (
          <span className="cond" key={i}><span className="k">{c.k}</span> {c.v}</span>
        ))}
      </div>
    </div>
    <div className="right">
      <Toggle checked={on} onChange={onToggle} />
      <button className="menu" onClick={onEdit} aria-label="편집">⋯</button>
    </div>
  </div>
);

export default RuleRow;
