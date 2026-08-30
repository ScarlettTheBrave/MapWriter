import pymem
import sys

INSTANCE_ADDRESSES = [
    0x2277d772028, 0x22780d58a08, 0x227819e5f50, 0x2278a4bfb70, 0x22791c3f340,
    0x2279bb3a140, 0x227c8d8d280, 0x227ca9a2920, 0x227cabb85a8, 0x227cb781298,
    0x227cc3760d8, 0x227cc8b12d0, 0x227cd426420, 0x227d0307ff0, 0x227d1ebf418,
    0x227d4d92f70, 0x227d5fd4aa0, 0x227d8598e40, 0x227d99e35d0, 0x227de8884d0,
    0x227de9da920, 0x227df91c4d8, 0x227e2968588, 0x227e3a840f8, 0x227e5370808,
    0x227e53a5040, 0x227e5c413f8, 0x227e814d4f8, 0x227e7da75a8, 0x2280020d070,
    0x227fff58650, 0x227fff5ec78, 0x227ff212490, 0x227fe59d8a0, 0x227fe5a13c0,
    0x227fe10f0f0, 0x228004f3cc8,
]

def main():
    try:
        pm = pymem.Pymem("Content.Client.exe")
    except pymem.exception.ProcessNotFound:
        print("Ошибка: игра не запущена.")
        sys.exit()

    print("=" * 55)
    print(f"{'АДРЕС ИНСТАНСА':<18} | {'ТОЧЕК В СЛОВАРЕ BLIPS'}")
    print("=" * 55)

    for addr in INSTANCE_ADDRESSES:
        if addr == 0: continue

        try:
            blips_ptr = pm.read_longlong(addr + 0x18)
            if blips_ptr == 0: continue

            # ВОЗВРАЩАЕМ ТВОИ СТАРЫЕ, ПРОВЕРЕННЫЕ СМЕЩЕНИЯ!
            raw_count = pm.read_int(blips_ptr + 0x38)
            free_count = pm.read_int(blips_ptr + 0x40)
            actual_count = raw_count - free_count

            # Если число выглядит как полный бред (например, отрицательное или миллиард), игнорируем
            if actual_count < 0 or actual_count > 10000:
                continue

            marker = " <--- ВОТ НАШ РАБОЧИЙ АДРЕС!" if actual_count > 0 else ""
            print(f"{hex(addr):<18} | {actual_count}{marker}")

        except Exception:
            pass # Игнорируем ошибки чтения мертвого мусора

    print("=" * 55)

if __name__ == "__main__":
    main()