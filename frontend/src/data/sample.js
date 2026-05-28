export const SAMPLE = {
  transit: {
    on: true,
    rules: [
      { id: 't1', on: true,  name: "신촌 2호선 — 등굣길",
        sub: "신촌역 · 내선순환 · 도착 3분 전",
        conds: [
          { k: "역", v: "신촌" }, { k: "노선", v: "2호선" },
          { k: "방향", v: "내선순환" }, { k: "발송", v: "도착 3분 전" },
          { k: "요일", v: "월–금" }, { k: "시간", v: "08:00–09:30" },
        ]},
      { id: 't2', on: true,  name: "강남 9호선 — 자취방 복귀",
        sub: "강남역 · 김포공항 방면 · 매 15분 반복",
        conds: [
          { k: "역", v: "강남" }, { k: "노선", v: "9호선" },
          { k: "간격", v: "15분" }, { k: "시간", v: "18:00–19:30" },
        ]},
      { id: 't3', on: false, name: "건대입구 7호선 — 주말 약속",
        sub: "장암 방면 · 도착 5분 전 · 토요일",
        conds: [
          { k: "역", v: "건대입구" }, { k: "노선", v: "7호선" },
          { k: "발송", v: "5분 전" }, { k: "요일", v: "토" },
        ]},
    ]
  },
  lunch: {
    on: true,
    rules: [
      { id: 'l1', on: true, name: "본관 학생식당 — 평일 11:30",
        sub: "메뉴 + 주변 음식점 3+",
        conds: [
          { k: "식당", v: "본관 A" }, { k: "시각", v: "11:30" },
          { k: "요일", v: "월–금" },
        ]},
      { id: 'l2', on: false, name: "기숙사 식당 — 저녁",
        sub: "메뉴 알림 · 17:30 · 주변 추천 없음",
        conds: [
          { k: "식당", v: "기숙사" }, { k: "시각", v: "17:30" },
          { k: "추천", v: "off" },
        ]},
    ]
  },
  library: {
    on: true,
    rooms: [
      { id: 'b1', on: true, name: "제 1 열람실 — 본관 3F",
        sub: "정원 280석 · 임계 20석 · 긴급 8석",
        conds: [
          { k: "정원", v: "280" }, { k: "임계", v: "20석" }, { k: "긴급", v: "8석" },
        ]},
      { id: 'b2', on: true, name: "제 4 열람실 — 도서관 1F",
        sub: "정원 240석 · 임계 25석 · 긴급 10석",
        conds: [
          { k: "정원", v: "240" }, { k: "임계", v: "25석" }, { k: "긴급", v: "10석" },
        ]},
      { id: 'b3', on: false, name: "대학원 열람실 — 별관 4F",
        sub: "정원 90석 · 임계 5석",
        conds: [
          { k: "정원", v: "90" }, { k: "임계", v: "5석" },
        ]},
    ]
  },
  feed: [
    { time: "11:30:02", kind: "LUNCH",   title: "본관 학생식당 메뉴",   detail: "김치찌개 · 닭갈비덮밥 · 추천: 소담" },
    { time: "10:42:18", kind: "TRANSIT", title: "신촌역 2호선",         detail: "내선순환 도착 3분 전" },
    { time: "09:58:44", kind: "LIBRARY", title: "제 4 열람실 잔여 23석", detail: "임계값 25석 이하 도달" },
    { time: "08:21:04", kind: "TRANSIT", title: "신촌역 2호선",         detail: "내선순환 도착 3분 전" },
    { time: "07:55:11", kind: "TRANSIT", title: "강남역 9호선",         detail: "김포공항 방면 도착 5분 전" },
    { time: "07:30:00", kind: "SYSTEM",  title: "활성 시간대 시작",     detail: "월요일 · 07:30–22:00" },
  ],
  history: [
    { time: "05-13 11:30", kind: "LUNCH",   title: "본관 학생식당 메뉴",     detail: "추천: 소담 / 비빔국수" },
    { time: "05-13 10:42", kind: "TRANSIT", title: "신촌역 2호선 내선순환",  detail: "도착 3분 전 / 지연 0분" },
    { time: "05-13 09:58", kind: "LIBRARY", title: "제 4 열람실 잔여 23석",  detail: "임계 25석 이하" },
    { time: "05-13 08:21", kind: "TRANSIT", title: "신촌역 2호선 내선순환",  detail: "도착 3분 전" },
    { time: "05-12 22:14", kind: "LIBRARY", title: "긴급 · 제 4 열람실 8석", detail: "긴급 임계 도달" },
    { time: "05-12 18:15", kind: "TRANSIT", title: "강남역 9호선",           detail: "정기 간격 알림" },
    { time: "05-12 11:30", kind: "LUNCH",   title: "본관 학생식당 메뉴",     detail: "추천: 일미식당 / 제육덮밥" },
    { time: "05-12 08:21", kind: "TRANSIT", title: "신촌역 2호선 내선순환",  detail: "DM 발송 실패 (재시도 3/3)", fail: true },
    { time: "05-11 11:30", kind: "LUNCH",   title: "본관 학생식당 메뉴",     detail: "추천: 소담 / 김밥" },
    { time: "05-11 09:12", kind: "ADMIN",   title: "크롤러 회복",             detail: "library-scraper / 3회 실패 후 정상" },
    { time: "05-10 12:00", kind: "LUNCH",   title: "본관 학생식당 메뉴",     detail: "추천: 청년면옥 / 잔치국수" },
    { time: "05-10 08:21", kind: "TRANSIT", title: "신촌역 2호선 내선순환",  detail: "도착 3분 전 / 여유" },
  ],
  settings: {
    hours: [
      { label: "월요일",  from: 7.5,  to: 22 },
      { label: "화요일",  from: 7.5,  to: 22 },
      { label: "수요일",  from: 7.5,  to: 22 },
      { label: "목요일",  from: 7.5,  to: 22 },
      { label: "금요일",  from: 7.5,  to: 21 },
      { label: "토요일",  from: 10,   to: 19 },
      { label: "일요일",  from: 10,   to: 19 },
    ]
  }
};
