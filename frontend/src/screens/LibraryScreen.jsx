import { SectionHead, EmbedPreview } from '../components/ui';
import RuleRow from '../components/RuleRow';
import { updateNotification } from '../api/notifications';

const LibraryScreen = ({ state, setState, onEdit, onAdd }) => {
  const rooms = state.library.rooms;

  async function handleToggle(id, enabled) {
    setState(s => ({
      ...s,
      library: { ...s.library, rooms: s.library.rooms.map(x => x.id === id ? { ...x, on: enabled } : x) },
    }));
    try {
      await updateNotification('library', id, { enabled });
    } catch {
      setState(s => ({
        ...s,
        library: { ...s.library, rooms: s.library.rooms.map(x => x.id === id ? { ...x, on: !enabled } : x) },
      }));
    }
  }

  return (
    <>
      <div className="page-intro">
        <p>
          열람실별 잔여 좌석 임계값을 설정하면, 임계값 이하로 감소할 때 30초 이내에 DM이 도착합니다.
          잔여석이 회복되었다가 다시 떨어질 때까지 동일 알림은 재발송되지 않습니다.
        </p>
      </div>

      <SectionHead title="감시 중인 열람실" meta={`${rooms.length}개`} />
      <div className="rules">
        {rooms.length === 0 && <div className="hint" style={{ padding: '20px 0' }}>등록된 도서관 알림이 없습니다.</div>}
        {rooms.map((r, i) => (
          <RuleRow key={r.id} idx={i + 1} title={r.name} sub={r.sub} conds={r.conds}
                   on={r.on}
                   onToggle={(v) => handleToggle(r.id, v)}
                   onEdit={() => onEdit(r)} />
        ))}
      </div>
      <button className="add-rule" onClick={onAdd}>
        <span className="plus">+</span> 새 열람실 추가
      </button>

      <div className="divider"></div>
      <SectionHead title="DM 미리보기" meta="제 4 열람실 · 긴급 임계 도달" />
      <EmbedPreview
        urgent
        kind="도서관 · library · 긴급"
        title="긴급 · 제 4 열람실 잔여 8석"
        sub="22:14 발송 · 임계값 8석에 도달했습니다. 평소 회복까지 12–18분이 소요됩니다."
        fields={[
          { k: "잔여 / 정원", v: "8 / 240" },
          { k: "추세", v: "↘ 감소" },
          { k: "긴급 임계", v: "8석" },
        ]}
        footnote="이 알림은 잔여석 회복 후 재하락 시 다시 발송됩니다."
      />
    </>
  );
};

export default LibraryScreen;
