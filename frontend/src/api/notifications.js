import { fmtTime } from '../utils/time';
import { getAccessToken, callRefresh } from './auth';

const BASE = '/api/v1/me/notifications';
const IMMEDIATE = '/api/v1/me/immediate-send';

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
      ],
    };
  }

  if (n.type === 'LUNCH') {
    const at = fmtTime(c.notify_at);
    return {
      ...base,
      name: `점심 알림 — ${at}`,
      sub: `${at} 발송 · 추천 ${c.recommend_count}곳`,
      conds: [
        { k: '시각', v: at },
        { k: '추천', v: `${c.recommend_count}곳` },
        { k: '오늘의 추천', v: c.highlight_today_pick ? '강조' : '끄기' },
      ],
    };
  }

  if (n.type === 'LIBRARY') {
    return {
      ...base,
      name: `열람실 ${c.reading_room_id}`,
      sub: `임계 ${c.threshold}석${c.urgent_threshold ? ` · 긴급 ${c.urgent_threshold}석` : ''}`,
      conds: [
        { k: '열람실', v: c.reading_room_id },
        { k: '임계', v: `${c.threshold}석` },
        ...(c.urgent_threshold != null ? [{ k: '긴급', v: `${c.urgent_threshold}석` }] : []),
      ],
    };
  }

  return base;
}

export function buildStateFromNotifications(notifications) {
  return {
    transit: { rules: notifications.filter(n => n.type === 'TRANSIT').map(toDisplayItem) },
    lunch:   { rules: notifications.filter(n => n.type === 'LUNCH').map(toDisplayItem) },
    library: { rooms: notifications.filter(n => n.type === 'LIBRARY').map(toDisplayItem) },
  };
}
