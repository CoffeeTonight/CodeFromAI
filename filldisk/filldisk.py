import os
import ctypes
from pathlib import Path
import time

# Windows에서 실제 사용 가능한 여유 공간 확인 (바이트 단위로 반환)
def get_free_bytes(path="."):
    path = str(Path(path).resolve())
    if not os.path.exists(path):
        print(f"경로가 존재하지 않습니다: {path}")
        return 999_999_999_999  # 매우 큰 값

    free_bytes = ctypes.c_ulonglong(0)
    success = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
        ctypes.c_wchar_p(path),
        ctypes.byref(free_bytes),
        None,
        None
    )
    if not success:
        print("GetDiskFreeSpaceExW 실패")
        return -1
    return free_bytes.value


def fill_disk_realistic(target_dir=r"D:\test_fill"):
    target = Path(target_dir)
    print(f"대상 경로: {target}\n")

    if not target.exists():
        try:
            target.mkdir(parents=True, exist_ok=True)
            print("폴더를 생성했습니다.\n")
        except Exception as e:
            print(f"폴더 생성 실패: {e}")
            return

    file_count = 0
    total_written = 0

    print("디스크 채우기 시작...\n")

    try:
        # 1단계: 큰 파일로 빠르게 채우기 (32MB → 1MB)
        for size_mb in [32, 16, 8, 4, 2, 1]:
            chunk = size_mb * 1024 * 1024
            while True:
                free = get_free_bytes(target)
                if free < chunk + 1024*1024:  # 최소 1MB 여유 확보
                    break

                filename = target / f"big_{file_count:05d}_{size_mb}MB.dat"
                try:
                    with open(filename, "wb") as f:
                        f.write(b"\x00" * chunk)
                    written = os.path.getsize(filename)
                    total_written += written
                    file_count += 1
                    print(f"{file_count:4d} | {size_mb:2d}MB 파일 생성  |  총: {total_written//(1024**2):7,} MB")
                except OSError:
                    break
                except Exception as e:
                    print(f"오류: {e}")
                    return

        # 2단계: 4KB 단위로 정밀하게 채우기
        print("\n→ 4KB 단위 정밀 채우기 단계 시작\n")
        chunk_4kb = 4096
        while True:
            free = get_free_bytes(target)
            if free < chunk_4kb * 2:  # 최소 2개 클러스터 여유
                break

            try:
                filename = target / f"mid_{file_count:06d}_4KB.dat"
                with open(filename, "wb") as f:
                    f.write(b"\x00" * chunk_4kb)
                written = os.path.getsize(filename)
                total_written += written
                file_count += 1

                if file_count % 50 == 0:
                    print(f"{file_count:6d} | 4KB 파일 ×50개  |  총: {total_written//(1024**2):7,} MB")
            except OSError:
                break

        # 3단계: 정말 마지막까지 - 1바이트 파일 대량 생성
        print("\n→ 마지막 1바이트 필사 모드 시작\n")
        tiny_count = 0
        while tiny_count < 1_000_000:  # 최대 100만개 시도 (안전장치)
            free = get_free_bytes(target)
            if free < 4096:  # 1클러스터도 안 남으면 종료
                break

            try:
                name = target / f"tiny_{file_count:08d}.txt"
                with open(name, "wb") as f:
                    f.write(b"x")  # 1바이트
                file_count += 1
                tiny_count += 1

                if tiny_count % 5000 == 0:
                    print(f"tiny 파일 {tiny_count:6,}개 생성 중... (총 파일 {file_count:,}개)")
            except OSError:
                break
            except Exception as e:
                print(f"tiny 쓰기 중 오류: {e}")
                break

        print("\n" + "═" * 70)
        print("채우기 완료 (또는 더 이상 쓸 공간 없음)")
        print(f"총 생성 파일 수 : {file_count:,} 개")
        print(f"총 사용한 용량  : 약 {total_written // (1024**2):,} MB")
        final_free = get_free_bytes(target) // 1024
        print(f"최종 남은 공간  : 약 {final_free:,} KB")
        print("═" * 70)

    except KeyboardInterrupt:
        print("\n사용자에 의한 중단")
    except Exception as e:
        print(f"예상치 못한 오류: {e}")


if __name__ == "__main__":
    # 반드시 경로 확인 후 실행하세요!
    fill_disk_realistic(r"D:\test_fill")