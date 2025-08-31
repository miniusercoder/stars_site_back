if True:  # Не сортировать этот импорт
    from fastapi_stars.scripts import init_django  # noqa: F401

import threading
import time

from integrations.payments.ton_deposit import check_ton_deposits


def start():
    threading.Thread(target=check_ton_deposits, daemon=True).start()

    while True:
        time.sleep(10)


if __name__ == "__main__":
    start()
