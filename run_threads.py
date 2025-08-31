import threading
import time

from fastapi_stars.scripts import init_django  # noqa: F401


def start():
    from integrations.payments.ton_deposit import check_ton_deposits
    from integrations.workers import send_transaction_worker, check_transaction_worker

    threading.Thread(target=check_ton_deposits, daemon=True).start()
    threading.Thread(target=send_transaction_worker, daemon=True).start()
    threading.Thread(target=check_transaction_worker, daemon=True).start()

    while True:
        time.sleep(10)


if __name__ == "__main__":
    start()
