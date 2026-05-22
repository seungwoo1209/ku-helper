"""admin 도메인 고유 예외 placeholder.

require_role 가드의 `NotAuthorizedForRole` 은 generic 권한 예외이므로 `app/core/security.py`
에 정의돼 있다. admin 도메인 본체(통계·크롤러 상태 등) 가 자체 예외가 필요해지는 시점에
여기에 정의한다.
"""
