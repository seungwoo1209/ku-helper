import { fmtTime } from '../utils/time';
import { getAccessToken, callRefresh } from './auth';

const BASE = '/api/v1/me/notifications';
const IMMEDIATE = '/api/v1/me/immediate-send';
const HISTORY_BASE = '/api/v1/me/notifications/history';

function authHeaders() {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${getAccessToken()}` };
}

// 401 시 토큰 갱신 후 1회 재시도
async function authFetch(url, options = {}) {
  let res = await fetch(url, { ...options, headers: authHeaders() });
  if (res.status === 401) {
    const newToken = await callRefresh();
    if (newToken) res = await fetch(url, { ...options, headers: authHeaders() });
  }
  return res;
}

export async function listNotifications() {
  const res = await authFetch(BASE);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function createNotification(payload) {
  const res = await authFetch(BASE, { method: 'POST', body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function updateNotification(type, id, payload) {
  const res = await authFetch(`${BASE}/${type.toLowerCase()}/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function deleteNotification(id) {
  const res = await authFetch(`${BASE}/${id}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
}

export async function immediateSendLunch() {
  const res = await authFetch(`${IMMEDIATE}/lunch`, { method: 'POST' });
  if (res.status === 429) throw new Error('RATE_LIMITED');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function immediateSendTransit(station_name, line) {
  const res = await authFetch(`${IMMEDIATE}/transit`, {
    method: 'POST',
    body: JSON.stringify({ station_name, line }),
  });
  if (res.status === 429) throw new Error('RATE_LIMITED');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function immediateSendLibrary(reading_room_id) {
  const res = await authFetch(`${IMMEDIATE}/library`, {
    method: 'POST',
    body: JSON.stringify({ reading_room_id }),
  });
  if (res.status === 429) throw new Error('RATE_LIMITED');
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/* API 응답 → 화면 표시용 형태 변환 */
function toDisplayItem(n) {
  const base = { id: n.id, on: n.enabled, type: n.type, config: n.config };
  const c = n.config;

  if (n.type === 'TRANSIT') {
    if (c.mode === 'arrival') {
      return {
        ...base,
        name: `${c.station_name} ${c.line}`,
        sub: `${c.station_name}역 · ${c.line} · ${c.direction} · 도착 ${c.minutes_before}분 전`,
        conds: [
          { k: '역', v: c.station_name },
          { k: '노선', v: c.line },
          { k: '방향', v: c.direction },
          { k: '발송', v: `도착 ${c.minutes_before}분 전` },
          { k: '혼잡도', v: c.include_congestion ? '포함' : '제외' },
        ],
      };
    }
    return {
      ...base,
      name: `${c.station_name} ${c.line}`,
      sub: `${c.station_name}역 · ${c.line} · 매 ${c.repeat_interval_minutes}분`,
      conds: [
        { k: '역', v: c.station_name },
        { k: '노선', v: c.line },
        { k: '간격', v: `${c.repeat_interval_minutes}분` },
        { k: '시간', v: `${fmtTime(c.start_time)}–${fmtTime(c.end_time)}` },
        { k: '혼잡도', v: c.include_congestion ? '포함' : '제외' },
      ],
    };
  }

  if (n.type === 'LUNCH') {
    const at = fmtTime(c.notify_at);
    return {
      ...base,
      name: `점심 알림 — ${at}`,
      sub: `${at} 발송`,
      conds: [
        { k: '시각', v: at },
        { k: '오늘의 추천', v: c.highlight_today_pick ? '강조' : '끄기' },
        ...(c.max_price != null ? [{ k: '최대 가격', v: `${c.max_price.toLocaleString()}원` }] : []),
      ],
    };
  }

  if (n.type === 'LIBRARY') {
    const roomLabel = { 0: '전체 열람실', 1: '제1열람실', 2: '제2열람실', 3: '제3열람실', 5: '제5열람실' }[c.reading_room_id] ?? `열람실 ${c.reading_room_id}`;
    return {
      ...base,
      name: roomLabel,
      sub: `임계 ${c.threshold}석${c.urgent_threshold ? ` · 긴급 ${c.urgent_threshold}석` : ''}`,
      conds: [
        { k: '열람실', v: roomLabel },
        { k: '임계', v: `${c.threshold}석` },
        ...(c.urgent_threshold != null ? [{ k: '긴급', v: `${c.urgent_threshold}석` }] : []),
      ],
    };
  }

  return base;
}

export async function listNotificationHistory() {
  const res = await authFetch(HISTORY_BASE);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function fmtSentAt(isoStr) {
  const kst = new Date(new Date(isoStr).getTime() + 9 * 60 * 60 * 1000);
  const mm = String(kst.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(kst.getUTCDate()).padStart(2, '0');
  const hh = String(kst.getUTCHours()).padStart(2, '0');
  const min = String(kst.getUTCMinutes()).padStart(2, '0');
  return `${mm}-${dd} ${hh}:${min}`;
}

function historyItemToDisplay(h) {
  const time = fmtSentAt(h.sent_at);
  const fail = h.status === 'FAILED';
  const p = h.payload ?? {};

  if (h.type === 'TRANSIT') {
    if (fail) return { time, kind: 'TRANSIT', title: '교통 알림', detail: h.failure_reason ?? '오류', fail };
    const first = p.arrivals?.[0];
    const detail = first ? `${first.direction} · 약 ${Math.round(first.arrival_seconds / 60)}분 후` : '';
    return { time, kind: 'TRANSIT', title: `${p.station_name} ${p.line}`, detail, fail };
  }
  if (h.type === 'LUNCH') {
    const detail = p.restaurants?.map(r => r.name).join(' / ') ?? '';
    return { time, kind: 'LUNCH', title: p.cafeteria_name ?? '학식 알림', detail, fail };
  }
  if (h.type === 'LIBRARY') {
    return { time, kind: 'LIBRARY', title: `${p.label} 잔여 ${p.available}석`, detail: `임계값 ${p.threshold}석 이하 도달`, fail };
  }
  return { time, kind: h.type, title: h.type, detail: h.failure_reason ?? '', fail };
}

export function buildHistoryFromResponse(items) {
  return items.map(historyItemToDisplay);
}

export function buildStateFromNotifications(notifications) {
  return {
    transit: { rules: notifications.filter(n => n.type === 'TRANSIT').map(toDisplayItem) },
    lunch:   { rules: notifications.filter(n => n.type === 'LUNCH').map(toDisplayItem) },
    library: { rooms: notifications.filter(n => n.type === 'LIBRARY').map(toDisplayItem) },
  };
}
