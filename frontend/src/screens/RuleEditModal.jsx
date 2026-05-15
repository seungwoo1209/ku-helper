import { useState, useEffect } from 'react';
import { Modal, Field, Btn, Chips } from '../components/ui';

const RuleEditModal = ({ open, rule, onClose, onSave, kind }) => {
  const [name, setName] = useState(rule?.name || "");
  const [days, setDays] = useState(['mon','tue','wed','thu','fri']);
  useEffect(() => { if (rule) { setName(rule.name); } }, [rule]);

  const isTransit = kind === 'transit';
  const isLunch   = kind === 'lunch';
  const isLibrary = kind === 'library';

  return (
    <Modal open={open} onClose={onClose}
      crumb={kind === 'transit' ? "교통 알림" : kind === 'lunch' ? "점심 알림" : "도서관 알림"}
      title={rule ? "규칙 편집" : "새 규칙"}
      footer={<>
        <Btn onClick={onClose}>취소</Btn>
        <Btn primary onClick={() => onSave({ name })}>저장</Btn>
      </>}>
      <Field label="규칙 이름">
        <input className="input" value={name} onChange={(e) => setName(e.target.value)}
               placeholder="예) 신촌 2호선 — 등굣길" />
      </Field>

      {isTransit && (
        <>
          <div className="field-row">
            <Field label="역명">
              <input className="input" defaultValue="신촌역" />
            </Field>
            <Field label="노선">
              <select className="select" defaultValue="2호선">
                <option>1호선</option><option>2호선</option><option>3호선</option><option>4호선</option><option>9호선</option>
              </select>
            </Field>
          </div>
          <div className="field-row">
            <Field label="방향">
              <select className="select" defaultValue="내선순환">
                <option>내선순환</option><option>외선순환</option><option>상행</option><option>하행</option>
              </select>
            </Field>
            <Field label="발송 시점">
              <select className="select" defaultValue="도착 3분 전">
                <option>도착 1분 전</option><option>도착 3분 전</option><option>도착 5분 전</option><option>정기 간격</option>
              </select>
            </Field>
          </div>
        </>
      )}

      {isLunch && (
        <>
          <div className="field-row">
            <Field label="식당">
              <select className="select" defaultValue="본관 학생식당 A">
                <option>본관 학생식당 A</option><option>중앙도서관 푸드코트</option><option>제 2 기숙사 식당</option>
              </select>
            </Field>
            <Field label="발송 시각">
              <input className="input" type="time" defaultValue="11:30" />
            </Field>
          </div>
          <Field label="주변 음식점 — 최대 가격">
            <input className="input" defaultValue="₩9,000" />
          </Field>
        </>
      )}

      {isLibrary && (
        <>
          <div className="field-row">
            <Field label="열람실">
              <select className="select" defaultValue="제 1 열람실">
                <option>제 1 열람실</option><option>제 2 열람실</option><option>제 3 열람실</option><option>제 4 열람실</option>
              </select>
            </Field>
            <Field label="임계값 (잔여 좌석)">
              <input className="input" type="number" defaultValue={20} />
            </Field>
          </div>
          <div className="field-row">
            <Field label="긴급 임계값">
              <input className="input" type="number" defaultValue={8} />
            </Field>
            <Field label="긴급 표시">
              <select className="select" defaultValue="임베드 빨간색">
                <option>임베드 빨간색</option><option>표시 없음</option>
              </select>
            </Field>
          </div>
        </>
      )}

      <Field label="요일">
        <Chips
          options={[
            { value: 'mon', label: '월' }, { value: 'tue', label: '화' }, { value: 'wed', label: '수' },
            { value: 'thu', label: '목' }, { value: 'fri', label: '금' }, { value: 'sat', label: '토' }, { value: 'sun', label: '일' }
          ]}
          value={days}
          onChange={setDays}
        />
      </Field>
    </Modal>
  );
};

export default RuleEditModal;
