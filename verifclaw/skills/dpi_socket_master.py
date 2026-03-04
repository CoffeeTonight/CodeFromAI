async def dpi_socket_master(pending_forcing: list):
    """실시간 DPI forcing 스킬 (현재는 dummy)"""
    if pending_forcing:
        print(f"[DPI] Forcing 실행 예정: {len(pending_forcing)}개 신호")
        for item in pending_forcing:
            print(f"   → 신호: {item.get('signal')} = {item.get('value')}")
    else:
        print("[DPI] Forcing 대기열 비어 있음")
    return True